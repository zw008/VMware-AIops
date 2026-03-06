"""VM deployment: all fast-provisioning channels for VM creation.

Channels:
1. OVA import — deploy from OVA file (local or datastore)
2. ISO attach — create empty VM + mount ISO
3. Full clone — full copy from source VM
4. Linked clone — instant clone from snapshot (shared base disk, COW delta)
5. Template deploy — clone from vSphere template
6. Batch deploy — YAML spec for multiple VMs via any channel above

Composes existing VM lifecycle operations (create, clone, snapshot, power)
with new OVA/ISO/linked-clone/template capabilities.
"""

from __future__ import annotations

import logging
import tarfile
import time
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

import yaml
from pyVmomi import vim

from vmware_aiops.ops.inventory import (
    find_datastore_by_name,
    find_vm_by_name,
)
from vmware_aiops.ops.vm_lifecycle import (
    _wait_for_task,
    clone_vm,
    create_snapshot,
    create_vm,
    power_on_vm,
    reconfigure_vm,
)

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-aiops.deploy")


# ─── OVA Deploy ──────────────────────────────────────────────────────────────


def _safe_tar_member(member: tarfile.TarInfo) -> bool:
    """Reject tar members with path traversal attempts (CVE-2007-4559)."""
    return not (member.name.startswith("/") or ".." in member.name)


def _read_ovf_from_ova(ova_path: str) -> tuple[str, dict[str, int]]:
    """Extract OVF descriptor and disk file info from an OVA (tar archive).

    Args:
        ova_path: Local file path to the .ova file.

    Returns:
        Tuple of (ovf_xml_string, {vmdk_filename: file_size_bytes})
    """
    disks: dict[str, int] = {}
    ovf_content = ""

    with tarfile.open(ova_path, "r") as tar:
        for member in tar.getmembers():
            if not _safe_tar_member(member):
                _log.warning("Skipping unsafe tar member: %s", member.name)
                continue
            if member.name.endswith(".ovf"):
                f = tar.extractfile(member)
                if f:
                    ovf_content = f.read().decode("utf-8")
            elif member.name.endswith((".vmdk", ".img")):
                disks[member.name] = member.size

    if not ovf_content:
        raise ValueError(f"No .ovf descriptor found in OVA: {ova_path}")

    return ovf_content, disks


def _upload_disk(
    lease: vim.HttpNfcLease,
    ova_path: str,
    disk_name: str,
    upload_url: str,
    disk_size: int,
) -> None:
    """Upload a VMDK from an OVA to the vSphere HTTP NFC lease URL."""
    with tarfile.open(ova_path, "r") as tar:
        member = tar.getmember(disk_name)
        if not _safe_tar_member(member):
            raise ValueError(f"Unsafe tar member path: {disk_name}")
        f = tar.extractfile(member)
        if f is None:
            raise ValueError(f"Cannot extract {disk_name} from OVA")

        data = f.read()

    # Validate upload URL scheme — only HTTPS allowed (B310)
    if not upload_url.lower().startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS upload URL: {upload_url}")

    req = Request(
        upload_url,
        data=data,
        method="PUT",
        headers={
            "Content-Type": "application/x-vnd.vmware-streamVmdk",
            "Content-Length": str(len(data)),
        },
    )

    # SSL verification disabled for ESXi self-signed certificates only
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # nosec B501 — ESXi self-signed certs

    urlopen(req, context=ctx)  # nosec B310 — scheme validated above


