"""iSCSI configuration: enable adapter, manage targets, rescan storage."""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.ops.inventory import find_host_by_name

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


class HostNotFoundError(Exception):
    """Raised when a host is not found by name."""


class ISCSIError(Exception):
    """Raised on iSCSI operation failures."""


def _require_host(si: ServiceInstance, host_name: str) -> vim.HostSystem:
    """Find a host or raise HostNotFoundError."""
    host = find_host_by_name(si, host_name)
    if host is None:
        raise HostNotFoundError(f"Host '{host_name}' not found")
    return host


def _validate_address(address: str) -> None:
    """Validate IP address format."""
    try:
        ipaddress.ip_address(address)
    except ValueError:
        raise ISCSIError(f"Invalid IP address: '{address}'") from None


def _validate_port(port: int) -> None:
    """Validate port range."""
    if not (1 <= port <= 65535):
        raise ISCSIError(f"Port must be 1-65535, got {port}")


def _get_storage_system(host: vim.HostSystem) -> vim.host.StorageSystem:
    """Get the host storage system manager."""
    ss = host.configManager.storageSystem
    if ss is None:
        raise ISCSIError(f"Storage system not available on host '{host.name}'")
    return ss


def _get_iscsi_hba(host: vim.HostSystem) -> vim.host.InternetScsiHba | None:
    """Find the software iSCSI HBA from host bus adapters."""
    storage_device = host.config.storageDevice
    if not storage_device or not storage_device.hostBusAdapter:
        return None
    for hba in storage_device.hostBusAdapter:
        if isinstance(hba, vim.host.InternetScsiHba) and hba.isSoftwareBased:
            return hba
    return None


# ─── Enable ───────────────────────────────────────────────────────────────────


def enable_software_iscsi(si: ServiceInstance, host_name: str) -> str:
    """Enable the software iSCSI adapter on a host."""
    host = _require_host(si, host_name)
    storage_system = _get_storage_system(host)

    # Check if already enabled
    hba = _get_iscsi_hba(host)
    if hba is not None:
        return (
            f"Software iSCSI is already enabled on host '{host_name}' "
            f"(HBA: {hba.device}, IQN: {hba.iScsiName})."
        )

    storage_system.UpdateSoftwareInternetScsiEnabled(enabled=True)
    return f"Software iSCSI enabled on host '{host_name}'."


# ─── Status ───────────────────────────────────────────────────────────────────


def get_iscsi_status(si: ServiceInstance, host_name: str) -> dict:
    """Get iSCSI adapter status and configured targets."""
    host = _require_host(si, host_name)
    hba = _get_iscsi_hba(host)

    if hba is None:
        return {
            "host": host_name,
            "enabled": False,
            "hba_device": None,
            "iqn": None,
            "send_targets": [],
        }

    targets = []
    if hba.configuredSendTarget:
        for t in hba.configuredSendTarget:
            targets.append({
                "address": t.address,
                "port": t.port,
            })

    return {
        "host": host_name,
        "enabled": True,
        "hba_device": hba.device,
        "iqn": hba.iScsiName,
        "send_targets": targets,
    }


# ─── Target Management ───────────────────────────────────────────────────────


def add_iscsi_target(
    si: ServiceInstance,
    host_name: str,
    address: str,
    port: int = 3260,
) -> str:
    """Add an iSCSI send target and rescan."""
    _validate_address(address)
    _validate_port(port)

    host = _require_host(si, host_name)
    hba = _get_iscsi_hba(host)
    if hba is None:
        raise ISCSIError(
            f"Software iSCSI is not enabled on host '{host_name}'. "
            "Enable it first with: vmware-aiops storage iscsi-enable"
        )

    # Check for duplicate
    if hba.configuredSendTarget:
        for t in hba.configuredSendTarget:
            if t.address == address and t.port == port:
                return f"iSCSI target {address}:{port} already configured on '{host_name}'."

    storage_system = _get_storage_system(host)
    target = vim.host.InternetScsiHba.SendTarget(address=address, port=port)
    storage_system.AddInternetScsiSendTargets(
        iScsiHbaDevice=hba.device,
        targets=[target],
    )

    # Rescan after adding target
    storage_system.RescanAllHba()
    storage_system.RescanVmfs()

    return f"iSCSI target {address}:{port} added to host '{host_name}' and storage rescanned."


def remove_iscsi_target(
    si: ServiceInstance,
    host_name: str,
    address: str,
    port: int = 3260,
) -> str:
    """Remove an iSCSI send target and rescan."""
    _validate_address(address)
    _validate_port(port)

    host = _require_host(si, host_name)
    hba = _get_iscsi_hba(host)
    if hba is None:
        raise ISCSIError(f"Software iSCSI is not enabled on host '{host_name}'.")

    # Check target exists
    found = False
    if hba.configuredSendTarget:
        for t in hba.configuredSendTarget:
            if t.address == address and t.port == port:
                found = True
                break
    if not found:
        raise ISCSIError(f"iSCSI target {address}:{port} not found on host '{host_name}'.")

    storage_system = _get_storage_system(host)
    target = vim.host.InternetScsiHba.SendTarget(address=address, port=port)
    storage_system.RemoveInternetScsiSendTargets(
        iScsiHbaDevice=hba.device,
        targets=[target],
    )

    # Rescan after removing target
    storage_system.RescanAllHba()
    storage_system.RescanVmfs()

    return f"iSCSI target {address}:{port} removed from host '{host_name}' and storage rescanned."


# ─── Rescan ───────────────────────────────────────────────────────────────────


def rescan_storage(si: ServiceInstance, host_name: str) -> str:
    """Rescan all HBAs and VMFS volumes on a host."""
    host = _require_host(si, host_name)
    storage_system = _get_storage_system(host)

    storage_system.RescanAllHba()
    storage_system.RescanVmfs()

    return f"Storage rescan completed on host '{host_name}'."
