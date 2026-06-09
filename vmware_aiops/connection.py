"""Connection management for vCenter and ESXi hosts.

Handles multi-target connections via pyVmomi with session reuse.
"""

from __future__ import annotations

import atexit
import ssl
from typing import TYPE_CHECKING

from pyVmomi import vim, vmodl
from pyVmomi.VmomiSupport import VmomiJSONEncoder  # noqa: F401

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

from vmware_aiops.config import AppConfig, TargetConfig, load_config

# Component 6: per-request backend-credential routing (shared resolver lib).
# Optional - absent in local/stdio dev; routing then no-ops and the startup
# config credentials are used. vmware-monitor + vmware-aiops both front the
# PROD vCenter, so both resolve `MCP - <role> - vcenter-prod`. syseng-only per
# the C5 validator ACCESS matrix; the backend account's own RBAC enforces
# read-vs-write (aiops is write-capable, so only syseng_elevated reaches it).
try:
    import uaa_hub_routing

    _HUB_ROUTING = True
    _VCENTER_SELECTOR = uaa_hub_routing.priority_selector(
        ("syseng_elevated", "syseng_readonly")
    )
except ImportError:
    _HUB_ROUTING = False


# ServiceInstance is a pyVmomi ManagedObject — its __setattr__ rejects any
# attribute not in its allowed list (raises "Managed object attributes are
# read-only" on pyVmomi 8.x). We keep per-connection metadata in this module
# dict, keyed by id(si). Cleared via atexit when the SI is disconnected.
# 踩坑 #32 (2026-05-19, 客户 vCenter 8.0U3 现场).
_SI_VERIFY_SSL: dict[int, bool] = {}


def get_verify_ssl(si: ServiceInstance) -> bool:
    """Return verify_ssl flag stashed by the connect() that created ``si``.

    Defaults to True (strict) if the SI was created outside this manager.
    """
    return _SI_VERIFY_SSL.get(id(si), True)


class ConnectionManager:
    """Manages connections to multiple vCenter/ESXi targets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._connections: dict[str, ServiceInstance] = {}

    @classmethod
    def from_config(cls, config: AppConfig | None = None) -> ConnectionManager:
        cfg = config or load_config()
        return cls(cfg)

    def connect(self, target_name: str | None = None) -> ServiceInstance:
        """Connect to a target by name, or the default target.

        Component 6: when the hub validator routes the request (X-Hub-Roles
        present), resolve the per-role vCenter username/password from 1Password
        (`MCP - <role> - vcenter-prod`) and open the session with THOSE creds -
        host/port/tls unchanged - cached per (target, routed account). No
        routing signal (legacy bearer / non-hub / stdio) -> the startup-config
        session, unchanged. Fail closed: a present-but-unresolvable signal
        raises and the request is denied; it never falls back to the startup
        credential on a routing miss.
        """
        target = (
            self._config.get_target(target_name)
            if target_name
            else self._config.default_target
        )

        routed = (
            uaa_hub_routing.routing_item("vcenter-prod", _VCENTER_SELECTOR)
            if _HUB_ROUTING
            else None
        )
        cache_key = target.name if routed is None else f"{target.name}#{routed}"

        if cache_key in self._connections:
            si = self._connections[cache_key]
            try:
                # Test if session is still alive
                _ = si.content.sessionManager.currentSession
                return si
            except (vmodl.fault.NotAuthenticated, Exception):
                del self._connections[cache_key]

        if routed is None:
            si = self._create_connection(target)
        else:
            fields = uaa_hub_routing.resolve_fields(routed)
            user, pw = fields.get("username"), fields.get("password")
            if not user or not pw:
                raise uaa_hub_routing.RoutingError(
                    f"1P item {routed!r} missing username/password"
                )
            si = self._create_connection(target, user=user, pwd=pw)
        self._connections[cache_key] = si
        return si

    def disconnect(self, target_name: str) -> None:
        """Disconnect from a specific target."""
        if target_name in self._connections:
            from pyVim.connect import Disconnect

            Disconnect(self._connections[target_name])
            del self._connections[target_name]

    def disconnect_all(self) -> None:
        """Disconnect from all targets."""
        for name in list(self._connections):
            self.disconnect(name)

    def list_targets(self) -> list[str]:
        """List all configured target names."""
        return [t.name for t in self._config.targets]

    def list_connected(self) -> list[str]:
        """List currently connected target names."""
        return list(self._connections.keys())

    @staticmethod
    def _create_connection(
        target: TargetConfig, *, user: str | None = None, pwd: str | None = None
    ) -> ServiceInstance:
        """Create a new pyVmomi connection.

        ``user``/``pwd`` override the target's startup credentials (Component 6
        per-role routing); when omitted, the target's own username + env
        password are used (legacy/startup path).
        """
        from pyVim.connect import Disconnect, SmartConnect

        context = None
        if not target.verify_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(
            host=target.host,
            user=user or target.username,
            pwd=pwd if pwd is not None else target.password,
            port=target.port,
            sslContext=context,
            disableSslCertValidation=not target.verify_ssl,
        )
        # Stash verify_ssl in module dict (NOT on si — pyVmomi 8.x rejects
        # setattr on ManagedObject, see 踩坑 #32). Consumers in ops/* read via
        # get_verify_ssl(si).
        _SI_VERIFY_SSL[id(si)] = target.verify_ssl

        def _cleanup(_si: ServiceInstance = si) -> None:
            _SI_VERIFY_SSL.pop(id(_si), None)
            try:
                Disconnect(_si)
            except Exception:
                pass

        atexit.register(_cleanup)
        return si


def get_content(si: ServiceInstance) -> vim.ServiceInstanceContent:
    """Shortcut to get ServiceContent from a ServiceInstance."""
    return si.RetrieveContent()
