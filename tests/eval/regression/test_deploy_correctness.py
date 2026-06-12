"""Regression tests — four P1 correctness bugs (GitHub #18/#19/#20/#21).

- #20: create_snapshot forced quiesce=not memory, so memory=False demanded a
  quiesced snapshot that fails (ApplicationQuiesceFault) on freshly-deployed
  VMs without running VMware Tools. quiesce is now an explicit param (False).
- #21: datacenter/compute-resource lookup assumed rootFolder.childEntity[0] is
  the target DC and its hostFolder.childEntity[0] is a ComputeResource —
  multi-DC picks the wrong DC, a top-level folder crashes, empty inventory
  IndexErrors. Now resolved by explicit vim.Datacenter / vim.ComputeResource
  search.
- #18: _upload_disk slurped the whole VMDK via f.read() and never posted lease
  progress, so vCenter aborted the lease on large/slow uploads. Now streams in
  fixed-size chunks and reports HttpNfcLeaseProgress.
- #19: OVA device URLs were mapped to disks by pop-order, ignoring importKey —
  multi-disk OVAs could write to the wrong device. Now matched by importKey via
  import_spec_result.fileItem.
"""

from __future__ import annotations

import tarfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pyVmomi import vim


# ── #20: create_snapshot must not force quiesce when memory=False ──


def test_create_snapshot_memory_false_does_not_force_quiesce() -> None:
    """memory=False must NOT imply quiesce=True. The old code set
    quiesce=not memory, breaking snapshots of VMs without VMware Tools."""
    from vmware_aiops.ops import vm_lifecycle

    vm = MagicMock()
    with patch.object(vm_lifecycle, "_require_vm", return_value=vm), \
         patch.object(vm_lifecycle, "_wait_for_task"):
        vm_lifecycle.create_snapshot(MagicMock(), "vm1", "snap", memory=False)

    _, kwargs = vm.CreateSnapshot_Task.call_args
    assert kwargs["quiesce"] is False, (
        "memory=False must default quiesce to False, not force it True"
    )
    assert kwargs["memory"] is False


def test_create_snapshot_quiesce_is_explicit_opt_in() -> None:
    """Quiesce is available as an explicit opt-in parameter."""
    from vmware_aiops.ops import vm_lifecycle

    vm = MagicMock()
    with patch.object(vm_lifecycle, "_require_vm", return_value=vm), \
         patch.object(vm_lifecycle, "_wait_for_task"):
        vm_lifecycle.create_snapshot(
            MagicMock(), "vm1", "snap", memory=False, quiesce=True
        )

    _, kwargs = vm.CreateSnapshot_Task.call_args
    assert kwargs["quiesce"] is True


# ── #21: explicit datacenter / compute-resource resolution ──


def _make_si(root_children):
    si = MagicMock()
    si.RetrieveContent.return_value.rootFolder.childEntity = root_children
    return si


def test_resolve_datacenter_selects_right_dc_by_name_multi_dc() -> None:
    """Multi-DC inventory must select the named DC, not childEntity[0]."""
    from vmware_aiops.ops import inventory

    dc_a = MagicMock(spec=vim.Datacenter)
    dc_a.name = "DC-A"
    dc_b = MagicMock(spec=vim.Datacenter)
    dc_b.name = "DC-B"
    si = MagicMock()

    with patch.object(inventory, "find_datacenter_by_name", return_value=dc_b):
        got = inventory.resolve_datacenter(si, "DC-B")

    assert got is dc_b, "must resolve the named DC, not the first one"


def test_resolve_datacenter_skips_top_level_folder() -> None:
    """A top-level Folder (not a Datacenter) must be skipped, not returned."""
    from vmware_aiops.ops import inventory

    folder = MagicMock(spec=vim.Folder)
    dc = MagicMock(spec=vim.Datacenter)
    dc.name = "DC-1"
    si = _make_si([folder, dc])

    got = inventory.resolve_datacenter(si)

    assert got is dc, "must skip the leading Folder and return the Datacenter"


def test_resolve_datacenter_empty_inventory_raises_not_indexerror() -> None:
    """Empty inventory must raise InventoryError, not IndexError."""
    import pytest

    from vmware_aiops.ops import inventory

    si = _make_si([])
    with pytest.raises(inventory.InventoryError):
        inventory.resolve_datacenter(si)


def test_find_compute_resource_searches_explicitly_not_index_zero() -> None:
    """hostFolder.childEntity[0] may be a nested Folder — the compute resource
    must be found by type, recursing into folders."""
    from vmware_aiops.ops import inventory

    cr = MagicMock(spec=vim.ComputeResource)
    cr.name = "cluster-1"
    nested = MagicMock(spec=vim.Folder)
    nested.childEntity = [cr]
    leading_folder = MagicMock(spec=vim.Folder)
    leading_folder.childEntity = []

    dc = MagicMock(spec=vim.Datacenter)
    dc.name = "DC-1"
    dc.hostFolder.childEntity = [leading_folder, nested]

    got = inventory.find_compute_resource(dc)
    assert got is cr, "must recurse into folders to find the ComputeResource"