def deploy_ova(
    si: ServiceInstance,
    ova_path: str,
    vm_name: str,
    datastore_name: str,
    network_name: str = "VM Network",
    folder_path: str | None = None,
    power_on: bool = False,
    snapshot_name: str | None = None,
) -> str:
    """Deploy a VM from a local OVA file.

    Flow:
    1. Parse OVF from OVA
    2. Create import spec via OvfManager
    3. Import via ResourcePool.ImportVApp
    4. Upload VMDKs via HTTP NFC lease
    5. Optionally power on + create baseline snapshot

    Args:
        si: vSphere ServiceInstance
        ova_path: Path to local .ova file
        vm_name: Desired VM name
        datastore_name: Target datastore
        network_name: Network to attach
        folder_path: VM folder path (optional)
        power_on: Power on after deploy
        snapshot_name: Create baseline snapshot with this name (optional)

    Returns:
        Status message.
    """
    content = si.RetrieveContent()

    # Find datastore
    ds = find_datastore_by_name(si, datastore_name)
    if ds is None:
        return f"Datastore '{datastore_name}' not found."

    # Find datacenter, folder, resource pool
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

    resource_pool = datacenter.hostFolder.childEntity[0].resourcePool

    # Parse OVA
    ovf_content, disks = _read_ovf_from_ova(ova_path)
    _log.info("OVA parsed: %d disk(s) found", len(disks))

    # Create import spec
    ovf_manager = content.ovfManager
    import_spec_params = vim.OvfManager.CreateImportSpecParams(
        entityName=vm_name,
    )

    # Map OVF networks to vSphere networks
    import_spec_result = ovf_manager.CreateImportSpec(
        ovfDescriptor=ovf_content,
        resourcePool=resource_pool,
        datastore=ds,
        cisp=import_spec_params,
    )

    if import_spec_result.error:
        errors = "; ".join(str(e.msg) for e in import_spec_result.error)
        return f"OVF validation failed: {errors}"

    if import_spec_result.warning:
        for w in import_spec_result.warning:
            _log.warning("OVF warning: %s", w.msg)

    # Start import
    lease = resource_pool.ImportVApp(
        spec=import_spec_result.importSpec,
        folder=vm_folder,
    )

    # Wait for lease to be ready
    timeout = 120
    start = time.time()
    while lease.state == vim.HttpNfcLease.State.initializing:
        if time.time() - start > timeout:
            return "Import lease timed out during initialization."
        time.sleep(2)

    if lease.state == vim.HttpNfcLease.State.error:
        return f"Import lease error: {lease.error.msg if lease.error else 'Unknown'}"

    # Upload disks
    try:
        device_urls = lease.info.deviceUrl
        for device_url in device_urls:
            target_url = device_url.url

            # Find the corresponding disk in OVA by order
            for disk_name, disk_size in disks.items():
                _log.info("Uploading %s (%d MB)...", disk_name,
                          disk_size // (1024 * 1024))
                _upload_disk(lease, ova_path, disk_name, target_url, disk_size)
                disks.pop(disk_name)
                break

        lease.Complete()
    except Exception as e:
        lease.Abort()
        return f"OVA deploy failed during upload: {e}"

    result_parts = [f"VM '{vm_name}' deployed from OVA successfully."]

    # Post-deploy: power on
    if power_on:
        try:
            msg = power_on_vm(si, vm_name)
            result_parts.append(msg)
        except Exception as e:
            result_parts.append(f"Power on failed: {e}")

    # Post-deploy: create baseline snapshot
    if snapshot_name:
        try:
            msg = create_snapshot(si, vm_name, snapshot_name,
                                  description="Baseline snapshot for sandbox",
                                  memory=False)
            result_parts.append(msg)
        except Exception as e:
            result_parts.append(f"Snapshot creation failed: {e}")

    return " | ".join(result_parts)


# ─── ISO Attach ──────────────────────────────────────────────────────────────


def attach_iso(
    si: ServiceInstance,
    vm_name: str,
    iso_ds_path: str,
) -> str:
    """Attach an ISO from a datastore to a VM's CD-ROM drive.

    Args:
        si: vSphere ServiceInstance
        vm_name: Target VM name
        iso_ds_path: Datastore path e.g. "[datastore1] iso/ubuntu.iso"

    Returns:
        Status message.
    """
    vm = find_vm_by_name(si, vm_name)
    if vm is None:
        return f"VM '{vm_name}' not found."

    # Find existing CD-ROM or create one
    cdrom = None
    ide_controller = None
    if vm.config and vm.config.hardware:
        for dev in vm.config.hardware.device:
            if isinstance(dev, vim.vm.device.VirtualCdrom):
                cdrom = dev
            elif isinstance(dev, vim.vm.device.VirtualIDEController):
                ide_controller = dev

    if cdrom:
        # Reconfigure existing CD-ROM to use ISO backing
        cdrom_spec = vim.vm.device.VirtualDeviceSpec(
            operation=vim.vm.device.VirtualDeviceSpec.Operation.edit,
            device=vim.vm.device.VirtualCdrom(
                key=cdrom.key,
                controllerKey=cdrom.controllerKey,
                unitNumber=cdrom.unitNumber,
                backing=vim.vm.device.VirtualCdrom.IsoBackingInfo(
                    fileName=iso_ds_path,
                ),
                connectable=vim.vm.device.VirtualDevice.ConnectInfo(
                    startConnected=True,
                    connected=True,
                    allowGuestControl=True,
                ),
            ),
        )
    else:
        # Add new CD-ROM device
        if ide_controller is None:
            return f"VM '{vm_name}' has no IDE controller for CD-ROM."

        cdrom_spec = vim.vm.device.VirtualDeviceSpec(
            operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
            device=vim.vm.device.VirtualCdrom(
                controllerKey=ide_controller.key,
                unitNumber=0,
                backing=vim.vm.device.VirtualCdrom.IsoBackingInfo(
                    fileName=iso_ds_path,
                ),
                connectable=vim.vm.device.VirtualDevice.ConnectInfo(
                    startConnected=True,
                    connected=True,
                    allowGuestControl=True,
                ),
            ),
        )

    config_spec = vim.vm.ConfigSpec(deviceChange=[cdrom_spec])
    task = vm.ReconfigVM_Task(spec=config_spec)
    _wait_for_task(task)
    return f"ISO '{iso_ds_path}' attached to VM '{vm_name}'."


# ─── Batch Clone ─────────────────────────────────────────────────────────────


def batch_clone(
    si: ServiceInstance,
    source_vm_name: str,
    vm_names: list[str],
    cpu: int | None = None,
    memory_mb: int | None = None,
    snapshot_name: str | None = None,
    power_on: bool = False,
) -> list[dict]:
    """Clone multiple VMs from a source VM (gold image).

    For each clone:
    1. Clone from source
    2. Reconfigure CPU/memory (if specified)
    3. Create baseline snapshot (if specified)
    4. Power on (if specified)

    Returns:
        List of result dicts with name, status, message.
    """
    source = find_vm_by_name(si, source_vm_name)
    if source is None:
        return [{"name": source_vm_name, "status": "error",
                 "message": f"Source VM '{source_vm_name}' not found."}]

    results: list[dict] = []
    for name in vm_names:
        result = {"name": name, "status": "ok", "messages": []}
        try:
            # 1. Clone
            msg = clone_vm(si, source_vm_name, name)
            result["messages"].append(msg)

            # 2. Reconfigure
            if cpu is not None or memory_mb is not None:
                msg = reconfigure_vm(si, name, cpu=cpu, memory_mb=memory_mb)
                result["messages"].append(msg)

            # 3. Snapshot
            if snapshot_name:
                msg = create_snapshot(si, name, snapshot_name,
                                      description="Baseline snapshot",
                                      memory=False)
                result["messages"].append(msg)

            # 4. Power on
            if power_on:
                msg = power_on_vm(si, name)
                result["messages"].append(msg)

        except Exception as e:
            result["status"] = "error"
            result["messages"].append(str(e))

        results.append(result)
        _log.info("Batch clone %s: %s", name, result["status"])

    return results


# ─── Linked Clone (from snapshot, instant) ───────────────────────────────────


def linked_clone(
    si: ServiceInstance,
    source_vm_name: str,
    new_name: str,
    snapshot_name: str,
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    baseline_snapshot: str | None = None,
) -> str:
    """Create a linked clone from a VM snapshot.

    Linked clones share the base disk with the source VM and use a
    copy-on-write (COW) delta disk. This makes creation near-instant
    and uses minimal disk space.

    Requirements:
    - Source VM must have at least one snapshot.
    - The named snapshot must exist.

    Args:
        source_vm_name: Source VM to clone from.
        new_name: Name for the new linked clone.
        snapshot_name: Snapshot to use as the clone base.
        cpu: Override CPU count (optional).
        memory_mb: Override memory (optional).
        power_on: Power on after creation.
        baseline_snapshot: Create a new snapshot on the clone (optional).
    """
    from vmware_aiops.ops.vm_lifecycle import list_snapshots

    source = find_vm_by_name(si, source_vm_name)
    if source is None:
        return f"Source VM '{source_vm_name}' not found."

    # Find the snapshot
    snaps = list_snapshots(si, source_vm_name)
    target_snap = next((s for s in snaps if s["name"] == snapshot_name), None)
    if target_snap is None:
        available = ", ".join(s["name"] for s in snaps) or "none"
        return f"Snapshot '{snapshot_name}' not found. Available: {available}"

    # Linked clone spec: use snapshot as disk move type
    relocate_spec = vim.vm.RelocateSpec(
        diskMoveType=vim.vm.RelocateSpec.DiskMoveOptions.createNewChildDiskBacking,
    )
    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        template=False,
        snapshot=target_snap["snapshot_ref"],
    )

    folder = source.parent
    task = source.Clone(folder=folder, name=new_name, spec=clone_spec)
    _wait_for_task(task, timeout=300)
    result_parts = [
        f"Linked clone '{new_name}' created from "
        f"'{source_vm_name}' @ snapshot '{snapshot_name}'."
    ]

    # Reconfigure
    if cpu is not None or memory_mb is not None:
        msg = reconfigure_vm(si, new_name, cpu=cpu, memory_mb=memory_mb)
        result_parts.append(msg)

    # Baseline snapshot on clone
    if baseline_snapshot:
        msg = create_snapshot(si, new_name, baseline_snapshot,
                              description="Baseline snapshot", memory=False)
        result_parts.append(msg)

    # Power on
    if power_on:
        msg = power_on_vm(si, new_name)
        result_parts.append(msg)

    return " | ".join(result_parts)


