"""CLI entry point for VMware AIops."""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vmware_aiops.config import CONFIG_DIR
from vmware_aiops.notify.audit import AuditLogger

_audit = AuditLogger()

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
deploy_app = typer.Typer(help="VM deployment: OVA, template, linked clone, batch.")
datastore_app = typer.Typer(help="Datastore browsing and image discovery.")
scan_app = typer.Typer(help="Log and alarm scanning.")
daemon_app = typer.Typer(help="Scanner daemon management.")

app.add_typer(inventory_app, name="inventory")
app.add_typer(health_app, name="health")
app.add_typer(vm_app, name="vm")
app.add_typer(deploy_app, name="deploy")
app.add_typer(datastore_app, name="datastore")
app.add_typer(scan_app, name="scan")
app.add_typer(daemon_app, name="daemon")

TargetOption = Annotated[
    str | None, typer.Option("--target", "-t", help="Target name from config")
]
ConfigOption = Annotated[
    Path | None, typer.Option("--config", "-c", help="Config file path")
]
DryRunOption = Annotated[
    bool, typer.Option("--dry-run", help="Print API calls without executing")
]


def _dry_run_print(
    *,
    target: str,
    vm_name: str,
    operation: str,
    api_call: str,
    parameters: dict | None = None,
    before_state: dict | None = None,
    expected_after: dict | None = None,
) -> None:
    """Print a dry-run preview of the API call that would be made."""
    console.print("\n[bold magenta][DRY-RUN] No changes will be made.[/]")
    console.print(f"[magenta]  Target:    {target}[/]")
    console.print(f"[magenta]  VM:        {vm_name}[/]")
    console.print(f"[magenta]  Operation: {operation}[/]")
    console.print(f"[magenta]  API Call:  {api_call}[/]")
    if parameters:
        for k, v in parameters.items():
            console.print(f"[magenta]  Param:     {k} = {v}[/]")
    if before_state:
        console.print(f"[magenta]  Current:   {before_state}[/]")
    if expected_after:
        console.print(f"[magenta]  Expected:  {expected_after}[/]")
    console.print("[magenta]  Run without --dry-run to execute.[/]\n")
    _audit.log(
        target=target,
        operation=operation,
        resource=vm_name,
        parameters={"dry_run": True, **(parameters or {})},
        before_state=before_state or {},
        result="dry-run",
    )


def _get_connection(target: str | None, config_path: Path | None = None):
    """Helper to get a pyVmomi connection."""
    from vmware_aiops.config import load_config
    from vmware_aiops.connection import ConnectionManager

    cfg = load_config(config_path)
    mgr = ConnectionManager(cfg)
    return mgr.connect(target), cfg


def _resolve_target(target: str | None) -> str:
    """Return a display name for the target (used in audit logs)."""
    return target or "default"


def _show_state_preview(info: dict, action: str, vm_name: str) -> None:
    """Display current VM state before a destructive operation."""
    console.print(f"\n[bold cyan]📋 Current state of VM '{vm_name}':[/]")
    state_keys = (
        "power_state", "cpu", "memory_mb", "guest_os",
        "host", "ip_address", "snapshot_count",
    )
    for key in state_keys:
        if key in info:
            console.print(f"  [cyan]{key}:[/] {info[key]}")
    console.print()


def _validate_vm_params(
    *,
    name: str | None = None,
    cpu: int | None = None,
    memory_mb: int | None = None,
    disk_gb: int | None = None,
) -> None:
    """Validate VM parameter ranges. Raises typer.BadParameter on invalid input."""
    if name is not None:
        if not name or len(name) > 80:
            raise typer.BadParameter(f"VM name must be 1-80 characters, got {len(name or '')}.")
        if name.startswith("-") or name.startswith("."):
            raise typer.BadParameter("VM name must not start with '-' or '.'.")
    if cpu is not None and not (1 <= cpu <= 128):
        raise typer.BadParameter(f"CPU count must be 1-128, got {cpu}.")
    if memory_mb is not None and not (128 <= memory_mb <= 1_048_576):
        raise typer.BadParameter(f"Memory must be 128-1048576 MB, got {memory_mb}.")
    if disk_gb is not None and not (1 <= disk_gb <= 65_536):
        raise typer.BadParameter(f"Disk size must be 1-65536 GB, got {disk_gb}.")


def _double_confirm(action: str, vm_name: str, target: str = "default") -> None:
    """Require two confirmations for destructive operations.

    Logs a 'rejected' audit entry if the user declines at either step.
    """
    console.print(f"[bold yellow]⚠️  即将执行: {action} VM '{vm_name}'[/]")
    try:
        typer.confirm(f"第 1 次确认: 确定要{action} '{vm_name}'?", abort=True)
        typer.confirm(f"第 2 次确认: 再次确认{action} '{vm_name}'，此操作不可撤销?", abort=True)
    except typer.Abort:
        _audit.log(
            target=target,
            operation=action,
            resource=vm_name,
            result="rejected",
        )
        raise


