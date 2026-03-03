"""MCP server wrapping VMware AIops operations.

This module exposes VMware vCenter/ESXi inventory, health monitoring,
and VM lifecycle tools via the Model Context Protocol (MCP) using stdio
transport.  It acts as a thin adapter layer — each ``@mcp.tool()``
function simply delegates to the corresponding function in the
``vmware_aiops`` package (ops.inventory, ops.health, ops.vm_lifecycle).

Security considerations
-----------------------
* **Read vs Write tools**: Read-only tools (list_*, get_*) have no side
  effects.  Write tools (vm_power_on, vm_power_off) mutate VM state and
  should be gated by the AI agent's confirmation flow.
* **Credential handling**: Credentials are loaded from environment
  variables / ``.env`` file — never passed via MCP messages.
* **Transport**: Uses stdio transport (local only); no network listener.

Source: https://github.com/zw008/VMware-AIops
License: MIT
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

# MCP SDK — Model Context Protocol server framework
from mcp.server.fastmcp import FastMCP

# Internal VMware operations modules
from vmware_aiops.config import load_config
from vmware_aiops.connection import ConnectionManager
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
        "Query inventory, check health/alarms, and manage VM power state."
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
def list_virtual_machines(target: str | None = None) -> list[dict]:
    """List all virtual machines with name, power state, CPU, memory, guest OS, and IP.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
    """
    si = _get_connection(target)
    return list_vms(si)


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
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
