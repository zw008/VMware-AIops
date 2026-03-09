"""MCP server wrapping VMware AIops operations.

This module exposes VMware vCenter/ESXi inventory, health monitoring,
VM lifecycle, datastore browsing, and VM deployment tools via the Model
Context Protocol (MCP) using stdio transport.  It acts as a thin adapter
layer — each ``@mcp.tool()`` function simply delegates to the
corresponding function in the ``vmware_aiops`` package.

Tool categories
---------------
* **Read-only** (no side effects): list_*, get_*, browse_*, scan_*
* **Write / Deploy** (mutate state): vm_power_*, deploy_*, attach_*,
  batch_*, convert_*  — should be gated by the AI agent's confirmation
  flow.

Security considerations
-----------------------
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.
* **Destructive ops**: Deploy and batch operations create VMs and consume
  resources; confirmation is recommended before execution.

Source: https://github.com/zw008/VMware-AIops
License: MIT
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from vmware_aiops.config import load_config
from vmware_aiops.connection import ConnectionManager
from vmware_aiops.ops import datastore_browser, vm_deploy
from vmware_aiops.ops.health import get_active_alarms, get_recent_events
from vmware_aiops.ops.inventory import (
    list_clusters,
    list_datastores,
    list_hosts,
    list_vms,
)
from vmware_aiops.ops.vm_lifecycle import (
    get_vm_info,
    power_off_vm,
    power_on_vm,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "vmware-aiops",
    instructions=(
        "VMware vCenter/ESXi AI-powered monitoring and operations. "
        "Query inventory, check health/alarms, manage VM power state, "
        "browse datastores for images, and deploy VMs via OVA, template, "
        "linked clone, or batch YAML spec."
    ),
)

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

_conn_mgr: ConnectionManager | None = None


def _get_connection(target: str | None = None) -> Any:
    """Return a pyVmomi ServiceInstance, lazily initialising the manager."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_AIOPS_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr.connect(target)


# ---------------------------------------------------------------------------
# Inventory tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_virtual_machines(
    target: str | None = None,
    limit: int | None = None,
    sort_by: str = "name",
    power_state: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    """List virtual machines with optional filtering, sorting, and field selection.

    For large inventories, use limit + fields to keep context compact.
    Example: limit=10, sort_by="memory_mb", fields=["name","memory_mb","power_state"]
    returns the 10 VMs sorted by memory with only 3 fields each.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        limit: Max number of VMs to return (None = all).
        sort_by: Sort field: "name" | "cpu" | "memory_mb" | "power_state".
        power_state: Filter by power state: "poweredOn" | "poweredOff" | "suspended".
        fields: Return only these fields (None = all).
            Available: name, power_state, cpu, memory_mb, guest_os, ip_address,
                       host, uuid, tools_status.
    """
    si = _get_connection(target)
    return list_vms(si, limit=limit, sort_by=sort_by, power_state=power_state, fields=fields)


@mcp.tool()
def list_esxi_hosts(target: str | None = None) -> list[dict]:
    """List all ESXi hosts with CPU cores, memory, version, VM count, and uptime.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_hosts(si)


@mcp.tool()
def list_all_datastores(target: str | None = None) -> list[dict]:
    """List all datastores with capacity, free space, type, and VM count.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_datastores(si)


@mcp.tool()
def list_all_clusters(target: str | None = None) -> list[dict]:
    """List all clusters with host count, DRS/HA status, and resource totals.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_clusters(si)


# ---------------------------------------------------------------------------
# Health tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_alarms(target: str | None = None) -> list[dict]:
    """Get all active/triggered alarms across the VMware inventory.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_active_alarms(si)


@mcp.tool()
def get_events(
    hours: int = 24,
    severity: str = "warning",
    target: str | None = None,
) -> list[dict]:
    """Get recent vCenter/ESXi events filtered by severity.

    Args:
        hours: How many hours back to query (default 24).
        severity: Minimum severity level: "critical", "warning", or "info".
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_recent_events(si, hours=hours, severity=severity)


# ---------------------------------------------------------------------------
# VM tools
# ---------------------------------------------------------------------------


@mcp.tool()
def vm_info(vm_name: str, target: str | None = None) -> dict:
    """Get detailed information about a specific VM (CPU, memory, disks, NICs, snapshots).

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return get_vm_info(si, vm_name)


@mcp.tool()
def vm_power_on(vm_name: str, target: str | None = None) -> str:
    """Power on a virtual machine.

    Args:
        vm_name: Exact name of the virtual machine.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return power_on_vm(si, vm_name)


@mcp.tool()
def vm_power_off(
    vm_name: str,
    force: bool = False,
    target: str | None = None,
) -> str:
    """Power off a virtual machine. Graceful shutdown by default, force if specified.

    Args:
        vm_name: Exact name of the virtual machine.
        force: If True, hard power off. If False, graceful guest shutdown.
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return power_off_vm(si, vm_name, force=force)