# ─── Inventory ────────────────────────────────────────────────────────────────


@inventory_app.command("vms")
def inventory_vms(
    target: TargetOption = None,
    config: ConfigOption = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n", help="Max VMs to show")] = None,
    sort_by: Annotated[str, typer.Option("--sort-by", help="Sort by: name|cpu|memory_mb|power_state")] = "name",
    power_state: Annotated[str | None, typer.Option("--power-state", help="Filter: poweredOn|poweredOff|suspended")] = None,
) -> None:
    """List virtual machines."""
    from vmware_aiops.ops.inventory import list_vms

    si, _ = _get_connection(target, config)
    result = list_vms(si, limit=limit, sort_by=sort_by, power_state=power_state)
    vms = result["vms"]
    total = result["total"]
    mode = result["mode"]
    hint = result["hint"]
    title = f"Virtual Machines ({total} total"
    if mode == "compact":
        title += ", compact mode"
    title += ")"
    if power_state:
        title += f" [{power_state}]"
    if limit:
        title += f" (top {limit})"
    table = Table(title=title)
    table.add_column("Name", style="cyan")
    table.add_column("Power")
    table.add_column("CPUs", justify="right")
    table.add_column("Memory (MB)", justify="right")
    if mode == "full":
        table.add_column("Guest OS")
        table.add_column("IP Address")
    for vm in vms:
        power_style = "green" if vm["power_state"] == "poweredOn" else "red"
        row = [
            vm["name"],
            f"[{power_style}]{vm['power_state']}[/]",
            str(vm.get("cpu", "-")),
            str(vm.get("memory_mb", "-")),
        ]
        if mode == "full":
            row.append(vm.get("guest_os", "-"))
            row.append(vm.get("ip_address") or "-")
        table.add_row(*row)
    console.print(table)
    if hint:
        console.print(f"[yellow]ℹ {hint}[/yellow]")


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
    dry_run: DryRunOption = False,
) -> None:
    """Power on a VM."""
    from vmware_aiops.ops.vm_lifecycle import power_on_vm

    si, _ = _get_connection(target, config)
    if dry_run:
        from vmware_aiops.ops.vm_lifecycle import get_vm_info
        before = get_vm_info(si, name)
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="power_on",
            api_call="vim.VirtualMachine.PowerOn()",
            before_state={"power_state": before.get("power_state")},
            expected_after={"power_state": "poweredOn"},
        )
        return
    result = power_on_vm(si, name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="power_on",
        resource=name,
        after_state={"power_state": "poweredOn"},
        result=result,
    )