# ─── Template Operations ────────────────────────────────────────────────────


def convert_to_template(si: ServiceInstance, vm_name: str) -> str:
    """Convert a VM to a vSphere template.

    The VM must be powered off. After conversion, it cannot be powered on
    directly — it can only be used as a clone source.
    """
    vm = find_vm_by_name(si, vm_name)
    if vm is None:
        return f"VM '{vm_name}' not found."

    if vm.runtime.powerState != vim.VirtualMachine.PowerState.poweredOff:
        return f"VM '{vm_name}' must be powered off before converting to template."

    vm.MarkAsTemplate()
    return f"VM '{vm_name}' converted to template."


def convert_to_vm(
    si: ServiceInstance,
    template_name: str,
    host_name: str | None = None,
) -> str:
    """Convert a template back to a regular VM."""
    from vmware_aiops.ops.inventory import find_host_by_name

    vm = find_vm_by_name(si, template_name)
    if vm is None:
        return f"Template '{template_name}' not found."

    if not vm.config.template:
        return f"'{template_name}' is already a VM, not a template."

    # Need a resource pool — find from host or use first available
    content = si.RetrieveContent()
    if host_name:
        host = find_host_by_name(si, host_name)
        if host is None:
            return f"Host '{host_name}' not found."
        pool = host.parent.resourcePool
    else:
        datacenter = content.rootFolder.childEntity[0]
        pool = datacenter.hostFolder.childEntity[0].resourcePool

    vm.MarkAsVirtualMachine(pool=pool)
    return f"Template '{template_name}' converted back to VM."


