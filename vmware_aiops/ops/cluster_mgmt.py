"""Cluster management: create, delete, configure HA/DRS, add/remove hosts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.ops.inventory import (
    find_cluster_by_name,
    find_datacenter_by_name,
    find_host_by_name,
)
from vmware_aiops.ops.vm_lifecycle import _wait_for_task

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


class ClusterNotFoundError(Exception):
    """Raised when a cluster is not found by name."""


class ClusterError(Exception):
    """Raised on cluster operation failures."""


_VALID_DRS_BEHAVIORS = {"fullyAutomated", "partiallyAutomated", "manual"}


def _require_cluster(
    si: ServiceInstance, cluster_name: str
) -> vim.ClusterComputeResource:
    """Find a cluster or raise ClusterNotFoundError."""
    cluster = find_cluster_by_name(si, cluster_name)
    if cluster is None:
        raise ClusterNotFoundError(f"Cluster '{cluster_name}' not found")
    return cluster


def _get_datacenter(si: ServiceInstance, datacenter_name: str | None = None) -> vim.Datacenter:
    """Find a datacenter by name, or return the first one."""
    if datacenter_name:
        dc = find_datacenter_by_name(si, datacenter_name)
        if dc is None:
            raise ClusterError(f"Datacenter '{datacenter_name}' not found")
        return dc
    content = si.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if isinstance(child, vim.Datacenter):
            return child
    raise ClusterError("No datacenter found in inventory")


# ─── Info ─────────────────────────────────────────────────────────────────────


def get_cluster_info(si: ServiceInstance, cluster_name: str) -> dict:
    """Get detailed cluster information."""
    cluster = _require_cluster(si, cluster_name)
    cfg = cluster.configuration

    hosts = []
    for host in cluster.host or []:
        hosts.append({
            "name": host.name,
            "connection_state": str(host.runtime.connectionState),
            "power_state": str(host.runtime.powerState),
            "maintenance_mode": host.runtime.inMaintenanceMode,
        })

    return {
        "name": cluster.name,
        "host_count": len(cluster.host or []),
        "hosts": hosts,
        "ha_enabled": cfg.dasConfig.enabled if cfg.dasConfig else False,
        "ha_admission_control": cfg.dasConfig.admissionControlEnabled if cfg.dasConfig else False,
        "drs_enabled": cfg.drsConfig.enabled if cfg.drsConfig else False,
        "drs_behavior": str(cfg.drsConfig.defaultVmBehavior) if cfg.drsConfig else "N/A",
        "total_cpu_mhz": cluster.summary.totalCpu if cluster.summary else 0,
        "total_memory_gb": round(
            cluster.summary.totalMemory / (1024**3)
        ) if cluster.summary and cluster.summary.totalMemory else 0,
        "effective_cpu_mhz": cluster.summary.effectiveCpu if cluster.summary else 0,
        "effective_memory_gb": round(
            cluster.summary.effectiveMemory / 1024
        ) if cluster.summary and cluster.summary.effectiveMemory else 0,
    }


# ─── Create / Delete ─────────────────────────────────────────────────────────


def create_cluster(
    si: ServiceInstance,
    cluster_name: str,
    datacenter_name: str | None = None,
    ha_enabled: bool = False,
    drs_enabled: bool = False,
    drs_behavior: str = "fullyAutomated",
) -> str:
    """Create a new cluster in the specified datacenter."""
    if drs_behavior not in _VALID_DRS_BEHAVIORS:
        raise ClusterError(
            f"Invalid DRS behavior '{drs_behavior}'. "
            f"Valid: {sorted(_VALID_DRS_BEHAVIORS)}"
        )

    # Check if cluster already exists
    existing = find_cluster_by_name(si, cluster_name)
    if existing is not None:
        raise ClusterError(f"Cluster '{cluster_name}' already exists")

    dc = _get_datacenter(si, datacenter_name)

    spec = vim.cluster.ConfigSpecEx(
        dasConfig=vim.cluster.DasConfigInfo(
            enabled=ha_enabled,
        ),
        drsConfig=vim.cluster.DrsConfigInfo(
            enabled=drs_enabled,
            defaultVmBehavior=vim.cluster.DrsConfigInfo.DrsBehavior(drs_behavior),
        ),
    )

    dc.hostFolder.CreateClusterEx(name=cluster_name, spec=spec)

    features = []
    if ha_enabled:
        features.append("HA")
    if drs_enabled:
        features.append(f"DRS({drs_behavior})")
    feature_str = f" with {', '.join(features)}" if features else ""

    return f"Cluster '{cluster_name}' created{feature_str}."


def delete_cluster(si: ServiceInstance, cluster_name: str) -> str:
    """Delete an empty cluster."""
    cluster = _require_cluster(si, cluster_name)

    if cluster.host and len(cluster.host) > 0:
        host_names = [h.name for h in cluster.host]
        raise ClusterError(
            f"Cluster '{cluster_name}' still has {len(cluster.host)} host(s): "
            f"{', '.join(host_names)}. Remove all hosts before deleting."
        )

    task = cluster.Destroy_Task()
    _wait_for_task(task)
    return f"Cluster '{cluster_name}' deleted."


# ─── Host Management ─────────────────────────────────────────────────────────


def add_host_to_cluster(
    si: ServiceInstance,
    cluster_name: str,
    host_name: str,
) -> str:
    """Move an already-managed host into a cluster.

    The host must already be in vCenter inventory (standalone or in another cluster).
    To add a brand-new host to vCenter, use the vCenter UI or AddHost_Task API.
    """
    cluster = _require_cluster(si, cluster_name)
    host = find_host_by_name(si, host_name)
    if host is None:
        raise ClusterError(f"Host '{host_name}' not found")

    # Check if already in this cluster
    for h in cluster.host or []:
        if h.name == host_name:
            return f"Host '{host_name}' is already in cluster '{cluster_name}'."

    task = cluster.MoveInto_Task(host=[host])
    _wait_for_task(task, timeout=300)
    return f"Host '{host_name}' moved into cluster '{cluster_name}'."


def remove_host_from_cluster(
    si: ServiceInstance,
    cluster_name: str,
    host_name: str,
) -> str:
    """Remove a host from a cluster by moving it to standalone in the datacenter host folder.

    The host must be in maintenance mode before removal.
    """
    cluster = _require_cluster(si, cluster_name)
    host = find_host_by_name(si, host_name)
    if host is None:
        raise ClusterError(f"Host '{host_name}' not found")

    # Verify host is in this cluster
    in_cluster = any(h.name == host_name for h in (cluster.host or []))
    if not in_cluster:
        raise ClusterError(f"Host '{host_name}' is not in cluster '{cluster_name}'")

    if not host.runtime.inMaintenanceMode:
        raise ClusterError(
            f"Host '{host_name}' must be in maintenance mode before removal. "
            f"Use: vmware-aiops vm guest-exec or ESXi UI to enter maintenance mode."
        )

    # Walk up from cluster to find its owning datacenter
    parent = cluster.parent
    while parent and not isinstance(parent, vim.Datacenter):
        parent = parent.parent
    if parent is None:
        raise ClusterError(f"Cannot determine datacenter for cluster '{cluster_name}'")
    dc = parent

    # Move host to datacenter's host folder as standalone
    task = dc.hostFolder.MoveInto_Task(host=[host])
    _wait_for_task(task, timeout=300)
    return f"Host '{host_name}' removed from cluster '{cluster_name}'."


# ─── Configure ────────────────────────────────────────────────────────────────


def configure_cluster(
    si: ServiceInstance,
    cluster_name: str,
    ha_enabled: bool | None = None,
    drs_enabled: bool | None = None,
    drs_behavior: str | None = None,
) -> str:
    """Reconfigure cluster HA/DRS settings."""
    if ha_enabled is None and drs_enabled is None and drs_behavior is None:
        return "Nothing to change. Specify --ha, --drs, or --drs-behavior."

    if drs_behavior is not None and drs_behavior not in _VALID_DRS_BEHAVIORS:
        raise ClusterError(
            f"Invalid DRS behavior '{drs_behavior}'. "
            f"Valid: {sorted(_VALID_DRS_BEHAVIORS)}"
        )

    cluster = _require_cluster(si, cluster_name)

    spec = vim.cluster.ConfigSpecEx()
    changes = []

    if ha_enabled is not None:
        spec.dasConfig = vim.cluster.DasConfigInfo(enabled=ha_enabled)
        changes.append(f"HA={'ON' if ha_enabled else 'OFF'}")

    if drs_enabled is not None or drs_behavior is not None:
        drs_cfg = vim.cluster.DrsConfigInfo()
        if drs_enabled is not None:
            drs_cfg.enabled = drs_enabled
            changes.append(f"DRS={'ON' if drs_enabled else 'OFF'}")
        if drs_behavior is not None:
            drs_cfg.defaultVmBehavior = vim.cluster.DrsConfigInfo.DrsBehavior(drs_behavior)
            changes.append(f"DRS behavior={drs_behavior}")
        spec.drsConfig = drs_cfg

    task = cluster.ReconfigureComputeResource_Task(spec=spec, modify=True)
    _wait_for_task(task)
    return f"Cluster '{cluster_name}' reconfigured: {', '.join(changes)}."