@vm_app.command("power-off")
def vm_power_off(
    name: str,
    force: Annotated[bool, typer.Option(help="Force power off")] = False,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Power off a VM (graceful shutdown or force)."""
    from vmware_aiops.ops.vm_lifecycle import get_vm_info, power_off_vm

    si, _ = _get_connection(target, config)
    before = get_vm_info(si, name)
    if dry_run:
        api = "vim.VirtualMachine.PowerOff()" if force else "vim.VirtualMachine.ShutdownGuest()"
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="power_off",
            api_call=api, parameters={"force": force},
            before_state={"power_state": before.get("power_state")},
            expected_after={"power_state": "poweredOff"},
        )
        return
    _show_state_preview(before, "关机", name)
    _double_confirm("关机", name, _resolve_target(target))
    result = power_off_vm(si, name, force=force)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="power_off",
        resource=name,
        parameters={"force": force},
        before_state={"power_state": before.get("power_state")},
        after_state={"power_state": "poweredOff"},
        result=result,
    )


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
    dry_run: DryRunOption = False,
) -> None:
    """Create a new VM."""
    from vmware_aiops.ops.vm_lifecycle import create_vm

    _validate_vm_params(name=name, cpu=cpu, memory_mb=memory, disk_gb=disk)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="create_vm",
            api_call="vim.Folder.CreateVM_Task()",
            parameters={"cpu": cpu, "memory_mb": memory, "disk_gb": disk, "network": network,
                         "datastore": datastore or "(auto)", "folder": folder or "(root)"},
        )
        return
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
    _audit.log(
        target=_resolve_target(target),
        operation="create_vm",
        resource=name,
        parameters={"cpu": cpu, "memory_mb": memory, "disk_gb": disk, "network": network},
        result=result,
    )


@vm_app.command("delete")
def vm_delete(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a VM (destructive!)."""
    from vmware_aiops.ops.vm_lifecycle import delete_vm, get_vm_info

    si, _ = _get_connection(target, config)
    before = get_vm_info(si, name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="delete_vm",
            api_call="vim.VirtualMachine.Destroy_Task()",
            before_state={
                "power_state": before.get("power_state"),
                "cpu": before.get("cpu"),
                "memory_mb": before.get("memory_mb"),
                "snapshot_count": before.get("snapshot_count"),
            },
        )
        return
    _show_state_preview(before, "删除", name)
    _double_confirm("删除", name, _resolve_target(target))
    result = delete_vm(si, name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="delete_vm",
        resource=name,
        before_state={
            "power_state": before.get("power_state"),
            "cpu": before.get("cpu"),
            "memory_mb": before.get("memory_mb"),
            "snapshot_count": before.get("snapshot_count"),
        },
        result=result,
    )


@vm_app.command("reconfigure")
def vm_reconfigure(
    name: str,
    cpu: Annotated[int | None, typer.Option(help="New CPU count")] = None,
    memory: Annotated[int | None, typer.Option(help="New memory in MB")] = None,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Reconfigure VM CPU/memory."""
    from vmware_aiops.ops.vm_lifecycle import get_vm_info, reconfigure_vm

    _validate_vm_params(cpu=cpu, memory_mb=memory)
    si, _ = _get_connection(target, config)
    before = get_vm_info(si, name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="reconfigure_vm",
            api_call="vim.VirtualMachine.ReconfigVM_Task()",
            parameters={"cpu": cpu or "(unchanged)", "memory_mb": memory or "(unchanged)"},
            before_state={"cpu": before.get("cpu"), "memory_mb": before.get("memory_mb")},
            expected_after={
                "cpu": cpu or before.get("cpu"),
                "memory_mb": memory or before.get("memory_mb"),
            },
        )
        return
    _show_state_preview(before, "调整配置", name)

    changes = []
    if cpu is not None:
        changes.append(f"CPU→{cpu}")
    if memory is not None:
        changes.append(f"内存→{memory}MB")

    proposed_cpu = cpu or before.get("cpu")
    proposed_mem = memory or before.get("memory_mb")
    console.print(
        f"[bold yellow]  Proposed: CPU={proposed_cpu}, "
        f"Memory={proposed_mem}MB[/]"
    )
    _double_confirm(f"调整配置({', '.join(changes)})", name, _resolve_target(target))
    result = reconfigure_vm(si, name, cpu=cpu, memory_mb=memory)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="reconfigure_vm",
        resource=name,
        parameters={"cpu": cpu, "memory_mb": memory},
        before_state={"cpu": before.get("cpu"), "memory_mb": before.get("memory_mb")},
        after_state={
            "cpu": cpu or before.get("cpu"),
            "memory_mb": memory or before.get("memory_mb"),
        },
        result=result,
    )


@vm_app.command("snapshot-create")
def vm_snapshot_create(
    vm_name: str,
    snap_name: Annotated[str, typer.Option("--name", help="Snapshot name")] = "snapshot",
    description: Annotated[str, typer.Option(help="Snapshot description")] = "",
    memory: Annotated[bool, typer.Option(help="Include memory")] = True,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a VM snapshot."""
    from vmware_aiops.ops.vm_lifecycle import create_snapshot

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=vm_name, operation="snapshot_create",
            api_call="vim.VirtualMachine.CreateSnapshot_Task()",
            parameters={"snap_name": snap_name, "description": description, "memory": memory},
        )
        return
    si, _ = _get_connection(target, config)
    result = create_snapshot(si, vm_name, snap_name, description, memory)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="snapshot_create",
        resource=vm_name,
        parameters={"snap_name": snap_name, "description": description, "memory": memory},
        result=result,
    )


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
    dry_run: DryRunOption = False,
) -> None:
    """Revert VM to a snapshot."""
    from vmware_aiops.ops.vm_lifecycle import get_vm_info, revert_to_snapshot

    si, _ = _get_connection(target, config)
    before = get_vm_info(si, vm_name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=vm_name, operation="snapshot_revert",
            api_call="vim.vm.Snapshot.RevertToSnapshot_Task()",
            parameters={"snap_name": snap_name},
            before_state={"power_state": before.get("power_state")},
        )
        return
    _show_state_preview(before, "恢复快照", vm_name)
    console.print(f"[bold yellow]  Snapshot: {snap_name}[/]")
    _double_confirm(f"恢复快照 '{snap_name}'", vm_name, _resolve_target(target))
    result = revert_to_snapshot(si, vm_name, snap_name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="snapshot_revert",
        resource=vm_name,
        parameters={"snap_name": snap_name},
        before_state={"power_state": before.get("power_state")},
        result=result,
    )


