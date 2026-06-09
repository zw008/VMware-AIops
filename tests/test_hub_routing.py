"""Component 6 routing tests for vmware-aiops ConnectionManager.connect().

Exercises the per-role routing path without touching pyVmomi, 1Password, the
MCP request context, or a real vCenter: _create_connection is replaced with a
fake that records the creds it was handed, and the uaa_hub_routing entry points
are monkeypatched. Mirrors the veeam/a10 resolver tests; vmware fronts the PROD
vCenter (backend `vcenter-prod`), syseng-only. aiops is write-capable, so the
fail-closed guarantee matters most here.
"""
import pytest

# Installed on the hub, not a PyPI dep -> CI without it skips (module import-guards it).
uaa_hub_routing = pytest.importorskip("uaa_hub_routing")

from vmware_aiops import connection as conn_mod
from vmware_aiops.config import AppConfig, TargetConfig


class _Sess:
    currentSession = object()


class _Content:
    sessionManager = _Sess()


class FakeSI:
    """Fake ServiceInstance: records creds, satisfies the liveness probe."""
    def __init__(self, user, pwd):
        self.user = user
        self.pwd = pwd
        self.content = _Content()


@pytest.fixture
def cm(monkeypatch):
    target = TargetConfig(name="prod", host="vc.example", username="startup-user", verify_ssl=False)
    cfg = AppConfig(targets=(target,))

    def fake_create(t, *, user=None, pwd=None):
        return FakeSI(user or t.username, pwd)

    monkeypatch.setattr(conn_mod.ConnectionManager, "_create_connection", staticmethod(fake_create))
    return conn_mod.ConnectionManager(cfg)


def test_no_routing_signal_uses_startup_target(cm, monkeypatch):
    monkeypatch.setattr(uaa_hub_routing, "routing_item", lambda *a, **k: None)
    si = cm.connect()
    assert si.user == "startup-user"   # startup config username
    assert si.pwd is None              # routed path not taken


def test_routed_uses_per_role_creds(cm, monkeypatch):
    monkeypatch.setattr(uaa_hub_routing, "routing_item", lambda *a, **k: "MCP - syseng_elevated - vcenter-prod")
    monkeypatch.setattr(uaa_hub_routing, "resolve_fields",
                        lambda title, **k: {"username": "svc-elev", "password": "elev-pw"})
    si = cm.connect()
    assert si.user == "svc-elev"       # routed creds
    assert si.pwd == "elev-pw"


def test_routed_caches_per_account(cm, monkeypatch):
    monkeypatch.setattr(uaa_hub_routing, "routing_item", lambda *a, **k: "MCP - syseng_elevated - vcenter-prod")
    calls = {"n": 0}

    def resolve(title, **k):
        calls["n"] += 1
        return {"username": "u", "password": "p"}

    monkeypatch.setattr(uaa_hub_routing, "resolve_fields", resolve)
    a = cm.connect()
    b = cm.connect()
    assert a is b              # cached per (target, account)
    assert calls["n"] == 1     # resolved once; second call hit the live cache


def test_distinct_accounts_get_distinct_connections(cm, monkeypatch):
    titles = iter(["MCP - syseng_elevated - vcenter-prod", "MCP - syseng_readonly - vcenter-prod"])
    monkeypatch.setattr(uaa_hub_routing, "routing_item", lambda *a, **k: next(titles))
    monkeypatch.setattr(uaa_hub_routing, "resolve_fields",
                        lambda title, **k: {"username": title, "password": "p"})
    a = cm.connect()
    b = cm.connect()
    assert a is not b
    assert {a.user, b.user} == {
        "MCP - syseng_elevated - vcenter-prod", "MCP - syseng_readonly - vcenter-prod"
    }


def test_routed_missing_field_fails_closed(cm, monkeypatch):
    monkeypatch.setattr(uaa_hub_routing, "routing_item", lambda *a, **k: "MCP - syseng_elevated - vcenter-prod")
    monkeypatch.setattr(uaa_hub_routing, "resolve_fields",
                        lambda title, **k: {"username": "u"})   # password missing
    with pytest.raises(uaa_hub_routing.RoutingError):
        cm.connect()


def test_routing_error_propagates_denies(cm, monkeypatch):
    def boom(*a, **k):
        raise uaa_hub_routing.RoutingError("malformed X-Hub-Roles")
    monkeypatch.setattr(uaa_hub_routing, "routing_item", boom)
    with pytest.raises(uaa_hub_routing.RoutingError):
        cm.connect()
