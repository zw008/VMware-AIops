"""MCP server wrapping VMware AIops operations.

This module exposes VMware vCenter/ESXi VM lifecycle, deployment, cluster
management, guest operations, and datastore browsing tools via the Model
Context Protocol (MCP) using stdio transport.  It acts as a thin adapter
layer — each ``@mcp.tool()`` function simply delegates to the
corresponding function in the ``vmware_aiops`` package.

For read-only monitoring (inventory, alarms, events, VM info), use the
companion skill ``vmware-monitor``.  For storage management (iSCSI, vSAN),
use ``vmware-storage``.  For Tanzu Kubernetes, use ``vmware-vks``.

Tool categories
---------------
* **Read-only** (no side effects): browse_*, scan_*
* **Write / Deploy** (mutate state): vm_power_*, deploy_*, attach_*,
  batch_*, convert_*, cluster_*  — should be gated by the AI agent's
  confirmation flow.

Security considerations
-----------------------
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.
* **Destructive ops**: Deploy and batch operations create VMs and consume
  resources; confirmation is recommended before execution.
* **Prompt injection defense**: Datastore file names/paths are sanitized
  via ``_sanitize()`` to strip control characters.

Source: https://github.com/zw008/VMware-AIops
License: MIT
"""


import logging
import os
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from vmware_policy import sanitize, vmware_tool

from vmware_aiops.config import load_config
from vmware_aiops.connection import ConnectionManager
from vmware_aiops.ops import datastore_browser, vm_deploy
from vmware_aiops.ops.guest_ops import (
    GuestOpsError,
    guest_download,
    guest_exec,
    guest_exec_with_output,
    guest_provision,
    guest_upload,
)
from vmware_aiops.ops.plan_executor import apply_plan, rollback_plan
from vmware_aiops.ops.planner import create_plan, list_plans
from vmware_aiops.ops.alarm_mgmt import acknowledge_alarm, list_alarms, reset_alarm
from vmware_aiops.ops.cluster_mgmt import ClusterError, ClusterNotFoundError
from vmware_aiops.ops.vm_lifecycle import (
    TaskFailedError,
    VMNotFoundError,
    clone_vm,
    create_snapshot,
    delete_snapshot,
    delete_vm,
    list_snapshots,
    migrate_vm,
    power_off_vm,
    power_on_vm,
    revert_to_snapshot,
)

logger = logging.getLogger(__name__)


def _safe_error(exc: Exception, tool: str) -> str:
    """Return an agent-safe error string; log full detail server-side only.

    Raw exception text can carry vSphere response bodies, internal paths, or
    host:port pairs. Full traceback goes to the server log; the agent sees only
    a control-char-stripped, length-capped message. Intentional validation
    errors and domain exceptions carrying teaching messages (VMNotFoundError,
    GuestOpsError, TaskFailedError, ClusterNotFoundError, ClusterError,
    TimeoutError, ConnectionError) pass through sanitized — a dropped
    connection should surface its teaching hint, matching the CLE path
    (which catches OSError) rather than being masked as "operation failed".
    """
    logger.error("Tool %s failed", tool, exc_info=True)
    _passthrough = (
        ValueError,
        FileNotFoundError,
        KeyError,
        PermissionError,
        TimeoutError,
        ConnectionError,
        VMNotFoundError,
        GuestOpsError,
        TaskFailedError,
        ClusterNotFoundError,
        ClusterError,
    )
    if isinstance(exc, _passthrough):
        return sanitize(str(exc), 300)
    return f"{type(exc).__name__}: operation failed."


mcp = FastMCP(
    "vmware-aiops",
    instructions=(
        "VMware vCenter/ESXi VM lifecycle and deployment operations. "
        "Manage VM power state, deploy VMs (OVA/template/clone/batch), "
        "browse datastores, manage clusters, execute guest commands, "
        "and plan multi-step operations. "
        "For read-only monitoring (inventory/alarms/events/VM info), "
        "use vmware-monitor. For storage/iSCSI/vSAN, use vmware-storage. "
        "For Tanzu Kubernetes, use vmware-vks."
    ),
)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: Optional[ConnectionManager] = None