@vm_app.command("snapshot-delete")
def vm_snapshot_delete(
    vm_name: str,
    snap_name: Annotated[str, typer.Option("--name", help="Snapshot name to delete")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete a VM snapshot."""
    from vmware_aiops.ops.vm_lifecycle import delete_snapshot

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=vm_name, operation="snapshot_delete",
            api_call="vim.vm.Snapshot.RemoveSnapshot_Task()",
            parameters={"snap_name": snap_name},
        )
        return
    si, _ = _get_connection(target, config)
    console.print(f"[bold yellow]⚠️  即将删除 VM '{vm_name}' 的快照 '{snap_name}'[/]")
    _double_confirm(f"删除快照 '{snap_name}'", vm_name, _resolve_target(target))
    result = delete_snapshot(si, vm_name, snap_name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="snapshot_delete",
        resource=vm_name,
        parameters={"snap_name": snap_name},
        result=result,
    )


@vm_app.command("clone")
def vm_clone(
    name: str,
    new_name: Annotated[str, typer.Option("--new-name", help="Name for the clone")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Clone a VM."""
    from vmware_aiops.ops.vm_lifecycle import clone_vm, get_vm_info

    si, _ = _get_connection(target, config)
    before = get_vm_info(si, name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="clone_vm",
            api_call="vim.VirtualMachine.Clone()",
            parameters={"new_name": new_name},
            before_state={"cpu": before.get("cpu"), "memory_mb": before.get("memory_mb")},
        )
        return
    _show_state_preview(before, "克隆", name)
    console.print(f"[bold yellow]  Clone name: {new_name}[/]")
    _double_confirm(f"克隆为 '{new_name}'", name, _resolve_target(target))
    result = clone_vm(si, name, new_name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="clone_vm",
        resource=name,
        parameters={"new_name": new_name},
        before_state={"cpu": before.get("cpu"), "memory_mb": before.get("memory_mb")},
        result=result,
    )


@vm_app.command("migrate")
def vm_migrate(
    name: str,
    to_host: Annotated[str, typer.Option("--to-host", help="Target ESXi host name")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Migrate (vMotion) a VM to another host."""
    from vmware_aiops.ops.vm_lifecycle import get_vm_info, migrate_vm

    si, _ = _get_connection(target, config)
    before = get_vm_info(si, name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="migrate_vm",
            api_call="vim.VirtualMachine.Relocate()",
            parameters={"to_host": to_host},
            before_state={"host": before.get("host")},
            expected_after={"host": to_host},
        )
        return
    _show_state_preview(before, "迁移", name)
    console.print(f"[bold yellow]  Target host: {to_host}[/]")
    _double_confirm(f"迁移到 '{to_host}'", name, _resolve_target(target))
    result = migrate_vm(si, name, to_host)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="migrate_vm",
        resource=name,
        parameters={"to_host": to_host},
        before_state={"host": before.get("host")},
        after_state={"host": to_host},
        result=result,
    )


# ─── TTL & Clean Slate ────────────────────────────────────────────────────────


@vm_app.command("set-ttl")
def vm_set_ttl(
    vm_name: str,
    minutes: Annotated[int, typer.Option("--minutes", "-m", help="Minutes until auto-deletion")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Set a TTL for a VM. The daemon will auto-delete it when time expires."""
    from vmware_aiops.ops.ttl import set_ttl

    result = set_ttl(vm_name, minutes, target=target)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="vm_set_ttl",
        resource=vm_name,
        parameters={"minutes": minutes},
        result=result,
    )


@vm_app.command("cancel-ttl")
def vm_cancel_ttl(vm_name: str) -> None:
    """Cancel an existing TTL for a VM."""
    from vmware_aiops.ops.ttl import cancel_ttl

    result = cancel_ttl(vm_name)
    console.print(f"[yellow]{result}[/]")


@vm_app.command("list-ttl")
def vm_list_ttl() -> None:
    """List all VMs with TTLs registered."""
    from vmware_aiops.ops.ttl import list_ttl

    entries = list_ttl()
    if not entries:
        console.print("[yellow]No TTLs registered.[/]")
        return
    table = Table(title="VM TTL Registry")
    table.add_column("VM Name", style="cyan")
    table.add_column("Expires At (UTC)")
    table.add_column("Remaining (min)", justify="right")
    table.add_column("Target")
    table.add_column("Status")
    for e in entries:
        status = "[red]EXPIRED[/]" if e["expired"] else "[green]active[/]"
        table.add_row(
            e["vm_name"],
            e["expires_at"],
            str(e["remaining_minutes"]),
            e["target"] or "(default)",
            status,
        )
    console.print(table)


@vm_app.command("clean-slate")
def vm_clean_slate(
    vm_name: str,
    snapshot: Annotated[str, typer.Option("--snapshot", "-s", help="Snapshot name")] = "baseline",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Revert VM to baseline snapshot (Clean Slate). Powers off first if needed."""
    from vmware_aiops.ops.vm_lifecycle import clean_slate, get_vm_info

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=vm_name, operation="clean_slate",
            api_call="vim.VirtualMachine.PowerOff() + RevertToSnapshot_Task()",
            parameters={"snapshot": snapshot},
        )
        return
    si, _ = _get_connection(target, config)
    before = get_vm_info(si, vm_name)
    _show_state_preview(before, "Clean Slate (恢复基线快照)", vm_name)
    console.print(f"[bold yellow]  Snapshot: {snapshot}[/]")
    _double_confirm(f"恢复基线快照 '{snapshot}'", vm_name, _resolve_target(target))
    result = clean_slate(si, vm_name, snapshot_name=snapshot)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target),
        operation="clean_slate",
        resource=vm_name,
        parameters={"snapshot": snapshot},
        before_state={"power_state": before.get("power_state")},
        result=result,
    )


# ─── Guest Operations ────────────────────────────────────────────────────────


@vm_app.command("guest-exec")
def vm_guest_exec_cmd(
    vm_name: Annotated[str, typer.Argument(help="VM name")],
    command: Annotated[str, typer.Option("--cmd", help="Full path to program (e.g. /bin/bash)")],
    arguments: Annotated[str, typer.Option("--args", help="Command arguments")] = "",
    username: Annotated[str, typer.Option("--user", "-u", help="Guest OS username")] = "root",
    password: Annotated[str, typer.Option("--password", "-p", help="Guest OS password", prompt=True, hide_input=True)] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Execute a command inside a VM via VMware Tools."""
    from vmware_aiops.ops.guest_ops import guest_exec

    si, _ = _get_connection(target, config)
    result = guest_exec(si, vm_name, command, username, password, arguments=arguments)
    _audit.log(
        target=_resolve_target(target),
        operation="guest_exec",
        resource=vm_name,
        result=f"exit_code={result['exit_code']}",
    )
    table = Table(title=f"Guest Exec: {vm_name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Command", result["command"])
    table.add_row("PID", str(result["pid"]))
    exit_style = "green" if result["exit_code"] == 0 else "red"
    table.add_row("Exit Code", f"[{exit_style}]{result['exit_code']}[/]")
    table.add_row("Timed Out", str(result["timed_out"]))
    console.print(table)


@vm_app.command("guest-upload")
def vm_guest_upload_cmd(
    vm_name: Annotated[str, typer.Argument(help="VM name")],
    local_path: Annotated[str, typer.Option("--local", help="Local file path")],
    guest_path: Annotated[str, typer.Option("--guest", help="Destination path inside VM")],
    username: Annotated[str, typer.Option("--user", "-u", help="Guest OS username")] = "root",
    password: Annotated[str, typer.Option("--password", "-p", help="Guest OS password", prompt=True, hide_input=True)] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Upload a file to a VM via VMware Tools."""
    from vmware_aiops.ops.guest_ops import guest_upload

    si, _ = _get_connection(target, config)
    result = guest_upload(si, vm_name, local_path, guest_path, username, password)
    _audit.log(
        target=_resolve_target(target),
        operation="guest_upload",
        resource=vm_name,
        result=result,
    )
    console.print(f"[green]✓ {result}[/green]")


@vm_app.command("guest-download")
def vm_guest_download_cmd(
    vm_name: Annotated[str, typer.Argument(help="VM name")],
    guest_path: Annotated[str, typer.Option("--guest", help="File path inside VM")],
    local_path: Annotated[str, typer.Option("--local", help="Local destination path")],
    username: Annotated[str, typer.Option("--user", "-u", help="Guest OS username")] = "root",
    password: Annotated[str, typer.Option("--password", "-p", help="Guest OS password", prompt=True, hide_input=True)] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Download a file from a VM via VMware Tools."""
    from vmware_aiops.ops.guest_ops import guest_download

    si, _ = _get_connection(target, config)
    result = guest_download(si, vm_name, guest_path, local_path, username, password)
    _audit.log(
        target=_resolve_target(target),
        operation="guest_download",
        resource=vm_name,
        result=result,
    )
    console.print(f"[green]✓ {result}[/green]")


# ─── Datastore ───────────────────────────────────────────────────────────────


@datastore_app.command("browse")
def ds_browse(
    name: Annotated[str, typer.Argument(help="Datastore name")],
    path: Annotated[str, typer.Option(help="Subdirectory path")] = "",
    pattern: Annotated[str, typer.Option(help="File pattern (e.g. *.ova)")] = "*",
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Browse files in a datastore."""
    from vmware_aiops.ops.datastore_browser import browse_datastore

    si, _ = _get_connection(target, config)
    files = browse_datastore(si, name, path=path, pattern=pattern)
    if not files:
        console.print("[yellow]No files found.[/]")
        return
    table = Table(title=f"Datastore: {name}")
    table.add_column("Name", style="cyan")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Type")
    table.add_column("Modified")
    table.add_column("Path")
    for f in files:
        table.add_row(f["name"], str(f["size_mb"]), f["type"], f["modified"][:19], f["ds_path"])
    console.print(table)


@datastore_app.command("scan-images")
def ds_scan_images(
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Scan all datastores for deployable images (OVA/ISO/OVF) and update local registry."""
    from vmware_aiops.ops.datastore_browser import update_registry

    si, _ = _get_connection(target, config)
    console.print("[bold]Scanning all datastores for images...[/]")
    registry = update_registry(si)
    images = registry.get("images", [])
    if not images:
        console.print("[yellow]No deployable images found.[/]")
        return
    table = Table(title=f"Image Registry ({len(images)} images)")
    table.add_column("Datastore", style="cyan")
    table.add_column("Name")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Type")
    table.add_column("Path")
    for img in images:
        table.add_row(img["datastore"], img["name"], str(img["size_mb"]),
                       img["type"], img["ds_path"])
    console.print(table)
    console.print(f"[green]Registry saved. Last scan: {registry['last_scan']}[/]")


@datastore_app.command("images")
def ds_list_images(
    image_type: Annotated[str, typer.Option("--type", help="Filter: ova, iso, ovf, vmdk")] = "",
    datastore: Annotated[str, typer.Option("--ds", help="Filter by datastore")] = "",
) -> None:
    """List images from local registry (run scan-images first)."""
    from vmware_aiops.ops.datastore_browser import list_images

    images = list_images(
        image_type=image_type or None,
        datastore=datastore or None,
    )
    if not images:
        console.print("[yellow]No images in registry. Run 'datastore scan-images' first.[/]")
        return
    table = Table(title="Available Images")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Datastore", style="cyan")
    table.add_column("Name")
    table.add_column("Size (MB)", justify="right")
    table.add_column("DS Path")
    for i, img in enumerate(images, 1):
        table.add_row(str(i), img["datastore"], img["name"],
                       str(img["size_mb"]), img["ds_path"])
    console.print(table)


# ─── Deploy ──────────────────────────────────────────────────────────────────


@deploy_app.command("ova")
def deploy_ova_cmd(
    ova_path: Annotated[str, typer.Argument(help="Local path to .ova file")],
    name: Annotated[str, typer.Option(help="VM name")],
    datastore: Annotated[str, typer.Option(help="Target datastore")],
    network: Annotated[str, typer.Option(help="Network name")] = "VM Network",
    folder: Annotated[str, typer.Option(help="VM folder path")] = "",
    power_on: Annotated[bool, typer.Option("--power-on", help="Power on after deploy")] = False,
    snapshot: Annotated[str, typer.Option(help="Create baseline snapshot")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Deploy a VM from an OVA file."""
    from vmware_aiops.ops.vm_deploy import deploy_ova

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="deploy_ova",
            api_call="OvfManager.CreateImportSpec() + ImportVApp()",
            parameters={"ova": ova_path, "datastore": datastore, "network": network},
        )
        return
    si, _ = _get_connection(target, config)
    _double_confirm("部署 OVA", name, _resolve_target(target))
    result = deploy_ova(
        si, ova_path=ova_path, vm_name=name,
        datastore_name=datastore, network_name=network,
        folder_path=folder or None,
        power_on=power_on, snapshot_name=snapshot or None,
    )
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="deploy_ova",
        resource=name, parameters={"ova": ova_path, "datastore": datastore},
        result=result,
    )


@deploy_app.command("template")
def deploy_template_cmd(
    template_name: Annotated[str, typer.Argument(help="Source template name")],
    name: Annotated[str, typer.Option(help="New VM name")],
    datastore: Annotated[str, typer.Option(help="Target datastore")] = "",
    cpu: Annotated[int | None, typer.Option(help="CPU count override")] = None,
    memory: Annotated[int | None, typer.Option(help="Memory (MB) override")] = None,
    power_on: Annotated[bool, typer.Option("--power-on")] = False,
    snapshot: Annotated[str, typer.Option(help="Create baseline snapshot")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Deploy a VM from a vSphere template."""
    from vmware_aiops.ops.vm_deploy import deploy_from_template

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="deploy_template",
            api_call="vim.VirtualMachine.Clone()",
            parameters={"template": template_name, "datastore": datastore or "(template default)"},
        )
        return
    si, _ = _get_connection(target, config)
    _double_confirm(f"从模板 '{template_name}' 部署", name, _resolve_target(target))
    result = deploy_from_template(
        si, template_name=template_name, new_name=name,
        datastore_name=datastore or None, cpu=cpu, memory_mb=memory,
        power_on=power_on, snapshot_name=snapshot or None,
    )
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="deploy_template",
        resource=name, parameters={"template": template_name},
        result=result,
    )


@deploy_app.command("linked-clone")
def deploy_linked_clone_cmd(
    source: Annotated[str, typer.Option(help="Source VM name")],
    snap: Annotated[str, typer.Option("--snapshot", help="Source snapshot name")],
    name: Annotated[str, typer.Option(help="New VM name")],
    cpu: Annotated[int | None, typer.Option(help="CPU count")] = None,
    memory: Annotated[int | None, typer.Option(help="Memory (MB)")] = None,
    power_on: Annotated[bool, typer.Option("--power-on")] = False,
    baseline: Annotated[str, typer.Option(help="Create baseline snapshot on clone")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a linked clone from a VM snapshot (instant, minimal disk)."""
    from vmware_aiops.ops.vm_deploy import linked_clone

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="linked_clone",
            api_call="vim.VirtualMachine.Clone(diskMoveType=createNewChildDiskBacking)",
            parameters={"source": source, "snapshot": snap},
        )
        return
    si, _ = _get_connection(target, config)
    _double_confirm(f"从 '{source}@{snap}' 创建链接克隆", name, _resolve_target(target))
    result = linked_clone(
        si, source_vm_name=source, new_name=name, snapshot_name=snap,
        cpu=cpu, memory_mb=memory, power_on=power_on,
        baseline_snapshot=baseline or None,
    )
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="linked_clone",
        resource=name, parameters={"source": source, "snapshot": snap},
        result=result,
    )


@deploy_app.command("batch")
def deploy_batch_cmd(
    spec: Annotated[str, typer.Argument(help="Path to deploy.yaml spec file")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Batch deploy VMs from a YAML specification file."""
    from vmware_aiops.ops.vm_deploy import batch_deploy, load_deploy_spec

    if dry_run:
        deploy_spec = load_deploy_spec(spec)
        vm_names = [v["name"] for v in deploy_spec["vms"]]
        _dry_run_print(
            target=_resolve_target(target), vm_name=", ".join(vm_names),
            operation="batch_deploy",
            api_call="Multiple VM operations per spec",
            parameters={"spec_file": spec, "vm_count": len(vm_names)},
        )
        return
    si, _ = _get_connection(target, config)
    deploy_spec = load_deploy_spec(spec)
    vm_names = [v["name"] for v in deploy_spec["vms"]]
    console.print(f"[bold yellow]批量部署 {len(vm_names)} 台 VM: {', '.join(vm_names)}[/]")
    _double_confirm(f"批量部署 {len(vm_names)} 台 VM", ", ".join(vm_names), _resolve_target(target))
    results = batch_deploy(si, spec)

    # Display results
    table = Table(title="Batch Deploy Results")
    table.add_column("VM", style="cyan")
    table.add_column("Status")
    table.add_column("Details")
    for r in results:
        status_style = "green" if r["status"] == "ok" else "red"
        table.add_row(
            r["name"],
            f"[{status_style}]{r['status']}[/]",
            " | ".join(r.get("messages", [])),
        )
    console.print(table)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    console.print(f"[bold]Result: {ok_count}/{len(results)} VMs deployed successfully.[/]")
    _audit.log(
        target=_resolve_target(target), operation="batch_deploy",
        resource=spec,
        parameters={"vm_count": len(results), "ok_count": ok_count},
        result=f"{ok_count}/{len(results)} OK",
    )


@deploy_app.command("batch-clone")
def deploy_batch_clone_cmd(
    source: Annotated[str, typer.Option(help="Source VM name")],
    prefix: Annotated[str, typer.Option(help="VM name prefix")] = "vm",
    count: Annotated[int, typer.Option(help="Number of clones")] = 1,
    cpu: Annotated[int | None, typer.Option(help="CPU count")] = None,
    memory: Annotated[int | None, typer.Option(help="Memory (MB)")] = None,
    snapshot: Annotated[str, typer.Option(help="Create baseline snapshot")] = "",
    power_on: Annotated[bool, typer.Option("--power-on")] = False,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Batch clone VMs from a source VM (gold image)."""
    from vmware_aiops.ops.vm_deploy import batch_clone

    vm_names = [f"{prefix}-{i:02d}" for i in range(1, count + 1)]
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=", ".join(vm_names),
            operation="batch_clone",
            api_call="vim.VirtualMachine.Clone() x N",
            parameters={"source": source, "count": count, "prefix": prefix},
        )
        return
    si, _ = _get_connection(target, config)
    console.print(f"[bold yellow]批量克隆 {count} 台: {', '.join(vm_names)}[/]")
    _double_confirm(f"从 '{source}' 批量克隆 {count} 台", source, _resolve_target(target))
    results = batch_clone(
        si, source_vm_name=source, vm_names=vm_names,
        cpu=cpu, memory_mb=memory,
        snapshot_name=snapshot or None, power_on=power_on,
    )

    table = Table(title="Batch Clone Results")
    table.add_column("VM", style="cyan")
    table.add_column("Status")
    table.add_column("Details")
    for r in results:
        status_style = "green" if r["status"] == "ok" else "red"
        table.add_row(r["name"], f"[{status_style}]{r['status']}[/]",
                       " | ".join(r.get("messages", [])))
    console.print(table)
    _audit.log(
        target=_resolve_target(target), operation="batch_clone",
        resource=source, parameters={"count": count, "prefix": prefix},
        result=f"{sum(1 for r in results if r['status'] == 'ok')}/{len(results)} OK",
    )


@deploy_app.command("mark-template")
def deploy_mark_template(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Convert a powered-off VM to a vSphere template."""
    from vmware_aiops.ops.vm_deploy import convert_to_template

    si, _ = _get_connection(target, config)
    _double_confirm("转换为模板", name, _resolve_target(target))
    result = convert_to_template(si, name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="mark_template",
        resource=name, result=result,
    )


@deploy_app.command("iso")
def deploy_iso_cmd(
    vm_name: Annotated[str, typer.Argument(help="VM name")],
    iso: Annotated[str, typer.Option(help="ISO datastore path, e.g. '[ds1] iso/ubuntu.iso'")],
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Attach an ISO to a VM's CD-ROM drive."""
    from vmware_aiops.ops.vm_deploy import attach_iso

    si, _ = _get_connection(target, config)
    result = attach_iso(si, vm_name, iso)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="attach_iso",
        resource=vm_name, parameters={"iso": iso}, result=result,
    )


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


# ─── Plan ─────────────────────────────────────────────────────────────────────


plan_app = typer.Typer(help="Plan → Apply: view and manage operation plans.")
app.add_typer(plan_app, name="plan")


@plan_app.command("list")
def plan_list() -> None:
    """List all pending/failed operation plans."""
    from vmware_aiops.ops.planner import list_plans

    plans = list_plans()
    if not plans:
        console.print("[dim]No plans found.[/dim]")
        return
    table = Table(title="Operation Plans")
    table.add_column("Plan ID", style="cyan")
    table.add_column("Created", style="dim")
    table.add_column("Status")
    table.add_column("Steps", justify="right")
    table.add_column("VMs Affected")
    for p in plans:
        status_style = "green" if p["status"] == "pending" else "red"
        table.add_row(
            p["plan_id"],
            p["created_at"],
            f"[{status_style}]{p['status']}[/]",
            str(p["total_steps"]),
            ", ".join(p["vms_affected"]),
        )
    console.print(table)


# ─── MCP Config Generator ────────────────────────────────────────────────────

mcp_config_app = typer.Typer(help="Generate MCP server config for local AI agents.")
app.add_typer(mcp_config_app, name="mcp-config")

_AGENT_TEMPLATES = {
    "goose": "goose.json",
    "cursor": "cursor.json",
    "claude-code": "claude-code.json",
    "continue": "continue.yaml",
    "vscode-copilot": "vscode-copilot.json",
    "localcowork": "localcowork.json",
    "mcp-agent": "mcp-agent.yaml",
}

_TEMPLATES_DIR = Path(__file__).parent.parent / "examples" / "mcp-configs"


@mcp_config_app.command("generate")
def mcp_config_generate(
    agent: Annotated[
        str,
        typer.Option(
            "--agent",
            "-a",
            help=(
                "Target agent: goose, cursor, claude-code, continue, "
                "vscode-copilot, localcowork, mcp-agent"
            ),
        ),
    ],
    install_path: Annotated[
        str | None,
        typer.Option("--path", help="Absolute path to VMware-AIops install dir"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write config to this file path"),
    ] = None,
) -> None:
    """Generate MCP server config for a local AI agent.

    Prints the ready-to-use config to stdout (or writes to --output file).
    Replace /path/to/VMware-AIops with your actual installation directory.

    Example:
        vmware-aiops mcp-config generate --agent goose
    """
    agent_lower = agent.lower()
    if agent_lower not in _AGENT_TEMPLATES:
        available = ", ".join(sorted(_AGENT_TEMPLATES.keys()))
        console.print(f"[red]Unknown agent '{agent}'. Available: {available}[/]")
        raise typer.Exit(1)

    template_file = _TEMPLATES_DIR / _AGENT_TEMPLATES[agent_lower]
    if not template_file.exists():
        console.print(f"[red]Template file not found: {template_file}[/]")
        raise typer.Exit(1)

    content = template_file.read_text()

    # Replace placeholder with actual path if provided
    if install_path:
        abs_path = str(Path(install_path).resolve())
        content = content.replace("/path/to/VMware-AIops", abs_path)
    else:
        # Try to resolve from package location
        pkg_dir = Path(__file__).parent.parent.resolve()
        # Only substitute if it looks like a real install (has pyproject.toml)
        if (pkg_dir / "pyproject.toml").exists():
            content = content.replace("/path/to/VMware-AIops", str(pkg_dir))

    if output:
        output.write_text(content)
        console.print(f"[green]Config written to: {output}[/]")
    else:
        console.print(content)


@mcp_config_app.command("list")
def mcp_config_list() -> None:
    """List all supported agents."""
    table = Table(title="Supported Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Template File")
    for agent_name, template in sorted(_AGENT_TEMPLATES.items()):
        table.add_row(agent_name, template)
    console.print(table)


@app.command("doctor")
def doctor_cmd(
    skip_auth: Annotated[
        bool,
        typer.Option("--skip-auth", help="Skip vSphere authentication check (faster)"),
    ] = False,
) -> None:
    """Check environment, config, connectivity, and daemon status."""
    import sys
    from vmware_aiops.doctor import run_doctor
    exit_code = run_doctor(skip_auth=skip_auth)
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
