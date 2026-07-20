"""Read-only mode must remove write tools from the real FastMCP registry.

Regression source: VMware-AIops issue #31 (juanpf-ha). An operator driving the
family with a local Llama 3.3 70B had to hand-write the prompt instruction
"work exclusively in read-only mode and never modify alerts, definitions,
reports or configuration", because read-only was only ever a documented
intent. A weak model can ignore a prompt; it cannot call a tool that is not in
list_tools().

vmware_policy/tests/test_readonly.py pins the gate's *semantics* against a
stand-in registry. This file pins the other half: that the real FastMCP API the
gate reaches for still behaves as assumed, and that this skill's actual tool
inventory splits the way its docs claim.
"""

import asyncio
import importlib
import sys

import pytest

#: Every tool whose docstring starts with ``[WRITE]``.
WRITE_TOOLS = {
    "acknowledge_vcenter_alarm",
    "add_host_vmk",
    "attach_iso_to_vm",
    "batch_clone_vms",
    "batch_deploy_from_spec",
    "batch_linked_clone_vms",
    "cluster_add_host",
    "create_dvs_portgroup",
    "cluster_configure",
    "cluster_create",
    "cluster_delete",
    "cluster_remove_host",
    "convert_vm_to_template",
    "deploy_linked_clone",
    "deploy_vm_from_ova",
    "deploy_vm_from_template",
    "remove_host_vmk",
    "reset_vcenter_alarm",
    "vm_apply_plan",
    "vm_cancel_ttl",
    "vm_clean_slate",
    "vm_clone",
    "vm_create",
    "vm_create_plan",
    "vm_create_snapshot",
    "vm_delete",
    "vm_delete_snapshot",
    "vm_guest_exec",
    "vm_guest_exec_output",
    "vm_guest_provision",
    "vm_guest_upload",
    "vm_migrate",
    "vm_power_off",
    "vm_power_on",
    "vm_reconfigure",
    "vm_revert_snapshot",
    "vm_rollback_plan",
    "vm_set_ttl",
}

#: Marked ``[READ]`` — read-only against vCenter — but on the gate's FORCE_WRITE
#: list: it writes to an operator-supplied local_path and takes guest
#: credentials. A locked-down deployment opts into that explicitly.
FORCE_WRITE_TOOLS = {"vm_guest_download"}

WITHHELD = WRITE_TOOLS | FORCE_WRITE_TOOLS


def _load_server(monkeypatch, read_only: str | None):
    """Import vmware_aiops.mcp_server.server fresh under the given read-only env."""
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.delenv("VMWARE_AIOPS_READ_ONLY", raising=False)
    if read_only is not None:
        monkeypatch.setenv("VMWARE_READ_ONLY", read_only)

    for name in [m for m in sys.modules if m.startswith("vmware_aiops.mcp_server")]:
        del sys.modules[name]
    return importlib.import_module("vmware_aiops.mcp_server.server")


def _tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


@pytest.fixture(autouse=True)
def _restore_modules():
    """Leave sys.modules as we found it so other test files import normally."""
    yield
    for name in [m for m in sys.modules if m.startswith("vmware_aiops.mcp_server")]:
        del sys.modules[name]


def test_default_mode_exposes_write_tools(monkeypatch):
    """Baseline: without the switch every tool is present."""
    server = _load_server(monkeypatch, None)
    names = _tool_names(server)
    assert WITHHELD <= names
    assert server.WITHHELD_WRITE_TOOLS == []


def test_read_only_removes_every_write_tool(monkeypatch):
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    assert not (WITHHELD & names), f"write tools survived: {WITHHELD & names}"


def test_read_only_keeps_read_tools(monkeypatch):
    """The gate must not be a blunt instrument — reads still work."""
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    for tool in (
        "list_vcenter_alarms",
        "cluster_info",
        "vm_list_snapshots",
        "browse_datastore",
    ):
        assert tool in names


def test_withheld_list_is_reported(monkeypatch):
    """Startup must be able to tell the operator what was withheld."""
    server = _load_server(monkeypatch, "true")
    assert set(server.WITHHELD_WRITE_TOOLS) == WITHHELD


def test_guest_download_is_withheld_despite_read_marker(monkeypatch):
    """FORCE_WRITE outranks the [READ] docstring marker.

    vm_guest_download does not modify vCenter, but it writes an
    operator-supplied local path and accepts guest credentials.
    """
    server = _load_server(monkeypatch, "true")
    assert "vm_guest_download" not in _tool_names(server)
    assert "vm_guest_download" in server.WITHHELD_WRITE_TOOLS


def test_every_surviving_tool_is_marked_read(monkeypatch):
    """End-to-end contract against the live registry."""
    server = _load_server(monkeypatch, "true")
    for tool in asyncio.run(server.mcp.list_tools()):
        assert (tool.description or "").lstrip().startswith("[READ]"), tool.name


def test_skill_env_var_also_works(monkeypatch):
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.setenv("VMWARE_AIOPS_READ_ONLY", "true")
    for name in [m for m in sys.modules if m.startswith("vmware_aiops.mcp_server")]:
        del sys.modules[name]
    server = importlib.import_module("vmware_aiops.mcp_server.server")
    assert not (WITHHELD & _tool_names(server))


def test_fastmcp_registry_api_still_present(monkeypatch):
    """The gate reaches into _tool_manager.list_tools(); pin that it exists.

    If an mcp upgrade moves this, we want a red test here rather than a gate
    that silently stops removing anything.
    """
    server = _load_server(monkeypatch, None)
    assert callable(getattr(server.mcp, "remove_tool", None))
    assert callable(getattr(server.mcp._tool_manager, "list_tools", None))
    assert server.mcp._tool_manager.list_tools()
