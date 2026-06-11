"""Cluster management commands: create, delete, configure HA/DRS, add/remove hosts."""

from __future__ import annotations

from typing import Annotated

import typer

from vmware_aiops.cli._common import (
    ConfigOption,
    DryRunOption,
    TargetOption,
    _audit,
    _double_confirm,
    _dry_run_print,
    _get_connection,
    _resolve_target,
    cli_errors,
    console,
)

cluster_app = typer.Typer(help="Cluster management: create, delete, configure HA/DRS.")


@cluster_app.command("info")
@cli_errors
def cluster_info_cmd(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
) -> None:
    """Show detailed cluster info."""
    from vmware_aiops.ops.cluster_mgmt import get_cluster_info

    si, _ = _get_connection(target, config)
    info = get_cluster_info(si, name)
    console.print(f"\n[bold cyan]Cluster '{name}':[/]")
    for k, v in info.items():
        if k == "hosts":
            console.print(f"  [cyan]hosts:[/]")
            for h in v:
                state_style = "green" if h["connection_state"] == "connected" else "red"
                maint = " [yellow](maintenance)[/]" if h["maintenance_mode"] else ""
                console.print(
                    f"    - {h['name']} [{state_style}]{h['connection_state']}[/]{maint}"
                )
        else:
            console.print(f"  [cyan]{k}:[/] {v}")


@cluster_app.command("create")
@cli_errors
def cluster_create_cmd(
    name: str,
    ha: Annotated[bool, typer.Option("--ha", help="Enable HA")] = False,
    drs: Annotated[bool, typer.Option("--drs", help="Enable DRS")] = False,
    drs_behavior: Annotated[
        str, typer.Option("--drs-behavior", help="DRS behavior: fullyAutomated|partiallyAutomated|manual")
    ] = "fullyAutomated",
    datacenter: Annotated[str, typer.Option(help="Datacenter name")] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Create a new cluster."""
    from vmware_aiops.ops.cluster_mgmt import create_cluster

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="create_cluster",
            api_call="datacenter.hostFolder.CreateClusterEx()",
            parameters={"ha": ha, "drs": drs, "drs_behavior": drs_behavior},
            resource_label="Cluster",
        )
        return
    si, _ = _get_connection(target, config)
    result = create_cluster(
        si, cluster_name=name, datacenter_name=datacenter or None,
        ha_enabled=ha, drs_enabled=drs, drs_behavior=drs_behavior,
    )
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="create_cluster",
        resource=name, parameters={"ha": ha, "drs": drs, "drs_behavior": drs_behavior},
        result=result,
    )


@cluster_app.command("delete")
@cli_errors
def cluster_delete_cmd(
    name: str,
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Delete an empty cluster (destructive!)."""
    from vmware_aiops.ops.cluster_mgmt import get_cluster_info, delete_cluster

    si, _ = _get_connection(target, config)
    info = get_cluster_info(si, name)
    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="delete_cluster",
            api_call="cluster.Destroy_Task()",
            before_state={"host_count": info["host_count"], "ha": info["ha_enabled"], "drs": info["drs_enabled"]},
            resource_label="Cluster",
        )
        return
    _double_confirm("删除集群", name, _resolve_target(target), resource_type="Cluster")
    result = delete_cluster(si, name)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="delete_cluster",
        resource=name, before_state=info, result=result,
    )


@cluster_app.command("add-host")
@cli_errors
def cluster_add_host_cmd(
    name: str,
    host: Annotated[str, typer.Option("--host", help="Host name to add")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Move a host into a cluster."""
    from vmware_aiops.ops.cluster_mgmt import add_host_to_cluster

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="cluster_add_host",
            api_call="cluster.MoveInto_Task()",
            parameters={"host": host},
            resource_label="Cluster",
        )
        return
    si, _ = _get_connection(target, config)
    _double_confirm("添加主机到集群", f"{host} → {name}", _resolve_target(target), resource_type="Host")
    result = add_host_to_cluster(si, cluster_name=name, host_name=host)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="cluster_add_host",
        resource=name, parameters={"host": host}, result=result,
    )


@cluster_app.command("remove-host")
@cli_errors
def cluster_remove_host_cmd(
    name: str,
    host: Annotated[str, typer.Option("--host", help="Host name to remove")],
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Remove a host from a cluster (host must be in maintenance mode)."""
    from vmware_aiops.ops.cluster_mgmt import remove_host_from_cluster

    if dry_run:
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="cluster_remove_host",
            api_call="datacenter.hostFolder.MoveIntoFolder_Task(list=[host])",
            parameters={"host": host},
            resource_label="Cluster",
        )
        return
    si, _ = _get_connection(target, config)
    _double_confirm("从集群移除主机", f"{host} ← {name}", _resolve_target(target), resource_type="Host")
    result = remove_host_from_cluster(si, cluster_name=name, host_name=host)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="cluster_remove_host",
        resource=name, parameters={"host": host}, result=result,
    )


@cluster_app.command("configure")
@cli_errors
def cluster_configure_cmd(
    name: str,
    ha: Annotated[bool | None, typer.Option("--ha/--no-ha", help="Enable/disable HA")] = None,
    drs: Annotated[bool | None, typer.Option("--drs/--no-drs", help="Enable/disable DRS")] = None,
    drs_behavior: Annotated[
        str, typer.Option("--drs-behavior", help="DRS behavior: fullyAutomated|partiallyAutomated|manual")
    ] = "",
    target: TargetOption = None,
    config: ConfigOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Configure cluster HA/DRS settings."""
    from vmware_aiops.ops.cluster_mgmt import configure_cluster, get_cluster_info

    params = {}
    if ha is not None:
        params["ha_enabled"] = ha
    if drs is not None:
        params["drs_enabled"] = drs
    if drs_behavior:
        params["drs_behavior"] = drs_behavior

    si, _ = _get_connection(target, config)
    if dry_run:
        before = get_cluster_info(si, name)
        _dry_run_print(
            target=_resolve_target(target), vm_name=name, operation="configure_cluster",
            api_call="cluster.ReconfigureComputeResource_Task()",
            parameters=params,
            before_state={"ha": before["ha_enabled"], "drs": before["drs_enabled"], "drs_behavior": before["drs_behavior"]},
            resource_label="Cluster",
        )
        return
    _double_confirm("重新配置集群", name, _resolve_target(target), resource_type="Cluster")
    result = configure_cluster(si, cluster_name=name, **params)
    console.print(f"[green]{result}[/]")
    _audit.log(
        target=_resolve_target(target), operation="configure_cluster",
        resource=name, parameters=params, result=result,
    )
