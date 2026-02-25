"""CLI entry point for VMware AIops."""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vmware_aiops.config import CONFIG_DIR

app = typer.Typer(
    name="vmware-aiops",
    help="VMware vCenter/ESXi AI-powered monitoring and operations.",
    no_args_is_help=True,
)
console = Console()

# Sub-commands
inventory_app = typer.Typer(help="Query vCenter/ESXi inventory.")
health_app = typer.Typer(help="Health checks: alarms, hardware, services.")
vm_app = typer.Typer(help="VM lifecycle: power, snapshot, clone, migrate.")
scan_app = typer.Typer(help="Log and alarm scanning.")
daemon_app = typer.Typer(help="Scanner daemon management.")

app.add_typer(inventory_app, name="inventory")
app.add_typer(health_app, name="health")
app.add_typer(vm_app, name="vm")
app.add_typer(scan_app, name="scan")
app.add_typer(daemon_app, name="daemon")

TargetOption = Annotated[
    str | None, typer.Option("--target", "-t", help="Target name from config")
]
ConfigOption = Annotated[
    Path | None, typer.Option("--config", "-c", help="Config file path")
]


def _get_connection(target: str | None, config_path: Path | None = None):
    """Helper to get a pyVmomi connection."""
    from vmware_aiops.config import load_config
    from vmware_aiops.connection import ConnectionManager

    cfg = load_config(config_path)
    mgr = ConnectionManager(cfg)
    return mgr.connect(target), cfg


# ─── Inventory ────────────────────────────────────────────────────────────────


@inventory_app.command("vms")
def inventory_vms(target: TargetOption = None, config: ConfigOption = None) -> None:
    """List all virtual machines."""
    from vmware_aiops.ops.inventory import list_vms

    si, _ = _get_connection(target, config)
    vms = list_vms(si)
    table = Table(title="Virtual Machines")
    table.add_column("Name", style="cyan")
    table.add_column("Power")
    table.add_column("CPUs", justify="right")
    table.add_column("Memory (MB)", justify="right")
    table.add_column("Guest OS")
    table.add_column("IP Address")
    for vm in vms:
        power_style = "green" if vm["power_state"] == "poweredOn" else "red"
        table.add_row(
            vm["name"],
            f"[{power_style}]{vm['power_state']}[/]",
            str(vm["cpu"]),
            str(vm["memory_mb"]),
            vm["guest_os"],
            vm["ip_address"] or "-",
        )
    console.print(table)


@inventory_app.command("hosts")
def inventory_hosts(target: TargetOption = None, config: ConfigOption = None) -> None:
    """List all ESXi hosts."""
    from vmware_aiops.ops.inventory import list_hosts

    si, _ = _get_connection(target, config)
    hosts = list_hosts(si)
    table = Table(title="ESXi Hosts")
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("CPU Cores", justify="right")
    table.add_column("Memory (GB)", justify="right")
    table.add_column("VMs", justify="right")
    for h in hosts:
        state_style = "green" if h["connection_state"] == "connected" else "red"
        table.add_row(
            h["name"],
            f"[{state_style}]{h['connection_state']}[/]",
            str(h["cpu_cores"]),
            str(h["memory_gb"]),
            str(h["vm_count"]),
        )
    console.print(table)


@inventory_app.command("datastores")
def inventory_datastores(
    target: TargetOption = None, config: ConfigOption = None
) -> None:
    """List all datastores."""
    from vmware_aiops.ops.inventory import list_datastores

    si, _ = _get_connection(target, config)
    stores = list_datastores(si)
    table = Table(title="Datastores")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Free (GB)", justify="right")
    table.add_column("Total (GB)", justify="right")
    table.add_column("Usage %", justify="right")
    for ds in stores:
        pct = ((ds["total_gb"] - ds["free_gb"]) / ds["total_gb"] * 100) if ds["total_gb"] else 0
        pct_style = "red" if pct > 85 else "yellow" if pct > 70 else "green"
        table.add_row(
            ds["name"],
            ds["type"],
            f"{ds['free_gb']:.1f}",
            f"{ds['total_gb']:.1f}",
            f"[{pct_style}]{pct:.1f}%[/]",
        )
    console.print(table)


@inventory_app.command("clusters")
def inventory_clusters(
    target: TargetOption = None, config: ConfigOption = None
) -> None:
    """List all clusters."""
    from vmware_aiops.ops.inventory import list_clusters

    si, _ = _get_connection(target, config)
    clusters = list_clusters(si)
    table = Table(title="Clusters")
    table.add_column("Name", style="cyan")
    table.add_column("Hosts", justify="right")
    table.add_column("DRS")
    table.add_column("HA")
    for c in clusters:
        table.add_row(
            c["name"],
            str(c["host_count"]),
            "[green]ON[/]" if c["drs_enabled"] else "[red]OFF[/]",
            "[green]ON[/]" if c["ha_enabled"] else "[red]OFF[/]",
        )
    console.print(table)


