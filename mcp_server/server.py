"""MCP server wrapping VMware AIops operations.

This module exposes VMware vCenter/ESXi VM lifecycle, deployment, cluster
management, guest operations, and datastore browsing tools via the Model
Context Protocol (MCP) using stdio transport.  It acts as a thin adapter
layer — each ``@mcp.tool()`` function (defined in ``mcp_server/tools/``)
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
* ``mcp_server/_shared.py`` — the shared ``mcp`` (FastMCP) instance, the
  connection helper, ``_safe_error``, and the ``@tool_errors`` decorator.
* ``mcp_server/tools/*.py`` — one module per tool category; importing each
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

from mcp_server._shared import _safe_error, mcp, tool_errors

# Importing the tool modules registers every @mcp.tool() onto the shared
# `mcp` instance above. Order does not matter; each module is self-contained.
from mcp_server.tools import (  # noqa: F401 — imported for registration side effects
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
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")