def deploy_from_template(
    si: ServiceInstance,
    template_name: str,
    new_name: str,
    datastore_name: str | None = None,
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    snapshot_name: str | None = None,
) -> str:
    """Deploy a new VM by cloning from a vSphere template.

    Args:
        template_name: Name of the source template.
        new_name: Name for the new VM.
        datastore_name: Target datastore (optional, uses template's if omitted).
        cpu: Override CPU count (optional).
        memory_mb: Override memory (optional).
        power_on: Power on after deploy.
        snapshot_name: Create baseline snapshot (optional).
    """
    template = find_vm_by_name(si, template_name)
    if template is None:
        return f"Template '{template_name}' not found."

    if not template.config.template:
        return f"'{template_name}' is not a template. Use 'clone' instead."

    relocate_spec = vim.vm.RelocateSpec()
    if datastore_name:
        ds = find_datastore_by_name(si, datastore_name)
        if ds is None:
            return f"Datastore '{datastore_name}' not found."
        relocate_spec.datastore = ds

    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        template=False,
    )

    folder = template.parent
    task = template.Clone(folder=folder, name=new_name, spec=clone_spec)
    _wait_for_task(task, timeout=600)
    result_parts = [f"VM '{new_name}' deployed from template '{template_name}'."]

    # Reconfigure
    if cpu is not None or memory_mb is not None:
        msg = reconfigure_vm(si, new_name, cpu=cpu, memory_mb=memory_mb)
        result_parts.append(msg)

    # Baseline snapshot
    if snapshot_name:
        msg = create_snapshot(si, new_name, snapshot_name,
                              description="Baseline snapshot", memory=False)
        result_parts.append(msg)

    # Power on
    if power_on:
        msg = power_on_vm(si, new_name)
        result_parts.append(msg)

    return " | ".join(result_parts)