# ─── Health ───────────────────────────────────────────────────────────────────


@health_app.command("alarms")
def health_alarms(target: TargetOption = None, config: ConfigOption = None) -> None:
    """Show active alarms."""
    from vmware_aiops.ops.health import get_active_alarms

    si, _ = _get_connection(target, config)
    alarms = get_active_alarms(si)
    if not alarms:
        console.print("[green]No active alarms.[/]")
        return
    table = Table(title="Active Alarms")
    table.add_column("Severity")
    table.add_column("Alarm", style="cyan")
    table.add_column("Entity")
    table.add_column("Time")
    for a in alarms:
        sev_style = {"red": "red", "yellow": "yellow"}.get(a["severity"], "white")
        table.add_row(
            f"[{sev_style}]{a['severity']}[/]",
            a["alarm_name"],
            a["entity_name"],
            a["time"],
        )
    console.print(table)


@health_app.command("events")
def health_events(
    hours: Annotated[int, typer.Option(help="Lookback hours")] = 24,
    severity: Annotated[str, typer.Option(help="Min severity: info/warning/error")] = "warning",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show recent events."""
    from vmware_aiops.ops.health import get_recent_events

    si, _ = _get_connection(target, config)
    events = get_recent_events(si, hours=hours, severity=severity)
    if not events:
        console.print(f"[green]No events above '{severity}' in the last {hours}h.[/]")
        return
    table = Table(title=f"Events (last {hours}h, >= {severity})")
    table.add_column("Time")
    table.add_column("Type", style="cyan")
    table.add_column("Message")
    for e in events:
        table.add_row(e["time"], e["event_type"], e["message"][:120])
    console.print(table)


# ─── VM ───────────────────────────────────────────────────────────────────────


@vm_app.command("info")
def vm_info(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show detailed info for a VM."""
    from vmware_aiops.ops.vm_lifecycle import get_vm_info

    si, _ = _get_connection(target, config)
    info = get_vm_info(si, name)
    for k, v in info.items():
        console.print(f"  [cyan]{k}:[/] {v}")


@vm_app.command("power-on")
def vm_power_on(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Power on a VM."""
    from vmware_aiops.ops.vm_lifecycle import power_on_vm

    si, _ = _get_connection(target, config)
    result = power_on_vm(si, name)
    console.print(f"[green]{result}[/]")


@vm_app.command("power-off")
def vm_power_off(
    name: str,
    force: Annotated[bool, typer.Option(help="Force power off")] = False,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Power off a VM (graceful shutdown or force)."""
    from vmware_aiops.ops.vm_lifecycle import power_off_vm

    si, _ = _get_connection(target, config)
    result = power_off_vm(si, name, force=force)
    console.print(f"[green]{result}[/]")


@vm_app.command("create")
def vm_create(
    name: str,
    cpu: Annotated[int, typer.Option(help="Number of CPUs")] = 2,
    memory: Annotated[int, typer.Option(help="Memory in MB")] = 4096,
    disk: Annotated[int, typer.Option(help="Disk size in GB")] = 40,
    network: Annotated[str, typer.Option(help="Network name")] = "VM Network",
    datastore: Annotated[str, typer.Option(help="Datastore name")] = "",
    folder: Annotated[str, typer.Option(help="VM folder path")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Create a new VM."""
    from vmware_aiops.ops.vm_lifecycle import create_vm

    si, _ = _get_connection(target, config)
    result = create_vm(
        si,
        vm_name=name,
        cpu=cpu,
        memory_mb=memory,
        disk_gb=disk,
        network_name=network,
        datastore_name=datastore or None,
        folder_path=folder or None,
    )
    console.print(f"[green]{result}[/]")


@vm_app.command("delete")
def vm_delete(
    name: str,
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Skip confirmation prompt")
    ] = False,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Delete a VM (destructive!)."""
    if not confirm:
        typer.confirm(f"Delete VM '{name}'? This cannot be undone", abort=True)

    from vmware_aiops.ops.vm_lifecycle import delete_vm

    si, _ = _get_connection(target, config)
    result = delete_vm(si, name)
    console.print(f"[green]{result}[/]")


@vm_app.command("reconfigure")
def vm_reconfigure(
    name: str,
    cpu: Annotated[int | None, typer.Option(help="New CPU count")] = None,
    memory: Annotated[int | None, typer.Option(help="New memory in MB")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Reconfigure VM CPU/memory."""
    from vmware_aiops.ops.vm_lifecycle import reconfigure_vm

    si, _ = _get_connection(target, config)
    result = reconfigure_vm(si, name, cpu=cpu, memory_mb=memory)
    console.print(f"[green]{result}[/]")


@vm_app.command("snapshot-create")
def vm_snapshot_create(
    vm_name: str,
    snap_name: Annotated[str, typer.Option("--name", help="Snapshot name")] = "snapshot",
    description: Annotated[str, typer.Option(help="Snapshot description")] = "",
    memory: Annotated[bool, typer.Option(help="Include memory")] = True,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Create a VM snapshot."""
    from vmware_aiops.ops.vm_lifecycle import create_snapshot

    si, _ = _get_connection(target, config)
    result = create_snapshot(si, vm_name, snap_name, description, memory)
    console.print(f"[green]{result}[/]")


@vm_app.command("snapshot-list")
def vm_snapshot_list(
    vm_name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """List VM snapshots."""
    from vmware_aiops.ops.vm_lifecycle import list_snapshots

    si, _ = _get_connection(target, config)
    snaps = list_snapshots(si, vm_name)
    if not snaps:
        console.print("[yellow]No snapshots found.[/]")
        return
    for s in snaps:
        prefix = "  " * s["level"]
        console.print(f"{prefix}[cyan]{s['name']}[/] ({s['created']}) - {s['description']}")


@vm_app.command("snapshot-revert")
def vm_snapshot_revert(
    vm_name: str,
    snap_name: Annotated[str, typer.Option("--name", help="Snapshot name to revert to")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Revert VM to a snapshot."""
    from vmware_aiops.ops.vm_lifecycle import revert_to_snapshot

    si, _ = _get_connection(target, config)
    result = revert_to_snapshot(si, vm_name, snap_name)
    console.print(f"[green]{result}[/]")


@vm_app.command("snapshot-delete")
def vm_snapshot_delete(
    vm_name: str,
    snap_name: Annotated[str, typer.Option("--name", help="Snapshot name to delete")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Delete a VM snapshot."""
    from vmware_aiops.ops.vm_lifecycle import delete_snapshot

    si, _ = _get_connection(target, config)
    result = delete_snapshot(si, vm_name, snap_name)
    console.print(f"[green]{result}[/]")


@vm_app.command("clone")
def vm_clone(
    name: str,
    new_name: Annotated[str, typer.Option("--new-name", help="Name for the clone")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Clone a VM."""
    from vmware_aiops.ops.vm_lifecycle import clone_vm

    si, _ = _get_connection(target, config)
    result = clone_vm(si, name, new_name)
    console.print(f"[green]{result}[/]")


@vm_app.command("migrate")
def vm_migrate(
    name: str,
    to_host: Annotated[str, typer.Option("--to-host", help="Target ESXi host name")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Migrate (vMotion) a VM to another host."""
    from vmware_aiops.ops.vm_lifecycle import migrate_vm

    si, _ = _get_connection(target, config)
    result = migrate_vm(si, name, to_host)
    console.print(f"[green]{result}[/]")


# ─── Scan ─────────────────────────────────────────────────────────────────────


@scan_app.command("now")
def scan_now(target: TargetOption = None, config: ConfigOption = None) -> None:
    """Run a one-time scan of alarms and events."""
    from vmware_aiops.scanner.alarm_scanner import scan_alarms
    from vmware_aiops.scanner.log_scanner import scan_logs

    si, cfg = _get_connection(target, config)
    console.print("[bold]Running scan...[/]")
    alarm_results = scan_alarms(si)
    log_results = scan_logs(si, cfg.scanner)
    total = len(alarm_results) + len(log_results)
    if total == 0:
        console.print("[green]All clear. No issues found.[/]")
    else:
        console.print(f"[yellow]Found {total} issue(s).[/]")
        for r in alarm_results + log_results:
            sev_style = {"critical": "red", "warning": "yellow"}.get(
                r["severity"], "white"
            )
            console.print(
                f"  [{sev_style}][{r['severity'].upper()}][/] {r['message']}"
            )


# ─── Daemon ───────────────────────────────────────────────────────────────────


@daemon_app.command("start")
def daemon_start(config: ConfigOption = None) -> None:
    """Start the scanner daemon."""
    from vmware_aiops.scanner.scheduler import start_scheduler

    console.print("[bold]Starting scanner daemon...[/]")
    start_scheduler(config)


@daemon_app.command("status")
def daemon_status() -> None:
    """Check scanner daemon status."""
    pid_file = CONFIG_DIR / "daemon.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        console.print(f"[green]Daemon running (PID: {pid})[/]")
    else:
        console.print("[yellow]Daemon not running.[/]")


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the scanner daemon."""
    import os as _os

    pid_file = CONFIG_DIR / "daemon.pid"
    if not pid_file.exists():
        console.print("[yellow]Daemon not running.[/]")
        return

    pid = int(pid_file.read_text().strip())
    try:
        _os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Daemon (PID: {pid}) stopped.[/]")
    except ProcessLookupError:
        console.print(f"[yellow]Daemon process (PID: {pid}) not found. Cleaning up.[/]")
    except OSError as e:
        console.print(f"[red]Failed to stop daemon: {e}[/]")
        return
    pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    app()
