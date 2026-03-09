"""Inventory queries for vCenter/ESXi resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


def _get_objects(si: ServiceInstance, obj_type: list, recursive: bool = True) -> list:
    """Generic container view helper."""
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, obj_type, recursive
    )
    try:
        return list(container.view)
    finally:
        container.Destroy()


_VM_SORT_KEYS = {"name", "cpu", "memory_mb", "power_state"}
_COMPACT_FIELDS = ("name", "power_state", "cpu", "memory_mb")


def list_vms(
    si: ServiceInstance,
    limit: int | None = None,
    sort_by: str = "name",
    power_state: str | None = None,
    fields: list[str] | None = None,
    compact_threshold: int = 50,
) -> dict:
    """List virtual machines with optional filtering, sorting, and field selection.

    Returns a dict with keys:
        total   - total VMs after filtering
        mode    - "full" or "compact" (auto-selected when total > compact_threshold)
        vms     - list of VM dicts
        hint    - optional suggestion when compact mode is auto-selected

    Auto-compact: when no explicit limit/fields are set and total VMs exceed
    compact_threshold (default 50), only compact fields are returned to keep
    context manageable. Use limit or fields to override.

    Args:
        si: vSphere ServiceInstance.
        limit: Max number of VMs to return (None = all).
        sort_by: Sort field: "name" | "cpu" | "memory_mb" | "power_state".
        power_state: Filter by power state: "poweredOn" | "poweredOff" | "suspended".
        fields: Return only these fields (None = auto).
            Available: name, power_state, cpu, memory_mb, guest_os, ip_address,
                       host, uuid, tools_status.
        compact_threshold: Auto-compact when VM count exceeds this (default 50).
    """
    vms = _get_objects(si, [vim.VirtualMachine])
    results = []
    for vm in vms:
        config = vm.config
        entry = {
            "name": vm.name,
            "power_state": str(vm.runtime.powerState),
            "cpu": config.hardware.numCPU if config else 0,
            "memory_mb": config.hardware.memoryMB if config else 0,
            "guest_os": config.guestFullName if config else "N/A",
            "ip_address": vm.guest.ipAddress if vm.guest else None,
            "host": vm.runtime.host.name if vm.runtime.host else "N/A",
            "uuid": config.uuid if config else "N/A",
            "tools_status": str(vm.guest.toolsRunningStatus) if vm.guest else "N/A",
        }
        results.append(entry)

    # Filter by power state
    if power_state:
        results = [r for r in results if power_state.lower() in r["power_state"].lower()]

    # Sort
    sort_key = sort_by if sort_by in _VM_SORT_KEYS else "name"
    results = sorted(results, key=lambda x: x[sort_key])

    total = len(results)

    # Limit
    if limit is not None and limit > 0:
        results = results[:limit]

    # Determine mode and field selection
    explicit_fields = bool(fields)
    explicit_limit = limit is not None and limit > 0

    if not explicit_fields and not explicit_limit and total > compact_threshold:
        # Auto-compact: large inventory, no explicit constraints
        mode = "compact"
        results = [{k: r[k] for k in _COMPACT_FIELDS if k in r} for r in results]
        hint = (
            f"Large inventory ({total} VMs): showing compact fields only. "
            "Use --limit N or --fields to get full details."
        )
    else:
        mode = "full"
        hint = None
        if fields:
            valid = {"name", "power_state", "cpu", "memory_mb", "guest_os",
                     "ip_address", "host", "uuid", "tools_status"}
            keep = [f for f in fields if f in valid]
            if keep:
                results = [{k: r[k] for k in keep if k in r} for r in results]

    return {"total": total, "mode": mode, "vms": results, "hint": hint}


def list_hosts(si: ServiceInstance) -> list[dict]:
    """List all ESXi hosts with basic info."""
    hosts = _get_objects(si, [vim.HostSystem])
    results = []
    for host in hosts:
        hw = host.hardware
        results.append({
            "name": host.name,
            "connection_state": str(host.runtime.connectionState),
            "power_state": str(host.runtime.powerState),
            "cpu_cores": hw.cpuInfo.numCpuCores if hw else 0,
            "cpu_threads": hw.cpuInfo.numCpuThreads if hw else 0,
            "memory_gb": round(hw.memorySize / (1024**3)) if hw else 0,
            "esxi_version": host.config.product.version if host.config else "N/A",
            "esxi_build": host.config.product.build if host.config else "N/A",
            "vm_count": len(host.vm) if host.vm else 0,
            "uptime_seconds": host.summary.quickStats.uptime or 0,
        })
    return sorted(results, key=lambda x: x["name"])


def list_datastores(si: ServiceInstance) -> list[dict]:
    """List all datastores with capacity info."""
    datastores = _get_objects(si, [vim.Datastore])
    results = []
    for ds in datastores:
        summary = ds.summary
        results.append({
            "name": ds.name,
            "type": summary.type,
            "free_gb": round(summary.freeSpace / (1024**3), 1) if summary.freeSpace else 0,
            "total_gb": round(summary.capacity / (1024**3), 1) if summary.capacity else 0,
            "accessible": summary.accessible,
            "url": summary.url,
            "vm_count": len(ds.vm) if ds.vm else 0,
        })
    return sorted(results, key=lambda x: x["name"])


def list_clusters(si: ServiceInstance) -> list[dict]:
    """List all clusters with configuration info."""
    clusters = _get_objects(si, [vim.ClusterComputeResource])
    results = []
    for cluster in clusters:
        cfg = cluster.configuration
        results.append({
            "name": cluster.name,
            "host_count": len(cluster.host) if cluster.host else 0,
            "drs_enabled": cfg.drsConfig.enabled if cfg.drsConfig else False,
            "drs_behavior": str(cfg.drsConfig.defaultVmBehavior) if cfg.drsConfig else "N/A",
            "ha_enabled": cfg.dasConfig.enabled if cfg.dasConfig else False,
            "total_cpu_mhz": cluster.summary.totalCpu if cluster.summary else 0,
            "total_memory_gb": round(
                cluster.summary.totalMemory / (1024**3)
            ) if cluster.summary and cluster.summary.totalMemory else 0,
        })
    return sorted(results, key=lambda x: x["name"])


def list_networks(si: ServiceInstance) -> list[dict]:
    """List all networks."""
    networks = _get_objects(si, [vim.Network])
    results = []
    for net in networks:
        results.append({
            "name": net.name,
            "vm_count": len(net.vm) if net.vm else 0,
            "accessible": net.summary.accessible if net.summary else True,
        })
    return sorted(results, key=lambda x: x["name"])


def find_vm_by_name(si: ServiceInstance, vm_name: str) -> vim.VirtualMachine | None:
    """Find a VM by exact name. Returns None if not found."""
    vms = _get_objects(si, [vim.VirtualMachine])
    for vm in vms:
        if vm.name == vm_name:
            return vm
    return None


def find_host_by_name(si: ServiceInstance, host_name: str) -> vim.HostSystem | None:
    """Find a host by name. Returns None if not found."""
    hosts = _get_objects(si, [vim.HostSystem])
    for host in hosts:
        if host.name == host_name:
            return host
    return None


def find_datastore_by_name(
    si: ServiceInstance, ds_name: str
) -> vim.Datastore | None:
    """Find a datastore by name. Returns None if not found."""
    datastores = _get_objects(si, [vim.Datastore])
    for ds in datastores:
        if ds.name == ds_name:
            return ds
    return None
