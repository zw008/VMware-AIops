"""VM lifecycle operations: create, delete, power, snapshot, clone, migrate."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.ops.inventory import (
    find_datastore_by_name,
    find_host_by_name,
    find_vm_by_name,
)

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


class VMNotFoundError(Exception):
    """Raised when a VM is not found by name."""


class TaskFailedError(Exception):
    """Raised when a vSphere task fails."""


def _wait_for_task(task, timeout: int = 300) -> object:
    """Wait for a vSphere task to complete."""
    start = time.time()
    while task.info.state in (vim.TaskInfo.State.running, vim.TaskInfo.State.queued):
        if time.time() - start > timeout:
            raise TimeoutError(f"Task timed out after {timeout}s")
        time.sleep(2)

    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result
    error_msg = str(task.info.error.msg) if task.info.error else "Unknown error"
    raise TaskFailedError(f"Task failed: {error_msg}")


def _require_vm(si: ServiceInstance, vm_name: str) -> vim.VirtualMachine:
    """Find a VM or raise VMNotFoundError."""
    vm = find_vm_by_name(si, vm_name)
    if vm is None:
        raise VMNotFoundError(f"VM '{vm_name}' not found")
    return vm


# ─── Info ─────────────────────────────────────────────────────────────────────


def get_vm_info(si: ServiceInstance, vm_name: str) -> dict:
    """Get detailed VM information."""
    vm = _require_vm(si, vm_name)
    config = vm.config
    guest = vm.guest
    runtime = vm.runtime

    disks = []
    nics = []
    if config and config.hardware:
        for dev in config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualDisk):
                disks.append({
                    "label": dev.deviceInfo.label,
                    "size_gb": round(dev.capacityInKB / (1024 * 1024), 1),
                    "thin": getattr(dev.backing, "thinProvisioned", None),
                })
            elif isinstance(dev, vim.vm.device.VirtualEthernetCard):
                nics.append({
                    "label": dev.deviceInfo.label,
                    "mac": dev.macAddress,
                    "connected": dev.connectable.connected if dev.connectable else False,
                    "network": dev.backing.deviceName
                    if hasattr(dev.backing, "deviceName")
                    else str(dev.backing),
                })

    return {
        "name": vm.name,
        "power_state": str(runtime.powerState),
        "cpu": config.hardware.numCPU if config else 0,
        "memory_mb": config.hardware.memoryMB if config else 0,
        "guest_os": config.guestFullName if config else "N/A",
        "guest_id": config.guestId if config else "N/A",
        "uuid": config.uuid if config else "N/A",
        "instance_uuid": config.instanceUuid if config else "N/A",
        "host": runtime.host.name if runtime.host else "N/A",
        "ip_address": guest.ipAddress if guest else None,
        "hostname": guest.hostName if guest else None,
        "tools_status": str(guest.toolsRunningStatus) if guest else "N/A",
        "tools_version": str(guest.toolsVersion) if guest and guest.toolsVersion else "N/A",
        "disks": disks,
        "nics": nics,
        "annotation": config.annotation if config and config.annotation else "",
        "snapshot_count": _count_snapshots(vm.snapshot) if vm.snapshot else 0,
    }


def _count_snapshots(snapshot_info) -> int:
    """Count total snapshots recursively."""
    count = 0
    if snapshot_info and snapshot_info.rootSnapshotList:
        for snap in snapshot_info.rootSnapshotList:
            count += 1 + _count_children(snap)
    return count


def _count_children(snap_tree) -> int:
    count = 0
    for child in snap_tree.childSnapshotList:
        count += 1 + _count_children(child)
    return count


# ─── Power Operations ────────────────────────────────────────────────────────


def power_on_vm(si: ServiceInstance, vm_name: str) -> str:
    """Power on a VM."""
    vm = _require_vm(si, vm_name)
    if vm.runtime.powerState == vim.VirtualMachine.PowerState.poweredOn:
        return f"VM '{vm_name}' is already powered on."
    task = vm.PowerOn()
    _wait_for_task(task)
    return f"VM '{vm_name}' powered on successfully."


def power_off_vm(si: ServiceInstance, vm_name: str, force: bool = False) -> str:
    """Power off a VM. Graceful (guest shutdown) by default, force if specified."""
    vm = _require_vm(si, vm_name)
    if vm.runtime.powerState == vim.VirtualMachine.PowerState.poweredOff:
        return f"VM '{vm_name}' is already powered off."

    if force:
        task = vm.PowerOff()
        _wait_for_task(task)
        return f"VM '{vm_name}' force powered off."

    # Graceful shutdown via VMware Tools
    try:
        vm.ShutdownGuest()
        # Wait for power off (no task returned for ShutdownGuest)
        for _ in range(60):
            time.sleep(2)
            if vm.runtime.powerState == vim.VirtualMachine.PowerState.poweredOff:
                return f"VM '{vm_name}' gracefully shut down."
        return f"VM '{vm_name}' shutdown initiated but still running after 120s. Use --force if needed."
    except vim.fault.ToolsUnavailable:
        return (
            f"VMware Tools not running on '{vm_name}'. "
            f"Use --force for hard power off."
        )


def reset_vm(si: ServiceInstance, vm_name: str) -> str:
    """Reset (hard reboot) a VM."""
    vm = _require_vm(si, vm_name)
    task = vm.Reset()
    _wait_for_task(task)
    return f"VM '{vm_name}' reset successfully."


def suspend_vm(si: ServiceInstance, vm_name: str) -> str:
    """Suspend a VM."""
    vm = _require_vm(si, vm_name)
    task = vm.Suspend()
    _wait_for_task(task)
    return f"VM '{vm_name}' suspended successfully."


# ─── Create / Delete ─────────────────────────────────────────────────────────


def create_vm(
    si: ServiceInstance,
    vm_name: str,
    cpu: int = 2,
    memory_mb: int = 4096,
    disk_gb: int = 40,
    network_name: str = "VM Network",
    datastore_name: str | None = None,
    folder_path: str | None = None,
    guest_id: str = "otherGuest64",
) -> str:
    """Create a new VM with basic configuration."""
    content = si.RetrieveContent()

    # Find datacenter and folder
    datacenter = content.rootFolder.childEntity[0]
    vm_folder = datacenter.vmFolder
    if folder_path:
        for part in folder_path.split("/"):
            found = False
            for child in vm_folder.childEntity:
                if hasattr(child, "childEntity") and child.name == part:
                    vm_folder = child
                    found = True
                    break
            if not found:
                return f"Folder '{folder_path}' not found."

    # Find resource pool
    resource_pool = datacenter.hostFolder.childEntity[0].resourcePool

    # Find datastore
    if datastore_name:
        ds = find_datastore_by_name(si, datastore_name)
        if ds is None:
            return f"Datastore '{datastore_name}' not found."
        ds_path = f"[{datastore_name}] {vm_name}"
    else:
        ds_path = f"{vm_name}"

    # VM config spec
    vmx_file = vim.vm.FileInfo(vmPathName=ds_path)

    # SCSI controller
    scsi_spec = vim.vm.device.VirtualDeviceSpec(
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.ParaVirtualSCSIController(
            key=1000,
            sharedBus=vim.vm.device.VirtualSCSIController.Sharing.noSharing,
        ),
    )

    # Disk
    disk_spec = vim.vm.device.VirtualDeviceSpec(
        fileOperation=vim.vm.device.VirtualDeviceSpec.FileOperation.create,
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.VirtualDisk(
            backing=vim.vm.device.VirtualDisk.FlatVer2BackingInfo(
                diskMode="persistent",
                thinProvisioned=True,
            ),
            capacityInKB=disk_gb * 1024 * 1024,
            controllerKey=1000,
            unitNumber=0,
        ),
    )

    # NIC
    nic_spec = vim.vm.device.VirtualDeviceSpec(
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.VirtualVmxnet3(
            backing=vim.vm.device.VirtualEthernetCard.NetworkBackingInfo(
                useAutoDetect=False,
                deviceName=network_name,
            ),
            connectable=vim.vm.device.VirtualDevice.ConnectInfo(
                startConnected=True,
                allowGuestControl=True,
                connected=True,
            ),
            addressType="assigned",
        ),
    )

    config_spec = vim.vm.ConfigSpec(
        name=vm_name,
        memoryMB=memory_mb,
        numCPUs=cpu,
        files=vmx_file,
        guestId=guest_id,
        deviceChange=[scsi_spec, disk_spec, nic_spec],
    )

    task = vm_folder.CreateVM_Task(config=config_spec, pool=resource_pool)
    _wait_for_task(task)
    return f"VM '{vm_name}' created successfully (CPU: {cpu}, Mem: {memory_mb}MB, Disk: {disk_gb}GB)."


def delete_vm(si: ServiceInstance, vm_name: str) -> str:
    """Delete a VM. Powers off first if running."""
    vm = _require_vm(si, vm_name)

    if vm.runtime.powerState == vim.VirtualMachine.PowerState.poweredOn:
        task = vm.PowerOff()
        _wait_for_task(task)

    task = vm.Destroy_Task()
    _wait_for_task(task)
    return f"VM '{vm_name}' deleted successfully."


# ─── Reconfigure ──────────────────────────────────────────────────────────────


def reconfigure_vm(
    si: ServiceInstance,
    vm_name: str,
    cpu: int | None = None,
    memory_mb: int | None = None,
) -> str:
    """Reconfigure VM CPU and/or memory. VM should be powered off for memory changes."""
    vm = _require_vm(si, vm_name)

    if cpu is None and memory_mb is None:
        return "Nothing to change. Specify --cpu and/or --memory."

    spec = vim.vm.ConfigSpec()
    changes = []
    if cpu is not None:
        spec.numCPUs = cpu
        changes.append(f"CPU: {cpu}")
    if memory_mb is not None:
        spec.memoryMB = memory_mb
        changes.append(f"Memory: {memory_mb}MB")

    task = vm.ReconfigVM_Task(spec=spec)
    _wait_for_task(task)
    return f"VM '{vm_name}' reconfigured: {', '.join(changes)}."


# ─── Snapshots ────────────────────────────────────────────────────────────────


def create_snapshot(
    si: ServiceInstance,
    vm_name: str,
    snap_name: str,
    description: str = "",
    memory: bool = True,
) -> str:
    """Create a VM snapshot."""
    vm = _require_vm(si, vm_name)
    task = vm.CreateSnapshot_Task(
        name=snap_name,
        description=description,
        memory=memory,
        quiesce=not memory,  # Can't quiesce with memory snapshot
    )
    _wait_for_task(task)
    return f"Snapshot '{snap_name}' created for VM '{vm_name}'."


def list_snapshots(si: ServiceInstance, vm_name: str) -> list[dict]:
    """List all snapshots for a VM."""
    vm = _require_vm(si, vm_name)
    if not vm.snapshot:
        return []

    results: list[dict] = []

    def _walk(snap_list, level: int = 0) -> None:
        for snap in snap_list:
            results.append({
                "name": snap.name,
                "description": snap.description,
                "created": str(snap.createTime),
                "state": str(snap.state),
                "level": level,
                "snapshot_ref": snap.snapshot,
            })
            if snap.childSnapshotList:
                _walk(snap.childSnapshotList, level + 1)

    _walk(vm.snapshot.rootSnapshotList)
    return results


def revert_to_snapshot(
    si: ServiceInstance, vm_name: str, snap_name: str
) -> str:
    """Revert VM to a named snapshot."""
    snaps = list_snapshots(si, vm_name)
    target = next((s for s in snaps if s["name"] == snap_name), None)
    if target is None:
        available = ", ".join(s["name"] for s in snaps) or "none"
        return f"Snapshot '{snap_name}' not found. Available: {available}"

    task = target["snapshot_ref"].RevertToSnapshot_Task()
    _wait_for_task(task)
    return f"VM '{vm_name}' reverted to snapshot '{snap_name}'."


def delete_snapshot(
    si: ServiceInstance,
    vm_name: str,
    snap_name: str,
    remove_children: bool = False,
) -> str:
    """Delete a named snapshot."""
    snaps = list_snapshots(si, vm_name)
    target = next((s for s in snaps if s["name"] == snap_name), None)
    if target is None:
        available = ", ".join(s["name"] for s in snaps) or "none"
        return f"Snapshot '{snap_name}' not found. Available: {available}"

    task = target["snapshot_ref"].RemoveSnapshot_Task(removeChildren=remove_children)
    _wait_for_task(task)
    return f"Snapshot '{snap_name}' deleted from VM '{vm_name}'."


# ─── Clone ────────────────────────────────────────────────────────────────────


def clone_vm(si: ServiceInstance, vm_name: str, new_name: str) -> str:
    """Clone a VM with the same configuration."""
    vm = _require_vm(si, vm_name)
    folder = vm.parent

    relocate_spec = vim.vm.RelocateSpec()
    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        template=False,
    )

    task = vm.Clone(folder=folder, name=new_name, spec=clone_spec)
    _wait_for_task(task, timeout=600)
    return f"VM '{vm_name}' cloned as '{new_name}'."


# ─── Migrate (vMotion) ───────────────────────────────────────────────────────


def migrate_vm(si: ServiceInstance, vm_name: str, target_host_name: str) -> str:
    """Migrate (vMotion) a VM to another host."""
    vm = _require_vm(si, vm_name)
    target_host = find_host_by_name(si, target_host_name)
    if target_host is None:
        return f"Target host '{target_host_name}' not found."

    current_host = vm.runtime.host.name if vm.runtime.host else "unknown"
    if current_host == target_host_name:
        return f"VM '{vm_name}' is already on host '{target_host_name}'."

    relocate_spec = vim.vm.RelocateSpec(
        host=target_host,
        pool=target_host.parent.resourcePool,
    )

    task = vm.Relocate(spec=relocate_spec)
    _wait_for_task(task, timeout=600)
    return f"VM '{vm_name}' migrated from '{current_host}' to '{target_host_name}'."
