"""Top-level Typer app: assembles all sub-apps and top-level commands."""

from __future__ import annotations

import typer

from vmware_aiops.cli.alarm import alarm_app
from vmware_aiops.cli.cluster import cluster_app
from vmware_aiops.cli.deploy import datastore_app, deploy_app
from vmware_aiops.cli.doctor import doctor_cmd
from vmware_aiops.cli.hub import hub_app
from vmware_aiops.cli.mcp_config import mcp_config_app
from vmware_aiops.cli.plan import plan_app
from vmware_aiops.cli.scan import daemon_app, scan_app
from vmware_aiops.cli.vm import vm_app

app = typer.Typer(
    name="vmware-aiops",
    help="VMware vCenter/ESXi AI-powered monitoring and operations.",
    no_args_is_help=True,
)

# Register sub-apps
app.add_typer(vm_app, name="vm")
app.add_typer(deploy_app, name="deploy")
app.add_typer(datastore_app, name="datastore")
app.add_typer(cluster_app, name="cluster")
app.add_typer(scan_app, name="scan")
app.add_typer(daemon_app, name="daemon")
app.add_typer(plan_app, name="plan")
app.add_typer(mcp_config_app, name="mcp-config")
app.add_typer(alarm_app, name="alarm")
app.add_typer(hub_app, name="hub")

# Register top-level commands
app.command("doctor")(doctor_cmd)


@app.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server (stdio transport).

    Single-command entry point for MCP clients (Claude Desktop, Cursor, etc.):
        vmware-aiops mcp

    Equivalent to the legacy `vmware-aiops-mcp` console script.
    """
    from mcp_server.server import main as _mcp_main

    _mcp_main()


if __name__ == "__main__":
    app()
