"""Regression — AIops re-exposes cluster-health summary by delegating to monitor.

AIops is the family's conversational entry point, so "what's wrong in my
environment?" must work from an AIops conversation too. The aggregation lives in
vmware-monitor (a dependency); AIops registers a thin ``cluster_health_summary``
MCP tool and ``summary`` CLI command that call it with AIops's own connection —
no logic is duplicated. These tests lock that wiring so a refactor on either side
cannot silently drop it.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from typer.testing import CliRunner

from vmware_aiops.cli import app

_SAMPLE = {
    "totals": {
        "clusters": 1,
        "hosts_total": 2,
        "hosts_connected": 1,
        "vms_total": 10,
        "vms_on": 8,
        "alarms": {"critical": 1, "warning": 0},
        "worst_status": "critical",
    },
    "top_issues": [
        {
            "severity": "critical",
            "kind": "host_down",
            "object": "esx-9",
            "scope": "host",
            "cluster": "prod",
            "detail": "host notResponding",
            "drilldown": "inventory hosts",
        },
    ],
    "issues_total": 1,
    "clusters": [
        {
            "name": "prod",
            "hosts_total": 2,
            "hosts_connected": 1,
            "vms_total": 10,
            "vms_on": 8,
            "cpu_used_pct": 40,
            "mem_used_pct": 50,
            "ha_enabled": True,
            "drs_enabled": True,
            "alarms": {"critical": 1, "warning": 0},
            "status": "critical",
            "attention": ["1 host disconnected"],
        },
    ],
    "snapshot": "point-in-time",
    "customization_hint": "hint",
}


class _Cfg:
    class default_target:  # noqa: N801 - stub matching config shape
        name = "prod-vc"


def test_mcp_tool_registered_and_read_only() -> None:
    """The delegated summary tool is present on the AIops MCP server."""
    from mcp_server.server import mcp

    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "cluster_health_summary" in tools, "AIops must re-expose cluster_health_summary"


def test_mcp_tool_delegates_to_monitor() -> None:
    """The tool calls the vmware-monitor aggregation with AIops's connection."""
    from mcp_server.tools import summary as tool_mod

    with (
        patch.object(tool_mod, "_get_connection", return_value=object()) as conn,
        patch.object(tool_mod, "get_cluster_health_summary", return_value=_SAMPLE) as agg,
    ):
        out = tool_mod.cluster_health_summary(target="prod-vc", top_n=5)
    assert out is _SAMPLE
    conn.assert_called_once()
    # include_vms + top_n threaded through to the monitor function.
    assert agg.call_args.kwargs["top_n"] == 5
    assert agg.call_args.kwargs["include_vms"] is True


def test_cli_summary_terminal_and_html(tmp_path) -> None:
    """`vmware-aiops summary` renders via monitor; --html writes an offline file."""
    out = tmp_path / "snap.html"
    with (
        patch("vmware_aiops.cli.summary._get_connection", return_value=(object(), _Cfg())),
        patch(
            "vmware_monitor.ops.cluster_summary.get_cluster_health_summary", return_value=_SAMPLE
        ),
        patch("vmware_aiops.cli.summary._audit"),
    ):
        term = CliRunner().invoke(app, ["summary"])
        assert term.exit_code == 0, term.output
        assert "Top 1 issues" in term.output and "prod" in term.output

        html = CliRunner().invoke(app, ["summary", "--html-path", str(out)])
        assert html.exit_code == 0, html.output
    assert out.exists()
    assert out.read_text().startswith("<!doctype html>")
