"""Regression tests — fixes from the 2026-06 code review.

Each test guards a verified bug:

- R1: _safe_error swallowed domain exceptions' teaching messages
- R2: _safe_error call sites passed a constant 'aiops' label instead of tool name
- R3: TTL entry was removed in `finally` — transient failure orphaned the VM
- R4: get_active_alarms collected propagated alarm states up to 4x (dedupe)
- R5: plan create_vm forwarded network_name=None, overriding the "VM Network" default
- R6: _find_triggered_alarm could Destroy() a container view twice
- R7: urlopen without timeout could hang the MCP stdio server forever
- R8: CLI commands dumped raw tracebacks for missing config / bad VM names
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[3]


# ── R1: domain exceptions pass through _safe_error with teaching text ──


def test_safe_error_passes_domain_exception_messages() -> None:
    from mcp_server.server import _safe_error
    from vmware_aiops.ops.cluster_mgmt import ClusterError, ClusterNotFoundError
    from vmware_aiops.ops.guest_ops import GuestOpsError
    from vmware_aiops.ops.vm_lifecycle import TaskFailedError, VMNotFoundError

    msg = "VM 'web-99' not found. Run vm_list to see available VMs."
    assert msg in _safe_error(VMNotFoundError(msg), "vm_power_on")

    for exc_type in (GuestOpsError, TaskFailedError, ClusterNotFoundError, ClusterError):
        teaching = f"{exc_type.__name__}: teaching message with fix hint"
        assert "teaching message with fix hint" in _safe_error(exc_type(teaching), "tool")

    assert "took too long" in _safe_error(TimeoutError("took too long"), "tool")


def test_safe_error_passes_connection_error_through() -> None:
    # issue #24: a dropped connection must surface its teaching hint through
    # MCP, matching the CLI path (which catches OSError). Before the fix it
    # was masked to a generic "operation failed".
    from mcp_server.server import _safe_error

    hint = "Connection to vcenter-prod dropped. Run 'vmware-aiops doctor'."
    out = _safe_error(ConnectionError(hint), "vm_power_on")
    assert hint in out
    assert "operation failed" not in out


def test_safe_error_still_masks_unknown_exceptions() -> None:
    from mcp_server.server import _safe_error

    out = _safe_error(RuntimeError("internal host:port leak"), "tool")
    assert "host:port" not in out
    assert "operation failed" in out


# ── R2: _safe_error call sites pass the actual tool name ──


def test_safe_error_call_sites_use_enclosing_tool_name() -> None:
    src = (_REPO / "mcp_server" / "server.py").read_text()
    tree = ast.parse(src)
    checked = 0
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if func.name == "_safe_error":
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_safe_error"
            ):
                label = node.args[1]
                assert isinstance(label, ast.Constant), f"{func.name}: non-constant label"
                assert label.value == func.name, (
                    f"{func.name}: _safe_error label is {label.value!r}, "
                    f"expected the tool name {func.name!r}"
                )
                checked += 1
    assert checked > 30, f"expected to verify many call sites, found {checked}"


# ── R3: TTL entry survives a transient deletion failure ──


def _ttl_entry(vm_name: str = "ttl-vm"):
    from vmware_aiops.ops.ttl import TTLEntry

    return TTLEntry(vm_name=vm_name, expires_at="2026-01-01T00:00:00+00:00", target=None)


def test_ttl_entry_kept_on_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from vmware_aiops.scanner import scheduler

    removed: list[str] = []
    monkeypatch.setattr(scheduler, "get_expired_entries", lambda: [_ttl_entry()])
    monkeypatch.setattr(scheduler, "remove_entry", removed.append)
    monkeypatch.setattr(
        scheduler, "delete_vm",
        lambda si, name: (_ for _ in ()).throw(RuntimeError("vCenter task timeout")),
    )

    scheduler._run_ttl_check(MagicMock())
    assert removed == [], "transient failure must NOT drop the TTL entry"


def test_ttl_entry_removed_when_vm_already_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    from vmware_aiops.ops.vm_lifecycle import VMNotFoundError
    from vmware_aiops.scanner import scheduler

    removed: list[str] = []
    monkeypatch.setattr(scheduler, "get_expired_entries", lambda: [_ttl_entry()])
    monkeypatch.setattr(scheduler, "remove_entry", removed.append)
    monkeypatch.setattr(
        scheduler, "delete_vm",
        lambda si, name: (_ for _ in ()).throw(VMNotFoundError("VM 'ttl-vm' not found")),
    )

    scheduler._run_ttl_check(MagicMock())
    assert removed == ["ttl-vm"], "VM already gone — stale entry must be dropped"


def test_ttl_entry_removed_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from vmware_aiops.scanner import scheduler

    removed: list[str] = []
    monkeypatch.setattr(scheduler, "get_expired_entries", lambda: [_ttl_entry()])
    monkeypatch.setattr(scheduler, "remove_entry", removed.append)
    monkeypatch.setattr(scheduler, "delete_vm", lambda si, name: f"VM '{name}' deleted")

    scheduler._run_ttl_check(MagicMock())
    assert removed == ["ttl-vm"]


# ── R4: get_active_alarms returns each triggered alarm exactly once ──


class _FakeHost:
    """Entity carrying the triggered alarm (also visible on ancestors)."""

    def __init__(self, name: str, alarm_states: list) -> None:
        self.name = name
        self.triggeredAlarmState = alarm_states


class _FakeContainer:
    def __init__(self, view: list) -> None:
        self.view = view
        self.destroy_count = 0

    def Destroy(self) -> None:  # noqa: N802 — pyVmomi API name
        self.destroy_count += 1


def test_get_active_alarms_no_duplicates_from_propagation() -> None:
    from vmware_aiops.ops.health import get_active_alarms

    alarm_state = SimpleNamespace(
        overallStatus="red",
        alarm=SimpleNamespace(info=SimpleNamespace(name="Host CPU usage")),
        entity=None,  # set below
        time="2026-06-11 00:00:00",
        acknowledged=False,
    )
    host = _FakeHost("esxi-1", [alarm_state])
    alarm_state.entity = host

    # The same alarm state propagates to rootFolder AND every container view.
    root = SimpleNamespace(triggeredAlarmState=[alarm_state])
    viewmgr = MagicMock()
    viewmgr.CreateContainerView.side_effect = lambda *a, **k: _FakeContainer([host])
    content = SimpleNamespace(rootFolder=root, viewManager=viewmgr)
    si = MagicMock()
    si.RetrieveContent.return_value = content

    alarms = get_active_alarms(si)

    assert len(alarms) == 1, f"propagated alarm must be deduplicated, got {len(alarms)}"
    assert alarms[0]["alarm_name"] == "Host CPU usage"
    assert alarms[0]["entity_name"] == "esxi-1"
    assert alarms[0]["severity"] == "critical"


# ── R5: plan create_vm drops None params so create_vm defaults apply ──


def test_plan_create_vm_drops_none_optional_params(monkeypatch: pytest.MonkeyPatch) -> None:
    from vmware_aiops.ops import plan_executor, vm_lifecycle

    captured: dict = {}

    def _fake_create_vm(si, vm_name, **kwargs):
        captured["vm_name"] = vm_name
        captured["kwargs"] = kwargs
        return f"VM '{vm_name}' created"

    monkeypatch.setattr(vm_lifecycle, "create_vm", _fake_create_vm)

    # network_name omitted entirely + explicit None datastore: both must be dropped
    plan_executor._dispatch(
        None, "create_vm",
        {"vm_name": "web-01", "cpu": 4, "datastore_name": None},
    )
    assert captured["vm_name"] == "web-01"
    assert captured["kwargs"]["cpu"] == 4
    assert "network_name" not in captured["kwargs"], (
        "None network_name must be dropped so create_vm's 'VM Network' default applies"
    )
    assert "datastore_name" not in captured["kwargs"]

    # explicit values still pass through
    plan_executor._dispatch(
        None, "create_vm",
        {"vm_name": "web-02", "network_name": "prod-net"},
    )
    assert captured["kwargs"]["network_name"] == "prod-net"


# ── R6: _find_triggered_alarm destroys each container view exactly once ──


class _NoAlarmEntity:
    """Matches by name but has no triggeredAlarmState attribute."""

    def __init__(self, name: str) -> None:
        self.name = name


def test_find_triggered_alarm_destroys_container_exactly_once() -> None:
    from vmware_aiops.ops.alarm_mgmt import _find_triggered_alarm

    containers: list[_FakeContainer] = []

    def _make_view(*args, **kwargs) -> _FakeContainer:
        # Entity matches the searched name but lacks triggeredAlarmState —
        # the old code Destroy()ed once before `continue` and again after the loop.
        container = _FakeContainer([_NoAlarmEntity("vm-1")])
        containers.append(container)
        return container

    viewmgr = MagicMock()
    viewmgr.CreateContainerView.side_effect = _make_view
    content = SimpleNamespace(rootFolder=object(), viewManager=viewmgr)
    si = MagicMock()
    si.RetrieveContent.return_value = content

    with pytest.raises(ValueError, match="not found"):
        _find_triggered_alarm(si, "vm-1", "Some Alarm")

    assert containers, "expected container views to be created"
    for container in containers:
        assert container.destroy_count == 1, (
            f"container view destroyed {container.destroy_count}x, expected exactly 1"
        )


# ── R7: every urlopen call passes a timeout ──


@pytest.mark.parametrize(
    "rel_path",
    [
        "vmware_aiops/ops/guest_ops.py",
        "vmware_aiops/ops/vm_deploy.py",
    ],
)
def test_urlopen_calls_have_timeout(rel_path: str) -> None:
    src = (_REPO / rel_path).read_text()
    tree = ast.parse(src)
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "urlopen":
            continue
        found += 1
        kw_names = {kw.arg for kw in node.keywords}
        assert "timeout" in kw_names, (
            f"{rel_path}:{node.lineno}: urlopen without timeout can hang the MCP server"
        )
    assert found > 0, f"expected urlopen calls in {rel_path}"


# ── R8: CLI prints one-line teaching error instead of traceback ──


def test_cli_missing_config_prints_one_line_error(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from vmware_aiops.cli import app

    missing = tmp_path / "no-such-config.yaml"
    result = CliRunner().invoke(
        app, ["vm", "power-on", "web-01", "--config", str(missing)]
    )

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "Error:" in result.output
    assert "Config file not found" in result.output


def test_cli_domain_exception_prints_teaching_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from vmware_aiops.cli import _common, app
    from vmware_aiops.ops.vm_lifecycle import VMNotFoundError

    def _fake_get_connection(target, config_path=None):
        raise VMNotFoundError("VM 'web-99' not found. Did you mean 'web-09'?")

    monkeypatch.setattr(_common, "_get_connection", _fake_get_connection)
    # vm.py imports _get_connection by name at module import — patch there too.
    from vmware_aiops.cli import vm as vm_module

    monkeypatch.setattr(vm_module, "_get_connection", _fake_get_connection)

    result = CliRunner().invoke(app, ["vm", "power-on", "web-99"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "web-99" in result.output