# ---------------------------------------------------------------------------
# Datastore tools
# ---------------------------------------------------------------------------


@mcp.tool()
def browse_datastore(
    datastore_name: str,
    path: str = "",
    pattern: str = "*",
    target: str | None = None,
) -> list[dict]:
    """Browse files in a vSphere datastore directory.

    Use this to discover OVA, ISO, VMDK, and other files on datastores
    before deploying VMs.

    Args:
        datastore_name: Name of the datastore to browse.
        path: Subdirectory path (empty string for root).
        pattern: Glob pattern to filter files (e.g. "*.ova", "*.iso", "*").
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return datastore_browser.browse_datastore(si, datastore_name, path=path, pattern=pattern)


@mcp.tool()
def scan_datastore_images(target: str | None = None) -> dict:
    """Scan all accessible datastores for deployable images (OVA/ISO/OVF/VMDK).

    Results are cached locally in ~/.vmware-aiops/image_registry.json for
    fast lookup via list_cached_images. Run this to refresh the cache.

    Args:
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return datastore_browser.update_registry(si)


@mcp.tool()
def list_cached_images(
    image_type: str | None = None,
    datastore: str | None = None,
) -> list[dict]:
    """List deployable images from the local registry cache.

    Run scan_datastore_images first to populate the cache.

    Args:
        image_type: Filter by extension: "ova", "iso", "ovf", or "vmdk".
        datastore: Filter by datastore name.
    """
    return datastore_browser.list_images(image_type=image_type, datastore=datastore)


# ---------------------------------------------------------------------------
# Deploy tools
# ---------------------------------------------------------------------------


@mcp.tool()
def deploy_vm_from_ova(
    ova_path: str,
    vm_name: str,
    datastore_name: str,
    network_name: str = "VM Network",
    folder_path: str | None = None,
    power_on: bool = False,
    snapshot_name: str | None = None,
    target: str | None = None,
) -> str:
    """Deploy a VM from a local OVA file.

    Parses the OVF descriptor, creates import spec, uploads VMDKs via
    HTTP NFC lease. Optionally powers on and creates a baseline snapshot.

    Args:
        ova_path: Local file path to the .ova file.
        vm_name: Desired name for the new VM.
        datastore_name: Target datastore for the VM.
        network_name: Network to attach (default "VM Network").
        folder_path: VM folder path in vCenter (optional).
        power_on: Power on after deployment.
        snapshot_name: Create a baseline snapshot with this name (optional).
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return vm_deploy.deploy_ova(
        si, ova_path=ova_path, vm_name=vm_name,
        datastore_name=datastore_name, network_name=network_name,
        folder_path=folder_path, power_on=power_on,
        snapshot_name=snapshot_name,
    )


@mcp.tool()
def deploy_vm_from_template(
    template_name: str,
    new_name: str,
    datastore_name: str | None = None,
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    snapshot_name: str | None = None,
    target: str | None = None,
) -> str:
    """Deploy a new VM by cloning from a vSphere template.

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
    si = _get_connection(target)
    return vm_deploy.deploy_from_template(
        si, template_name=template_name, new_name=new_name,
        datastore_name=datastore_name, cpu=cpu, memory_mb=memory_mb,
        power_on=power_on, snapshot_name=snapshot_name,
    )


@mcp.tool()
def deploy_linked_clone(
    source_vm_name: str,
    snapshot_name: str,
    new_name: str,
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    baseline_snapshot: str | None = None,
    target: str | None = None,
) -> str:
    """Create a linked clone from a VM snapshot (near-instant, minimal disk).

    Linked clones share the source disk and use copy-on-write delta disks.
    This is the fastest provisioning method.

    Args:
        source_vm_name: Source VM to clone from.
        snapshot_name: Snapshot on the source VM to use as clone base.
        new_name: Name for the new linked clone.
        cpu: Override CPU count (optional).
        memory_mb: Override memory in MB (optional).
        power_on: Power on after creation.
        baseline_snapshot: Create a new snapshot on the clone (optional).
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return vm_deploy.linked_clone(
        si, source_vm_name=source_vm_name, new_name=new_name,
        snapshot_name=snapshot_name, cpu=cpu, memory_mb=memory_mb,
        power_on=power_on, baseline_snapshot=baseline_snapshot,
    )


@mcp.tool()
def attach_iso_to_vm(
    vm_name: str,
    iso_ds_path: str,
    target: str | None = None,
) -> str:
    """Attach an ISO from a datastore to a VM's CD-ROM drive.

    Args:
        vm_name: Target VM name.
        iso_ds_path: Datastore path, e.g. "[datastore1] iso/ubuntu.iso".
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return vm_deploy.attach_iso(si, vm_name, iso_ds_path)


