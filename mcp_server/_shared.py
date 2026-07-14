"""Shared MCP server primitives: the FastMCP instance, connection helper,
error sanitisation, and the ``@tool_errors`` decorator.

Tool modules under ``mcp_server/tools/`` import ``mcp`` from here and register
their ``@mcp.tool()`` functions onto it. ``mcp_server/server.py`` then imports
those modules and runs the server.

Keep ``Optional[X]`` (never PEP 604 ``X | None``) in any FastMCP-reflected
tool signature — on Python 3.10 with older mcp/pydantic the union is eval'd to
``types.UnionType`` and FastMCP's ``issubclass`` check crashes (踩坑 #33).
"""

import functools
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP
from vmware_policy import sanitize

from vmware_aiops.config import load_config
from vmware_aiops.connection import ConnectionManager
from vmware_aiops.ops.cluster_mgmt import ClusterError, ClusterNotFoundError
from vmware_aiops.ops.guest_ops import GuestOpsError
from vmware_aiops.ops.vm_lifecycle import TaskFailedError, VMNotFoundError

logger = logging.getLogger(__name__)

_DOCTOR_HINT = "Run 'vmware-aiops doctor' to verify connectivity and credentials."


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


def tool_errors(shape: str = "str") -> Callable:
    """Wrap a tool body in the canonical try/except → ``_safe_error`` pattern.

    Collapses the ~41 near-identical error blocks. Behaviour is byte-for-byte
    identical to the inline handlers it replaces — the only difference is the
    error payload shape, selected per the tool's declared return type:

    * ``"str"``  → ``f"Error: {msg} {hint}"``
    * ``"dict"`` → ``{"error": msg, "hint": hint}``
    * ``"list"`` → ``[{"error": msg, "hint": hint}]``

    The decorated tool name passed to ``_safe_error`` is ``func.__name__``,
    matching the literal names used by the original inline blocks.

    Place this *between* ``@vmware_tool`` and the function so the audit
    decorator and FastMCP still see the original signature (preserved via
    ``functools.wraps``); the wrapper catches exceptions exactly where the
    inline ``try/except`` did, so ``@vmware_tool`` never observes them.
    """

    def decorator(func: Callable) -> Callable:
        name = func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 — sanitised below
                msg = _safe_error(e, name)
                if shape == "dict":
                    return {"error": msg, "hint": _DOCTOR_HINT}
                if shape == "list":
                    return [{"error": msg, "hint": _DOCTOR_HINT}]
                return f"Error: {msg} {_DOCTOR_HINT}"

        return wrapper

    return decorator


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


def _ensure_conn_mgr() -> ConnectionManager:
    """Lazily build the shared ConnectionManager (does not connect anything)."""
    global _conn_mgr  # noqa: PLW0603
    if _conn_mgr is None:
        config_path_str = os.environ.get("VMWARE_AIOPS_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        config = load_config(config_path)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr


def _get_connection(target: Optional[str] = None) -> Any:
    """Return a pyVmomi ServiceInstance, lazily initialising the manager."""
    return _ensure_conn_mgr().connect(target)
