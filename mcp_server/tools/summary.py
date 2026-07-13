"""Cluster-health summary tool (read-only) — delegates to vmware-monitor.

The aggregation + ranking logic lives in the vmware-monitor package (a declared
dependency). AIops is the family's conversational entry point, so it re-exposes
the same one-glance triage here — using its own vCenter connection — rather than
forcing the user to switch skills. Read-only; no state is changed.
"""

from typing import Optional

from vmware_monitor.ops.cluster_summary import get_cluster_health_summary
from vmware_policy import vmware_tool

from mcp_server._shared import _get_connection, mcp, tool_errors


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
@vmware_tool(risk_level="low")
@tool_errors("dict")
def cluster_health_summary(
    target: Optional[str] = None,
    cluster_filter: Optional[str] = None,
    include_vms: bool = True,
    top_n: int = 10,
) -> dict:
    """[READ] One-glance health rollup for every cluster — "is anything on fire?".

    Aggregates hosts, VM power state, live CPU/memory pressure, and triggered
    alarms per cluster, assigns each an opinionated status ("ok"/"warn"/
    "critical"), and flattens the individual anomalies into a ranked ``top_issues``
    focus list — the fast triage view for "what's wrong in my environment right
    now?". Delegates to the vmware-monitor library (read-only); use it FIRST for a
    cross-cluster glance before drilling into specific VMs/hosts with the other
    AIops tools.

    Returns {totals, top_issues, issues_total, clusters, snapshot,
    customization_hint}. Lead with ``top_issues`` (worst first, each with a
    drill-down hint), show ``clusters`` as context, and echo ``customization_hint``
    as the closing line. Point-in-time snapshot — no trending.

    Args:
        target: Optional vCenter/ESXi target name from config. Uses default if omitted.
        cluster_filter: Case-insensitive substring to show only matching clusters.
        include_vms: Roll up VM power counts (default True). False skips the VM
            pass on very large fleets.
        top_n: Cap the top_issues focus list (default 10; 0 hides it).
    """
    si = _get_connection(target)
    return get_cluster_health_summary(
        si, cluster_filter=cluster_filter, include_vms=include_vms, top_n=top_n
    )