# ─── Batch Linked Clone ─────────────────────────────────────────────────────


def batch_linked_clone(
    si: ServiceInstance,
    source_vm_name: str,
    snapshot_name: str,
    vm_names: list[str],
    cpu: int | None = None,
    memory_mb: int | None = None,
    power_on: bool = False,
    baseline_snapshot: str | None = None,
) -> list[dict]:
    """Create multiple linked clones from a source VM snapshot.

    This is the fastest batch provisioning method — each clone shares the
    source disk and only stores delta changes.
    """
    results: list[dict] = []
    for name in vm_names:
        result = {"name": name, "status": "ok", "messages": []}
        try:
            msg = linked_clone(
                si, source_vm_name, name, snapshot_name,
                cpu=cpu, memory_mb=memory_mb,
                power_on=power_on, baseline_snapshot=baseline_snapshot,
            )
            result["messages"].append(msg)
        except Exception as e:
            result["status"] = "error"
            result["messages"].append(str(e))
        results.append(result)
    return results


# ─── Batch Deploy from YAML ─────────────────────────────────────────────────


def load_deploy_spec(spec_path: str) -> dict:
    """Load and validate a YAML deployment spec.

    Expected format:
    ```yaml
    defaults:
      cpu: 4
      memory_mb: 8192
      disk_gb: 100
      network: "VM Network"
      datastore: datastore1
      snapshot: clean-slate
      power_on: true

    # Provisioning channel (pick one):
    #   source: golden-vm             # Full clone from VM
    #   template: ubuntu-template     # Clone from vSphere template
    #   linked_clone:                 # Linked clone (fastest)
    #     source: golden-vm
    #     snapshot: clean-state

    vms:
      - name: sandbox-01
      - name: sandbox-02
        cpu: 8
        memory_mb: 16384
      - name: sandbox-win-01
        guest_id: windows2019srv_64Guest
        iso: "[datastore1] iso/win2022.iso"
        ova: /path/to/image.ova       # Per-VM OVA override
    ```
    """
    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    if not spec or "vms" not in spec:
        raise ValueError(f"Invalid deploy spec: missing 'vms' section in {spec_path}")

    return spec