@mcp.tool()
def convert_vm_to_template(
    vm_name: str,
    target: str | None = None,
) -> str:
    """Convert a powered-off VM to a vSphere template.

    After conversion the VM cannot be powered on — it serves as a
    clone source for deploy_vm_from_template.

    Args:
        vm_name: Name of the VM to convert (must be powered off).
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return vm_deploy.convert_to_template(si, vm_name)


@mcp.tool()
def batch_clone_vms(
    source_vm_name: str,
    vm_names: list[str],
    cpu: int | None = None,
    memory_mb: int | None = None,
    snapshot_name: str | None = None,
    power_on: bool = False,
    target: str | None = None,
) -> list[dict]:
    """Batch clone multiple VMs from a source VM (gold image).

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
    si = _get_connection(target)
    return vm_deploy.batch_clone(
        si, source_vm_name=source_vm_name, vm_names=vm_names,
        cpu=cpu, memory_mb=memory_mb,
        snapshot_name=snapshot_name, power_on=power_on,
    )


@mcp.tool()
def batch_linked_clone_vms(
    source_vm_name: str,
    snapshot_name: str,
    vm_names: list[str],
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    baseline_snapshot: str | None = None,
    target: str | None = None,
) -> list[dict]:
    """Batch create linked clones from a VM snapshot (fastest batch provisioning).

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
    si = _get_connection(target)
    return vm_deploy.batch_linked_clone(
        si, source_vm_name=source_vm_name, snapshot_name=snapshot_name,
        vm_names=vm_names, cpu=cpu, memory_mb=memory_mb,
        power_on=power_on, baseline_snapshot=baseline_snapshot,
    )


@mcp.tool()
def batch_deploy_from_spec(
    spec_path: str,
    target: str | None = None,
) -> list[dict]:
    """Batch deploy VMs from a YAML specification file.

    The YAML spec supports all provisioning channels:
    - source: clone from a VM
    - template: clone from a vSphere template
    - linked_clone: instant clone from a snapshot
    - Per-VM ova: deploy from OVA file
    - Fallback: create empty VMs (optionally with ISO)

    Args:
        spec_path: Path to the deploy.yaml specification file.
        target: Optional vCenter/ESXi target name from config.
    """
    si = _get_connection(target)
    return vm_deploy.batch_deploy(si, spec_path)


# ---------------------------------------------------------------------------
# TTL & Clean Slate
# ---------------------------------------------------------------------------


@mcp.tool()
def vm_set_ttl(
    vm_name: str,
    minutes: int,
    target: str | None = None,
) -> str:
    """Set a Time-To-Live (TTL) for a VM. The daemon auto-deletes it when expired.

    The scheduler daemon must be running (`vmware-aiops daemon start`) for
    automatic deletion. TTLs are persisted in ~/.vmware-aiops/ttl.json.

    Args:
        vm_name: Name of the VM to auto-delete.
        minutes: Minutes until deletion (minimum 1).
        target: Optional vCenter/ESXi target name from config.
    """
    from vmware_aiops.ops.ttl import set_ttl as _set_ttl
    return _set_ttl(vm_name, minutes, target=target)


@mcp.tool()
def vm_cancel_ttl(vm_name: str) -> str:
    """Cancel an existing TTL for a VM (prevents auto-deletion).

    Args:
        vm_name: Name of the VM whose TTL should be cancelled.
    """
    from vmware_aiops.ops.ttl import cancel_ttl as _cancel_ttl
    return _cancel_ttl(vm_name)


@mcp.tool()
def vm_list_ttl() -> list[dict]:
    """List all VMs with TTLs registered, including expiry time and status.

    Returns a list of TTL entries with remaining_minutes and expired flag.
    """
    from vmware_aiops.ops.ttl import list_ttl as _list_ttl
    return _list_ttl()


@mcp.tool()
def vm_clean_slate(
    vm_name: str,
    snapshot_name: str = "baseline",
    target: str | None = None,
) -> str:
    """Revert a VM to its baseline snapshot (Clean Slate).

    Powers off the VM first if it is running, then reverts to the named
    snapshot. Use this to reset a lab/dev VM to a clean starting state
    after a task completes.

    Args:
        vm_name: Name of the VM to revert.
        snapshot_name: Snapshot name to revert to (default: "baseline").
        target: Optional vCenter/ESXi target name from config.
    """
    from vmware_aiops.ops.vm_lifecycle import clean_slate
    si = _get_connection(target)
    return clean_slate(si, vm_name, snapshot_name=snapshot_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