def _get_connection(target: Optional[str] = None) -> Any:
    """Return a pyVmomi ServiceInstance, lazily initialising the manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_AIOPS_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


# ---------------------------------------------------------------------------
# VM lifecycle tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_power_on(vm_name: str, target: Optional[str] = None) -> str:
    """[WRITE] Power on a virtual machine.

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    try:
        si = _get_connection(target)
        return power_on_vm(si, vm_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_power_on')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_power_off(
    vm_name: str,
    force: bool = False,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Power off a VM — graceful guest shutdown by default, hard power-off with force=True.

    Graceful mode calls VMware Tools guest shutdown and waits up to 120s; if Tools is not
    running or shutdown stalls, the response tells you to retry with force=True. An
    already-off VM returns success without change. Audited to ~/.vmware/audit.db.
    Use vm_power_on to start a VM; vm_delete requires the VM to be off first.

    Args:
        vm_name: Exact VM name as shown in vCenter inventory (case-sensitive).
        force: False (default) = graceful guest shutdown via VMware Tools;
            True = immediate hard power-off (risks guest filesystem damage).
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        Status string: shut down, force powered off, already off, or a Tools-unavailable hint.
    """
    try:
        si = _get_connection(target)
        return power_off_vm(si, vm_name, force=force)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_power_off')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def vm_clone(
    vm_name: str,
    new_name: str,
    to_host: Optional[str] = None,
    to_datastore: Optional[str] = None,
    power_on: bool = False,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Clone a VM. Without to_host/to_datastore the clone lands on the source's host+datastore.

    Args:
        vm_name: Source VM (or template) name.
        new_name: Name for the new clone.
        to_host: Target ESXi host name (default: source's host).
        to_datastore: Target datastore name (default: source's datastore).
        power_on: Power on the clone after creation.
        target: vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return clone_vm(
            si, vm_name, new_name,
            target_host=to_host,
            target_datastore=to_datastore,
            power_on=power_on,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_clone')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def vm_migrate(
    vm_name: str,
    to_host: str,
    to_datastore: Optional[str] = None,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Migrate (vMotion) a VM to another host, optionally with storage vMotion.

    If the target host has no access to the VM's current datastore, you MUST pass
    to_datastore — vCenter rejects cross-host vMotion without shared storage.

    Args:
        vm_name: VM to migrate.
        to_host: Target ESXi host name.
        to_datastore: Target datastore (required for cross-storage hosts).
        target: vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return migrate_vm(si, vm_name, to_host, target_datastore=to_datastore)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_migrate')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="critical")
def vm_delete(vm_name: str, target: Optional[str] = None) -> str:
    """[WRITE] Delete a VM (irreversible). VM must be powered off.

    Args:
        vm_name: VM to delete. Must be powered off.
        target: vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return delete_vm(si, vm_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_delete')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_create_snapshot(
    vm_name: str,
    snapshot_name: str,
    description: str = "",
    memory: bool = False,
    quiesce: bool = False,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Create a snapshot of a VM.

    Args:
        vm_name: VM to snapshot.
        snapshot_name: Snapshot name.
        description: Optional description.
        memory: Include memory state (heavier, allows resume).
        quiesce: Quiesce guest filesystem (requires running VMware Tools).
        target: vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return create_snapshot(
            si, vm_name, snapshot_name,
            description=description, memory=memory, quiesce=quiesce,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_create_snapshot')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def vm_revert_snapshot(
    vm_name: str,
    snapshot_name: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Revert a VM to a named snapshot (loses changes since snapshot).

    Args:
        vm_name: VM to revert.
        snapshot_name: Snapshot to revert to.
        target: vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return revert_to_snapshot(si, vm_name, snapshot_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_revert_snapshot')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def vm_delete_snapshot(
    vm_name: str,
    snapshot_name: str,
    remove_children: bool = False,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Permanently delete a named snapshot, consolidating its delta disk into the parent.

    Frees disk space and does NOT change the VM's current state (unlike vm_revert_snapshot,
    which discards changes since the snapshot). Works while the VM is powered on. Run
    vm_list_snapshots first for exact names — unknown names return the available list.
    Irreversible: confirm with the user before calling. Audited to ~/.vmware/audit.db.

    Args:
        vm_name: Exact name of the VM owning the snapshot.
        snapshot_name: Exact snapshot name from vm_list_snapshots output.
        remove_children: False (default) = children are kept and consolidated;
            True = delete the entire snapshot subtree below this one as well.
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        Status string confirming deletion, or a not-found message listing available snapshots.
    """
    try:
        si = _get_connection(target)
        return delete_snapshot(si, vm_name, snapshot_name, remove_children=remove_children)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_delete_snapshot')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def vm_list_snapshots(vm_name: str, target: Optional[str] = None) -> list[dict]:
    """[READ] List the full snapshot tree of a VM, including nested child snapshots.

    Read-only, no side effects. Call this before vm_revert_snapshot, vm_delete_snapshot,
    or deploy_linked_clone to get exact snapshot names. Returns an empty list when the
    VM has no snapshots.

    Args:
        vm_name: Exact VM name as shown in vCenter inventory.
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        One dict per snapshot: name, description, created (timestamp), state
        (poweredOn/poweredOff at snapshot time), level (0 = root, higher = nesting
        depth). No pagination — snapshot trees are small.
    """
    try:
        si = _get_connection(target)
        snaps = list_snapshots(si, vm_name)
        return [
            {k: v for k, v in s.items() if k != "snapshot_ref"}
            for s in snaps
        ]
    except Exception as e:
        return [{"error": _safe_error(e, 'vm_list_snapshots'), "hint": "Run 'vmware-aiops doctor' to verify connectivity."}]


# ---------------------------------------------------------------------------
# Datastore tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def browse_datastore(
    datastore_name: str,
    path: str = "",
    pattern: str = "*",
    target: Optional[str] = None,
) -> list[dict]:
    """[READ] Browse files in a vSphere datastore directory.

    Use this to discover OVA, ISO, VMDK, and other files on datastores
    before deploying VMs.

    Args:
        datastore_name: Name of the datastore to browse.
        path: Subdirectory path (empty string for root).
        pattern: Glob pattern to filter files (e.g. "*.ova", "*.iso", "*").
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return datastore_browser.browse_datastore(si, datastore_name, path=path, pattern=pattern)
    except Exception as e:
        return [{"error": _safe_error(e, 'browse_datastore'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def scan_datastore_images(target: Optional[str] = None) -> dict:
    """[READ] Scan all accessible datastores for deployable images (OVA/ISO/OVF/VMDK).

    Results are cached locally in ~/.vmware-aiops/image_registry.json for
    fast lookup via list_cached_images. Run this to refresh the cache.

    Args:
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return datastore_browser.update_registry(si)
    except Exception as e:
        return {"error": _safe_error(e, 'scan_datastore_images'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# Deploy tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def deploy_vm_from_ova(
    ova_path: str,
    vm_name: str,
    datastore_name: str,
    network_name: str = "VM Network",
    folder_path: Optional[str] = None,
    power_on: bool = False,
    snapshot_name: Optional[str] = None,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Create a new VM by importing a local .ova file (OVF parse + VMDK upload).

    Use for OVA appliance files on the local machine. For vSphere templates use
    deploy_vm_from_template; to copy an existing VM use vm_clone or deploy_linked_clone.
    Upload time scales with OVA size. Fails before creating anything if the datastore
    is not found. Audited to ~/.vmware/audit.db.

    Args:
        ova_path: Local filesystem path to the .ova file (must be readable by this server).
        vm_name: Name for the new VM; must not already exist.
        datastore_name: Target datastore name; discover with browse_datastore.
        network_name: Port group for the VM's NICs (default "VM Network").
        folder_path: vCenter VM folder path; omit to use the datacenter's root VM folder.
        power_on: True powers the VM on after import (default False).
        snapshot_name: If set, creates a baseline snapshot with this name after deploy.
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        Status string with the deployed VM name, or an error naming the missing resource.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.deploy_ova(
            si, ova_path=ova_path, vm_name=vm_name,
            datastore_name=datastore_name, network_name=network_name,
            folder_path=folder_path, power_on=power_on,
            snapshot_name=snapshot_name,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'deploy_vm_from_ova')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def deploy_vm_from_template(
    template_name: str,
    new_name: str,
    datastore_name: Optional[str] = None,
    cpu: Optional[int] = None,
    memory_mb: Optional[int] = None,
    power_on: bool = False,
    snapshot_name: Optional[str] = None,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Deploy a new VM by cloning from a vSphere template.

    Args:
        template_name: Name of the source vSphere template.
        new_name: Name for the new VM.
        datastore_name: Target datastore (uses template's datastore if omitted).
        cpu: Override CPU count (optional).
        memory_mb: Override memory in MB (optional).
        power_on: Power on after deployment.
        snapshot_name: Create a baseline snapshot with this name (optional).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.deploy_from_template(
            si, template_name=template_name, new_name=new_name,
            datastore_name=datastore_name, cpu=cpu, memory_mb=memory_mb,
            power_on=power_on, snapshot_name=snapshot_name,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'deploy_vm_from_template')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def deploy_linked_clone(
    source_vm_name: str,
    snapshot_name: str,
    new_name: str,
    cpu: Optional[int] = None,
    memory_mb: Optional[int] = None,
    power_on: bool = False,
    baseline_snapshot: Optional[str] = None,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Create a linked clone from a VM snapshot — near-instant, minimal disk usage.

    The clone shares the source's base disk and writes changes to a copy-on-write delta
    disk, so it depends on the source VM staying intact. Fastest provisioning method for
    test/dev fleets; use vm_clone or deploy_vm_from_template for fully independent copies.
    Requires the source VM to have the named snapshot — run vm_list_snapshots first;
    unknown names return the available list. Audited to ~/.vmware/audit.db.

    Args:
        source_vm_name: Exact name of the source VM (must have at least one snapshot).
        snapshot_name: Snapshot on the source to use as the clone base (from vm_list_snapshots).
        new_name: Name for the new linked clone; must not already exist.
        cpu: Override vCPU count; omit to keep the source's value.
        memory_mb: Override memory in MB; omit to keep the source's value.
        power_on: True powers the clone on after creation (default False).
        baseline_snapshot: If set, creates a snapshot with this name on the new clone.
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        Status string with the new clone name, or a snapshot/VM-not-found error.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.linked_clone(
            si, source_vm_name=source_vm_name, new_name=new_name,
            snapshot_name=snapshot_name, cpu=cpu, memory_mb=memory_mb,
            power_on=power_on, baseline_snapshot=baseline_snapshot,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'deploy_linked_clone')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def attach_iso_to_vm(
    vm_name: str,
    iso_ds_path: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Mount a datastore ISO into a VM's virtual CD-ROM drive.

    Reconfigures the existing CD-ROM (replacing any currently mounted ISO) or adds a
    new CD-ROM on the VM's IDE controller if none exists; fails with a clear message
    if the VM has no IDE controller. Works whether the VM is powered on or off — the
    device is set connected and start-connected. Find ISO files first with
    browse_datastore using pattern "*.iso". Audited to ~/.vmware/audit.db.

    Args:
        vm_name: Exact VM name as shown in vCenter inventory.
        iso_ds_path: Full datastore path in bracket format, e.g.
            "[datastore1] iso/ubuntu-22.04.iso" (datastore name in brackets, then
            the path relative to the datastore root).
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        Status string confirming attachment, or a VM-not-found / no-IDE-controller error.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.attach_iso(si, vm_name, iso_ds_path)
    except Exception as e:
        return f"Error: {_safe_error(e, 'attach_iso_to_vm')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def convert_vm_to_template(
    vm_name: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Convert a powered-off VM to a vSphere template.

    After conversion the VM cannot be powered on — it serves as a
    clone source for deploy_vm_from_template.

    Args:
        vm_name: Name of the VM to convert (must be powered off).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.convert_to_template(si, vm_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'convert_vm_to_template')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def batch_clone_vms(
    source_vm_name: str,
    vm_names: list[str],
    cpu: Optional[int] = None,
    memory_mb: Optional[int] = None,
    snapshot_name: Optional[str] = None,
    power_on: bool = False,
    target: Optional[str] = None,
) -> list[dict]:
    """[WRITE] Batch clone multiple VMs from a source VM (gold image).

    Each clone: full copy → optional reconfigure → optional snapshot → optional power on.

    Args:
        source_vm_name: Source VM to clone from.
        vm_names: List of names for the new VMs.
        cpu: Override CPU count for all clones (optional).
        memory_mb: Override memory for all clones (optional).
        snapshot_name: Create a baseline snapshot on each clone (optional).
        power_on: Power on each clone after creation.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.batch_clone(
            si, source_vm_name=source_vm_name, vm_names=vm_names,
            cpu=cpu, memory_mb=memory_mb,
            snapshot_name=snapshot_name, power_on=power_on,
        )
    except Exception as e:
        return [{"error": _safe_error(e, 'batch_clone_vms'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def batch_linked_clone_vms(
    source_vm_name: str,
    snapshot_name: str,
    vm_names: list[str],
    cpu: Optional[int] = None,
    memory_mb: Optional[int] = None,
    power_on: bool = False,
    baseline_snapshot: Optional[str] = None,
    target: Optional[str] = None,
) -> list[dict]:
    """[WRITE] Batch create linked clones from a VM snapshot (fastest batch provisioning).

    Each clone shares the source disk via copy-on-write.

    Args:
        source_vm_name: Source VM to clone from.
        snapshot_name: Snapshot to use as clone base.
        vm_names: List of names for the new linked clones.
        cpu: Override CPU count (optional).
        memory_mb: Override memory (optional).
        power_on: Power on each clone.
        baseline_snapshot: Create a new snapshot on each clone (optional).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.batch_linked_clone(
            si, source_vm_name=source_vm_name, snapshot_name=snapshot_name,
            vm_names=vm_names, cpu=cpu, memory_mb=memory_mb,
            power_on=power_on, baseline_snapshot=baseline_snapshot,
        )
    except Exception as e:
        return [{"error": _safe_error(e, 'batch_linked_clone_vms'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def batch_deploy_from_spec(
    spec_path: str,
    target: Optional[str] = None,
) -> list[dict]:
    """[WRITE] Deploy multiple VMs in one call from a declarative YAML spec file.

    Use for fleet provisioning (several VMs, shared defaults); for a single VM prefer
    deploy_vm_from_template, vm_clone, deploy_vm_from_ova, or deploy_linked_clone.
    The provisioning channel is chosen by spec keys: top-level "source" (full clone),
    "template", "linked_clone: {source, snapshot}", per-VM "ova", else empty-VM creation
    (optionally with "iso"). A "defaults" block sets cpu/memory_mb/disk_gb/network/
    datastore/snapshot/power_on, overridable per VM. VMs deploy sequentially; one VM's
    failure is recorded and the rest continue. Audited to ~/.vmware/audit.db.

    Args:
        spec_path: Local filesystem path to the deploy.yaml specification file.
        target: vCenter/ESXi target name from config.yaml; omit to use the default target.

    Returns:
        One dict per VM: name, status ("ok" or "error"), and messages with per-step results.
    """
    try:
        si = _get_connection(target)
        return vm_deploy.batch_deploy(si, spec_path)
    except Exception as e:
        return [{"error": _safe_error(e, 'batch_deploy_from_spec'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


# ---------------------------------------------------------------------------
# Cluster tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def cluster_create(
    name: str,
    datacenter: Optional[str] = None,
    ha: bool = False,
    drs: bool = False,
    drs_behavior: str = "fullyAutomated",
    target: Optional[str] = None,
) -> str:
    """[WRITE] Create a new empty cluster in a datacenter, optionally enabling HA and DRS.

    Fails with a clear error (no partial state) if a cluster with that name already
    exists or drs_behavior is invalid. After creation, add hosts with cluster_add_host;
    change HA/DRS later with cluster_configure; verify with cluster_info.
    Audited to ~/.vmware/audit.db.

    Args:
        name: Name for the new cluster; must be unique in the datacenter.
        datacenter: Datacenter name; omit to use the first datacenter on the target.
        ha: True enables vSphere HA (default False).
        drs: True enables DRS (default False).
        drs_behavior: "fullyAutomated" (default), "partiallyAutomated", or "manual".
            Only takes effect when drs=True.
        target: vCenter target name from config.yaml; omit to use the default target.

    Returns:
        Status string confirming creation and which features (HA/DRS) were enabled.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import create_cluster
        si = _get_connection(target)
        return create_cluster(
            si, cluster_name=name, datacenter_name=datacenter,
            ha_enabled=ha, drs_enabled=drs, drs_behavior=drs_behavior,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'cluster_create')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def cluster_delete(name: str, target: Optional[str] = None) -> str:
    """[WRITE] Delete an empty cluster (no hosts must remain).

    Args:
        name: Name of the cluster to delete.
        target: Optional vCenter target name from config.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import delete_cluster
        si = _get_connection(target)
        return delete_cluster(si, name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'cluster_delete')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def cluster_add_host(
    cluster_name: str,
    host_name: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Move an ESXi host that vCenter already manages into a cluster.

    The host must already be in vCenter inventory (standalone or in another cluster) —
    this tool does NOT register brand-new hosts and takes no host credentials; use the
    vCenter UI for first-time host registration. Idempotent: a host already in the
    cluster returns success without change. Maintenance mode is not required to join
    (it IS required by cluster_remove_host). Check membership with cluster_info.
    Audited to ~/.vmware/audit.db.

    Args:
        cluster_name: Existing destination cluster name (create with cluster_create).
        host_name: Host name exactly as shown in vCenter inventory, typically the
            FQDN, e.g. "esxi-01.lab.local".
        target: vCenter target name from config.yaml; omit to use the default target.

    Returns:
        Status string: moved, already-in-cluster, or host/cluster-not-found error.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import add_host_to_cluster
        si = _get_connection(target)
        return add_host_to_cluster(si, cluster_name=cluster_name, host_name=host_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'cluster_add_host')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def cluster_remove_host(
    cluster_name: str,
    host_name: str,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Remove a host from a cluster (host must be in maintenance mode).

    Args:
        cluster_name: Cluster to remove the host from.
        host_name: ESXi host name to remove.
        target: Optional vCenter target name from config.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import remove_host_from_cluster
        si = _get_connection(target)
        return remove_host_from_cluster(si, cluster_name=cluster_name, host_name=host_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'cluster_remove_host')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def cluster_configure(
    name: str,
    ha: Optional[bool] = None,
    drs: Optional[bool] = None,
    drs_behavior: Optional[str] = None,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Reconfigure cluster HA/DRS settings.

    Args:
        name: Cluster name.
        ha: Enable (True) or disable (False) HA, or None to leave unchanged.
        drs: Enable (True) or disable (False) DRS, or None to leave unchanged.
        drs_behavior: DRS behavior: "fullyAutomated", "partiallyAutomated", or "manual".
        target: Optional vCenter target name from config.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import configure_cluster
        si = _get_connection(target)
        return configure_cluster(
            si, cluster_name=name,
            ha_enabled=ha, drs_enabled=drs, drs_behavior=drs_behavior,
        )
    except Exception as e:
        return f"Error: {_safe_error(e, 'cluster_configure')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def cluster_info(name: str, target: Optional[str] = None) -> dict:
    """[READ] Get detailed cluster information: member hosts, HA/DRS config, resource capacity.

    Read-only, no side effects. Use before cluster_add_host / cluster_remove_host (shows
    membership and per-host maintenance mode) and to verify cluster_configure changes.

    Args:
        name: Exact cluster name.
        target: vCenter target name from config.yaml; omit to use the default target.

    Returns:
        Dict with name, host_count, hosts (each: name, connection_state, power_state,
        maintenance_mode), ha_enabled, ha_admission_control, drs_enabled, drs_behavior,
        total/effective CPU (MHz) and memory (GB). Errors return a dict with "error" + hint.
    """
    try:
        from vmware_aiops.ops.cluster_mgmt import get_cluster_info
        si = _get_connection(target)
        return get_cluster_info(si, name)
    except Exception as e:
        return {"error": _safe_error(e, 'cluster_info'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# TTL & Clean Slate
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_set_ttl(
    vm_name: str,
    minutes: int,
    target: Optional[str] = None,
) -> str:
    """[WRITE] Set a Time-To-Live (TTL) for a VM. The daemon auto-deletes it when expired.

    The scheduler daemon must be running (`vmware-aiops daemon start`) for
    automatic deletion. TTLs are persisted in ~/.vmware-aiops/ttl.json.

    Args:
        vm_name: Name of the VM to auto-delete.
        minutes: Minutes until deletion (minimum 1).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        from vmware_aiops.ops.ttl import set_ttl as _set_ttl
        return _set_ttl(vm_name, minutes, target=target)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_set_ttl')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_cancel_ttl(vm_name: str) -> str:
    """[WRITE] Cancel an existing TTL for a VM (prevents auto-deletion).

    Args:
        vm_name: Name of the VM whose TTL should be cancelled.
    """
    try:
        from vmware_aiops.ops.ttl import cancel_ttl as _cancel_ttl
        return _cancel_ttl(vm_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_cancel_ttl')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def vm_list_ttl() -> list[dict]:
    """[READ] List all VMs with TTLs registered, including expiry time and status.

    Returns a list of TTL entries with remaining_minutes and expired flag.
    """
    try:
        from vmware_aiops.ops.ttl import list_ttl as _list_ttl
        return _list_ttl()
    except Exception as e:
        return [{"error": _safe_error(e, 'vm_list_ttl'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def vm_clean_slate(
    vm_name: str,
    snapshot_name: str = "baseline",
    target: Optional[str] = None,
) -> str:
    """[WRITE] Revert a VM to its baseline snapshot (Clean Slate).

    Powers off the VM first if it is running, then reverts to the named
    snapshot. Use this to reset a lab/dev VM to a clean starting state
    after a task completes.

    Args:
        vm_name: Name of the VM to revert.
        snapshot_name: Snapshot name to revert to (default: "baseline").
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        from vmware_aiops.ops.vm_lifecycle import clean_slate
        si = _get_connection(target)
        return clean_slate(si, vm_name, snapshot_name=snapshot_name)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_clean_slate')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


# ---------------------------------------------------------------------------
# Guest Operations tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium", sensitive_params=['password'])
def vm_guest_exec(
    vm_name: str,
    command: str,
    arguments: str = "",
    username: str = "root",
    password: str = "",
    working_directory: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Execute a command inside a VM via VMware Tools.

    Requires VMware Tools running in the guest OS.
    Returns exit_code, stdout, stderr, and timed_out flag.

    Note: VMware Guest Ops API does not capture stdout/stderr directly.
    To capture output, redirect to a file and use vm_guest_download:
        command="/bin/bash", arguments="-c 'ls -la /tmp > /tmp/output.txt'"
        Then download /tmp/output.txt.

    Args:
        vm_name: Target VM name.
        command: Full path to program (e.g. "/bin/bash", "C:\\Windows\\System32\\cmd.exe").
        arguments: Command arguments (e.g. "-c 'whoami'").
        username: Guest OS username (default "root").
        password: Guest OS password.
        working_directory: Working directory inside guest (optional).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return guest_exec(
            si, vm_name, command, username, password,
            arguments=arguments,
            working_directory=working_directory,
        )
    except Exception as e:
        return {"error": _safe_error(e, 'vm_guest_exec'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium", sensitive_params=['password'])
def vm_guest_exec_output(
    vm_name: str,
    command: str,
    username: str = "root",
    password: str = "",
    timeout: int = 300,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Execute a shell command inside a VM and capture stdout + stderr.

    Automatically detects guest OS (Linux/Windows) and selects the correct
    shell. Output is captured by redirecting to a temp file, downloading it,
    then cleaning up — no manual redirection needed.

    Returns exit_code, stdout, stderr, timed_out, os_family.

    Args:
        vm_name: Target VM name.
        command: Shell command (e.g. "df -h", "ls /etc", "ipconfig").
        username: Guest OS username (default "root").
        password: Guest OS password.
        timeout: Max wait seconds (default 300).
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return guest_exec_with_output(si, vm_name, command, username, password, timeout=timeout)
    except Exception as e:
        return {"error": _safe_error(e, 'vm_guest_exec_output'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium", sensitive_params=['password'])
def vm_guest_upload(
    vm_name: str,
    local_path: str,
    guest_path: str,
    username: str = "root",
    password: str = "",
    target: Optional[str] = None,
) -> str:
    """[WRITE] Upload a file from local machine to a VM via VMware Tools.

    Requires VMware Tools running in the guest OS.

    Args:
        vm_name: Target VM name.
        local_path: Local file path to upload.
        guest_path: Destination path inside the guest.
        username: Guest OS username (default "root").
        password: Guest OS password.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return guest_upload(si, vm_name, local_path, guest_path, username, password)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_guest_upload')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="medium", sensitive_params=['password'])
def vm_guest_download(
    vm_name: str,
    guest_path: str,
    local_path: str,
    username: str = "root",
    password: str = "",
    target: Optional[str] = None,
) -> str:
    """[READ] Download a file from a VM to local machine via VMware Tools.

    Requires VMware Tools running in the guest OS.

    Args:
        vm_name: Target VM name.
        guest_path: File path inside the guest to download.
        local_path: Local destination path.
        username: Guest OS username (default "root").
        password: Guest OS password.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return guest_download(si, vm_name, guest_path, local_path, username, password)
    except Exception as e:
        return f"Error: {_safe_error(e, 'vm_guest_download')} Run 'vmware-aiops doctor' to verify connectivity and credentials."


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium", sensitive_params=['password'])
def vm_guest_provision(
    vm_name: str,
    username: str,
    password: str,
    steps: list[dict],
    timeout: int = 300,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Provision a VM by running a sequence of guest operations (exec / upload / service).

    Combines key injection, software installation, and service startup into a
    single call. Steps execute in order; stops on first failure.

    Step types:
      - exec:    {"type": "exec", "command": "apt-get install -y nginx"}
      - upload:  {"type": "upload", "local_path": "/tmp/id_rsa.pub", "guest_path": "/root/.ssh/authorized_keys"}
      - service: {"type": "service", "name": "nginx", "action": "start"}

    Args:
        vm_name: Target VM name.
        username: Guest OS username.
        password: Guest OS password.
        steps: Ordered list of step dicts.
        timeout: Per-step timeout in seconds (default 300).
        target: Optional vCenter/ESXi target name from config.

    Returns:
        dict with success, completed_steps, total_steps, results, error.

    Example:
        steps = [
            {"type": "upload", "local_path": "~/.ssh/id_rsa.pub", "guest_path": "/root/.ssh/authorized_keys"},
            {"type": "exec", "command": "chmod 600 /root/.ssh/authorized_keys"},
            {"type": "exec", "command": "apt-get install -y nginx"},
            {"type": "service", "name": "nginx", "action": "enable"},
            {"type": "service", "name": "nginx", "action": "start"},
        ]
    """
    try:
        si = _get_connection(target)
        return guest_provision(si, vm_name, username, password, steps, timeout=timeout)
    except Exception as e:
        return {"error": _safe_error(e, 'vm_guest_provision'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# Plan → Apply tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_create_plan(
    operations: list[dict[str, Any]],
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create an execution plan for multi-step VM operations.

    Auto-triggered when operations involve 2+ steps or 2+ VMs.
    Validates actions, checks target existence in vSphere, and generates
    a plan with rollback info for each step.

    Each operation is a dict with "action" key plus action-specific params.
    Allowed actions: power_on, power_off, reset, suspend, create_vm,
    delete_vm, reconfigure, create_snapshot, delete_snapshot,
    revert_snapshot, clone, migrate, deploy_ova, deploy_template,
    linked_clone, attach_iso, convert_to_template.

    Example:
        operations=[
            {"action": "power_off", "vm_name": "test-1"},
            {"action": "revert_snapshot", "vm_name": "test-1", "snapshot_name": "baseline"},
            {"action": "power_on", "vm_name": "test-1"}
        ]

    Returns plan dict with plan_id, steps, summary (vms_affected,
    irreversible_steps, rollback_available). Show to user for confirmation
    before calling vm_apply_plan.

    Args:
        operations: List of operation dicts, each with "action" + params.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return create_plan(si, operations, target=target)
    except Exception as e:
        return {"error": _safe_error(e, 'vm_create_plan'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_apply_plan(plan_id: str, target: Optional[str] = None) -> dict:
    """[WRITE] Execute a previously created plan step by step.

    Steps run sequentially. On failure: stops immediately, keeps the plan
    file with per-step results, and returns rollback_available flag.
    On success: deletes the plan file.

    If a step fails and rollback_available is true, ask the user whether
    to rollback, then call vm_rollback_plan if confirmed.

    Args:
        plan_id: The plan ID returned by vm_create_plan.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        result = apply_plan(si, plan_id)

        # If failed with rollback available, hint to the agent
        if result.get("status") == "failed" and result.get("rollback_available"):
            result["hint"] = (
                "Plan failed. Ask the user: 'Do you want to rollback the "
                "already-executed steps?' If yes, call vm_rollback_plan."
            )
        return result
    except Exception as e:
        return {"error": _safe_error(e, 'vm_apply_plan'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def vm_rollback_plan(plan_id: str, target: Optional[str] = None) -> dict:
    """[WRITE] Rollback executed steps of a failed plan in reverse order.

    Only call this after vm_apply_plan returns status='failed' and the
    user confirms they want to rollback. Irreversible steps (delete_vm,
    revert_snapshot, etc.) are skipped with a warning.

    Args:
        plan_id: The plan ID of the failed plan.
        target: Optional vCenter/ESXi target name from config.
    """
    try:
        si = _get_connection(target)
        return rollback_plan(si, plan_id)
    except Exception as e:
        return {"error": _safe_error(e, 'vm_rollback_plan'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def vm_list_plans() -> list[dict]:
    """[READ] List all pending/failed plans.

    Returns plan summaries (plan_id, created_at, status, steps count,
    VMs affected). Stale plans (>24h) are auto-cleaned.
    """
    try:
        return list_plans()
    except Exception as e:
        return [{"error": _safe_error(e, 'vm_list_plans'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


# ---------------------------------------------------------------------------
# Alarm management tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_vcenter_alarms(
    target: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """[READ] List active/triggered alarms across the vCenter inventory.

    Returns alarms with severity (critical/warning/info), entity name and type,
    alarm name, acknowledged flag, and trigger time.

    Args:
        target: Optional vCenter target name from config. Uses default if omitted.
        limit: Max number of alarms to return (None = all). Use when many alarms are active.
    """
    try:
        si = _get_connection(target)
        results = list_alarms(si)
        if limit is not None:
            results = results[:limit]
        return results
    except Exception as e:
        return [{"error": _safe_error(e, 'list_vcenter_alarms'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}]


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def acknowledge_vcenter_alarm(
    entity_name: str,
    alarm_name: str,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Acknowledge a triggered vCenter alarm — marks it as seen WITHOUT clearing it.

    The alarm stays in the active list with acknowledged=true until its condition clears
    or it is reset. To remove the alarm entirely after fixing the root cause, use
    reset_vcenter_alarm instead. Get exact entity_name and alarm_name values from
    list_vcenter_alarms first; an unknown pair returns a not-found error.
    Audited to ~/.vmware/audit.db.

    Args:
        entity_name: Name of the VM, ESXi host, or cluster the alarm fired on
            (from list_vcenter_alarms output).
        alarm_name: Exact alarm definition name, e.g. "Virtual machine CPU usage".
        target: vCenter target name from config.yaml; omit to use the default target.

    Returns:
        Dict: entity_name, alarm_name, action ("acknowledged"), acknowledged (true).
    """
    try:
        si = _get_connection(target)
        return acknowledge_alarm(si, entity_name, alarm_name, target_name=target or "default")
    except Exception as e:
        return {"error": _safe_error(e, 'acknowledge_vcenter_alarm'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def reset_vcenter_alarm(
    entity_name: str,
    alarm_name: str,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Clear triggered vCenter alarms back to normal state.

    Uses AlarmManager.ClearTriggeredAlarms. The named alarm no longer appears in
    the active alarm list. Use this after resolving the underlying issue. Use
    list_vcenter_alarms to find entity_name and alarm_name values.

    Gotcha: vSphere has no per-alarm clear — this clears ALL triggered alarms
    matching the named alarm's entity type (host/VM/all) and current status
    (red/yellow). The response's 'scope' field states exactly what was cleared.

    Args:
        entity_name: Name of the entity with the alarm (VM name, host name, or cluster name).
        alarm_name: Exact alarm definition name from list_vcenter_alarms output.
        target: Optional vCenter target name from config.
    """
    try:
        si = _get_connection(target)
        return reset_alarm(si, entity_name, alarm_name, target_name=target or "default")
    except Exception as e:
        return {"error": _safe_error(e, 'reset_vcenter_alarm'), "hint": "Run 'vmware-aiops doctor' to verify connectivity and credentials."}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