def test_create_vm_uses_resolve_datacenter_helper() -> None:
    """create_vm must route DC/compute resolution through the shared helper
    rather than indexing childEntity[0]."""
    from vmware_aiops.ops import vm_lifecycle

    dc = MagicMock(spec=vim.Datacenter)
    dc.name = "DC-1"
    cr = MagicMock(spec=vim.ComputeResource)

    with patch.object(vm_lifecycle, "resolve_datacenter", return_value=dc) as rd, \
         patch.object(vm_lifecycle, "find_compute_resource", return_value=cr) as fcr, \
         patch.object(vm_lifecycle, "find_datastore_by_name", return_value=MagicMock()), \
         patch.object(vm_lifecycle, "_wait_for_task"):
        vm_lifecycle.create_vm(MagicMock(), "vm1", datacenter_name="DC-1")

    rd.assert_called_once()
    fcr.assert_called_once()


# ── #18: _upload_disk streams in chunks and reports lease progress ──


def test_upload_disk_streams_in_chunks_and_reports_progress() -> None:
    """_upload_disk must read the tar member in chunks (size arg, multiple
    reads) and call HttpNfcLeaseProgress at least once."""
    from vmware_aiops.ops import vm_deploy

    # Fake extracted file: 3 chunk reads then EOF.
    extracted = MagicMock()
    extracted.read.side_effect = [b"a" * 8, b"b" * 8, b"c" * 4, b""]

    member = SimpleNamespace(
        name="disk1.vmdk", size=20, type=tarfile.REGTYPE,
    )
    tar = MagicMock()
    tar.getmember.return_value = member
    tar.extractfile.return_value = extracted
    tar_cm = MagicMock()
    tar_cm.__enter__.return_value = tar

    lease = MagicMock()

    def _fake_urlopen(req, **kw):
        # Drain the streaming body so the generator runs (and reports progress).
        for _ in req.data:
            pass
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        return cm

    with patch.object(vm_deploy.tarfile, "open", return_value=tar_cm), \
         patch.object(vm_deploy, "_safe_tar_member", return_value=True), \
         patch.object(vm_deploy, "urlopen", side_effect=_fake_urlopen):
        vm_deploy._upload_disk(
            lease, "/tmp/x.ova", "disk1.vmdk",
            "https://esxi/nfc/disk1.vmdk", 20, verify_ssl=False,
        )

    # Read was called with a chunk-size argument, multiple times (streaming).
    read_calls = extracted.read.call_args_list
    assert len(read_calls) >= 2, "expected chunked reads, not a single f.read()"
    assert all(c.args and isinstance(c.args[0], int) for c in read_calls), (
        "each read must pass an explicit chunk size"
    )
    assert lease.HttpNfcLeaseProgress.called, (
        "lease progress must be reported during/after the upload"
    )


# ── #19: OVA device URLs map to disks by importKey, not pop-order ──


def test_deploy_ova_maps_device_urls_by_importkey_out_of_order() -> None:
    """A 2-disk OVA whose device URLs arrive out of order must map each disk to
    the correct device via importKey, not the next remaining disk."""
    from vmware_aiops.ops import vm_deploy

    # OVA disks: keyed by file path inside the archive.
    disks = {"disk-A.vmdk": 100, "disk-B.vmdk": 200}

    # import_spec_result.fileItem links deviceId -> path.
    fi_a = SimpleNamespace(deviceId="key-A", path="disk-A.vmdk")
    fi_b = SimpleNamespace(deviceId="key-B", path="disk-B.vmdk")
    import_spec_result = SimpleNamespace(
        error=None, warning=None, fileItem=[fi_a, fi_b],
        importSpec=MagicMock(),
    )

    # Device URLs arrive B-first (out of order vs. disk dict insertion order).
    url_b = SimpleNamespace(
        url="https://esxi/nfc/B", importKey="key-B", targetId="disk-B.vmdk",
    )
    url_a = SimpleNamespace(
        url="https://esxi/nfc/A", importKey="key-A", targetId="disk-A.vmdk",
    )

    lease = MagicMock()
    lease.state = vim.HttpNfcLease.State.ready
    lease.info.deviceUrl = [url_b, url_a]

    resource_pool = MagicMock()
    resource_pool.ImportVApp.return_value = lease

    content = MagicMock()
    content.ovfManager.CreateImportSpec.return_value = import_spec_result
    si = MagicMock()
    si.RetrieveContent.return_value = content

    dc = MagicMock(spec=vim.Datacenter)
    cr = MagicMock(spec=vim.ComputeResource)
    cr.resourcePool = resource_pool

    uploads: list[tuple[str, str]] = []

    def _record_upload(lease_, ova_path, disk_name, target_url, disk_size, **kw):
        uploads.append((disk_name, target_url))

    with patch.object(vm_deploy, "find_datastore_by_name", return_value=MagicMock()), \
         patch.object(vm_deploy, "resolve_datacenter", return_value=dc), \
         patch.object(vm_deploy, "find_compute_resource", return_value=cr), \
         patch.object(vm_deploy, "_read_ovf_from_ova", return_value=("<ovf/>", disks)), \
         patch.object(vm_deploy, "get_verify_ssl", return_value=False), \
         patch.object(vm_deploy, "_upload_disk", side_effect=_record_upload):
        vm_deploy.deploy_ova(si, "/tmp/x.ova", "vm1", "ds1")

    by_url = dict((u, d) for d, u in uploads)
    assert by_url["https://esxi/nfc/A"] == "disk-A.vmdk", (
        "device A must receive disk-A by importKey, not pop-order"
    )
    assert by_url["https://esxi/nfc/B"] == "disk-B.vmdk", (
        "device B must receive disk-B by importKey, not pop-order"
    )
