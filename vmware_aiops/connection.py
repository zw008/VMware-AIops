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
        """Connect to a target by name, or the default target."""
        target = (
            self._config.get_target(target_name)
            if target_name
            else self._config.default_target
        )

        if target.name in self._connections:
            si = self._connections[target.name]
            try:
                # Test if session is still alive
                _ = si.content.sessionManager.currentSession
                return si
            except (vmodl.fault.NotAuthenticated, Exception):
                del self._connections[target.name]

        si = self._create_connection(target)
        self._connections[target.name] = si
        return si

    def disconnect(self, target_name: str) -> None:
        """Disconnect from a specific target."""
        if target_name in self._connections:
            from pyVmomi import connect as pyvmomi_connect

            pyvmomi_connect.Disconnect(self._connections[target_name])
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
    def _create_connection(target: TargetConfig) -> ServiceInstance:
        """Create a new pyVmomi connection."""
        from pyVmomi import connect as pyvmomi_connect

        context = None
        if not target.verify_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        si = pyvmomi_connect.SmartConnect(
            host=target.host,
            user=target.username,
            pwd=target.password,
            port=target.port,
            sslContext=context,
        )
        atexit.register(pyvmomi_connect.Disconnect, si)
        return si


def get_content(si: ServiceInstance) -> vim.ServiceInstanceContent:
    """Shortcut to get ServiceContent from a ServiceInstance."""
    return si.RetrieveContent()