def batch_deploy(
    si: ServiceInstance,
    spec_path: str,
) -> list[dict]:
    """Deploy multiple VMs from a YAML specification file.

    Supports all provisioning channels:
    - Clone mode: 'source' specified → full clone from VM
    - Template mode: 'template' specified → clone from vSphere template
    - Linked clone mode: 'linked_clone' specified → instant clone from snapshot
    - OVA mode: per-VM 'ova' field → deploy from OVA file
    - Create mode: fallback → create empty VM (optionally with ISO)

    Returns:
        List of result dicts per VM.
    """
    spec = load_deploy_spec(spec_path)
    defaults = spec.get("defaults", {})
    source_vm = spec.get("source")
    template = spec.get("template")
    lc_config = spec.get("linked_clone")
    vm_specs = spec["vms"]

    results: list[dict] = []

    for vm_spec in vm_specs:
        name = vm_spec["name"]
        # Merge defaults with per-VM overrides
        cpu = vm_spec.get("cpu", defaults.get("cpu", 2))
        memory_mb = vm_spec.get("memory_mb", defaults.get("memory_mb", 4096))
        disk_gb = vm_spec.get("disk_gb", defaults.get("disk_gb", 40))
        network = vm_spec.get("network", defaults.get("network", "VM Network"))
        datastore = vm_spec.get("datastore", defaults.get("datastore"))
        snapshot = vm_spec.get("snapshot", defaults.get("snapshot"))
        do_power_on = vm_spec.get("power_on", defaults.get("power_on", False))
        iso = vm_spec.get("iso")
        ova = vm_spec.get("ova")
        guest_id = vm_spec.get("guest_id", defaults.get("guest_id", "otherGuest64"))

        result = {"name": name, "status": "ok", "messages": []}

        try:
            if ova:
                # OVA mode (per-VM)
                msg = deploy_ova(
                    si, ova_path=ova, vm_name=name,
                    datastore_name=datastore or "",
                    network_name=network,
                )
                result["messages"].append(msg)

            elif lc_config:
                # Linked clone mode (fastest)
                msg = linked_clone(
                    si, source_vm_name=lc_config["source"],
                    new_name=name,
                    snapshot_name=lc_config["snapshot"],
                    cpu=cpu, memory_mb=memory_mb,
                )
                result["messages"].append(msg)

            elif template:
                # Template mode
                msg = deploy_from_template(
                    si, template_name=template, new_name=name,
                    datastore_name=datastore, cpu=cpu, memory_mb=memory_mb,
                )
                result["messages"].append(msg)

            elif source_vm:
                # Full clone mode
                msg = clone_vm(si, source_vm, name)
                result["messages"].append(msg)
                if cpu or memory_mb:
                    msg = reconfigure_vm(si, name, cpu=cpu, memory_mb=memory_mb)
                    result["messages"].append(msg)

            else:
                # Create empty VM mode
                msg = create_vm(
                    si, vm_name=name, cpu=cpu, memory_mb=memory_mb,
                    disk_gb=disk_gb, network_name=network,
                    datastore_name=datastore, guest_id=guest_id,
                )
                result["messages"].append(msg)

            # Attach ISO if specified (works with all modes)
            if iso:
                msg = attach_iso(si, name, iso)
                result["messages"].append(msg)

            # Create baseline snapshot
            if snapshot:
                msg = create_snapshot(si, name, snapshot,
                                      description="Baseline snapshot",
                                      memory=False)
                result["messages"].append(msg)

            # Power on
            if do_power_on:
                msg = power_on_vm(si, name)
                result["messages"].append(msg)

        except Exception as e:
            result["status"] = "error"
            result["messages"].append(str(e))

        results.append(result)
        _log.info("Batch deploy %s: %s", name, result["status"])

    return results
