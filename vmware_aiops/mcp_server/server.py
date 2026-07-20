"""MCP server wrapping VMware AIops operations.

This module exposes VMware vCenter/ESXi VM lifecycle, deployment, cluster
management, guest operations, and datastore browsing tools via the Model
Context Protocol (MCP) using stdio transport.  It acts as a thin adapter
layer — each ``@mcp.tool()`` function (defined in ``vmware_aiops/mcp_server/tools/``)
simply delegates to the corresponding function in the ``vmware_aiops``
package.

For read-only monitoring (inventory, alarms, events, VM info), use the
companion skill ``vmware-monitor``.  For storage management (iSCSI, vSAN),
use ``vmware-storage``.  For Tanzu Kubernetes, use ``vmware-vks``.

Tool categories
---------------
* **Read-only** (no side effects): browse_*, scan_*
* **Write / Deploy** (mutate state): vm_power_*, deploy_*, attach_*,
  batch_*, convert_*, cluster_*  — should be gated by the AI agent's
  confirmation flow.

Module layout
-------------
* ``vmware_aiops/mcp_server/_shared.py`` — the shared ``mcp`` (FastMCP) instance, the
  connection helper, ``_safe_error``, and the ``@tool_errors`` decorator.
* ``vmware_aiops/mcp_server/tools/*.py`` — one module per tool category; importing each
  registers its ``@mcp.tool()`` functions onto the shared ``mcp`` instance.
* this file — re-exports ``mcp`` and exposes ``main()`` (the ``vmware-aiops-mcp``
  console script and the ``vmware-aiops mcp`` subcommand both call it).

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
from typing import Optional

from vmware_policy import apply_read_only_gate, mtime_cached_loader, set_environment_resolver

from vmware_aiops.config import CONFIG_FILE, load_config

from vmware_aiops.mcp_server._shared import _safe_error, mcp, tool_errors

# Importing the tool modules registers every @mcp.tool() onto the shared
# `mcp` instance above. Order does not matter; each module is self-contained.
from vmware_aiops.mcp_server.tools import (  # noqa: F401 — imported for registration side effects
    alarm,
    cluster,
    datastore,
    deploy,
    guest,
    network,
    plan,
    summary,
    ttl,
    vm,
)

__all__ = ["mcp", "main", "_safe_error", "tool_errors"]


# ---------------------------------------------------------------------------
# Read-only gate
# ---------------------------------------------------------------------------


def _config_read_only() -> Optional[bool]:
    """Best-effort read of ``read_only`` from the config file.

    Runs at import time, when no config file need exist yet (tests, ``--help``,
    smoke checks), so every failure degrades to "not configured" and lets the
    env vars decide. None and False are equivalent here — config is the last
    link in the precedence chain — but None keeps 'not configured'
    distinguishable from 'configured off' in logs and debugging.

    Resolved through the same VMWARE_AIOPS_CONFIG override the connection layer
    uses. Reading the default path instead would silently ignore settings in an
    operator's custom config file — a control that appears configured and does
    nothing, which is the exact failure this work exists to remove.
    """
    try:
        _cfg_path = os.environ.get("VMWARE_AIOPS_CONFIG")
        return load_config(Path(_cfg_path) if _cfg_path else None).read_only
    except Exception:  # noqa: BLE001 — absent/unreadable config is not an error here
        return None


# Applied once, after every tool module above has registered. In read-only mode
# the write tools are removed from the registry, so list_tools() never offers
# them — the guarantee is structural rather than a prompt instruction the model
# may ignore (issue #31).
WITHHELD_WRITE_TOOLS: list[str] = apply_read_only_gate(
    mcp, "vmware-aiops", config_flag=_config_read_only()
)


# ---------------------------------------------------------------------------
# Environment declaration
# ---------------------------------------------------------------------------


_cached_config = mtime_cached_loader("VMWARE_AIOPS_CONFIG", CONFIG_FILE, load_config)


def _environment_for(target: Optional[str]) -> str:
    """Report the environment a target declares, for policy scoping.

    Policy rules scope by environment ("irreversible work in production needs a
    second person"), and vmware-policy cannot read this skill's config itself.
    Registering this lookup is what lets those rules fire at all. Reloaded on
    config.yaml mtime change so an edit takes effect without restarting the
    server. The config is cached via :func:`vmware_policy.mtime_cached_loader`,
    so repeated tool calls pay one ``os.stat`` instead of a full YAML parse.
    """
    try:
        return _cached_config().environment_for(target)
    except Exception:  # noqa: BLE001 — an unreadable config means "undeclared"
        return ""


set_environment_resolver(_environment_for)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
