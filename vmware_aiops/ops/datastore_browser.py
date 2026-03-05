"""Datastore file browsing and image discovery.

Browses vSphere datastores to find OVA, ISO, OVF, and VMDK files.
Maintains a local image registry (cache) for quick selection during deployment.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.config import CONFIG_DIR
from vmware_aiops.ops.inventory import find_datastore_by_name

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-aiops.datastore")

IMAGE_REGISTRY_FILE = CONFIG_DIR / "image_registry.json"

# File patterns for deployable images
IMAGE_PATTERNS = ("*.ova", "*.ovf", "*.iso", "*.vmdk")


def _wait_for_task(task, timeout: int = 120) -> object:
    """Wait for a vSphere task to complete."""
    start = time.time()
    while task.info.state in (vim.TaskInfo.State.running, vim.TaskInfo.State.queued):
        if time.time() - start > timeout:
            raise TimeoutError(f"Datastore browse timed out after {timeout}s")
        time.sleep(1)
    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result
    error_msg = str(task.info.error.msg) if task.info.error else "Unknown error"
    raise RuntimeError(f"Datastore browse failed: {error_msg}")


def browse_datastore(
    si: ServiceInstance,
    ds_name: str,
    path: str = "",
    pattern: str = "*",
) -> list[dict]:
    """Browse files in a datastore directory.

    Args:
        si: vSphere ServiceInstance
        ds_name: Datastore name
        path: Subdirectory path (empty for root)
        pattern: Glob pattern to filter files (e.g. "*.ova", "*")

    Returns:
        List of file dicts with name, size, type, modified, ds_path
    """
    ds = find_datastore_by_name(si, ds_name)
    if ds is None:
        raise ValueError(f"Datastore '{ds_name}' not found.")

    browser = ds.browser
    search_spec = vim.host.DatastoreBrowser.SearchSpec()
    search_spec.matchPattern = [pattern]
    search_spec.details = vim.host.DatastoreBrowser.FileInfo.Details(
        fileType=True,
        fileSize=True,
        modification=True,
    )
    # Include all file types in results
    search_spec.query = [
        vim.host.DatastoreBrowser.IsoImageQuery(),
        vim.host.DatastoreBrowser.VmDiskQuery(),
        vim.host.DatastoreBrowser.FolderQuery(),
    ]

    ds_path = f"[{ds_name}] {path}".rstrip()
    task = browser.SearchDatastoreSubFolders_Task(
        datastorePath=ds_path,
        searchSpec=search_spec,
    )
    results_raw = _wait_for_task(task)

    files: list[dict] = []
    for result in results_raw:
        folder = result.folderPath
        for f in result.file:
            file_type = type(f).__name__.replace("Info", "")
            files.append({
                "name": f.path,
                "size_mb": round(f.fileSize / (1024 * 1024), 1) if f.fileSize else 0,
                "type": file_type,
                "modified": str(f.modification) if f.modification else "",
                "ds_path": f"{folder}{f.path}",
            })

    return sorted(files, key=lambda x: x["name"])


def scan_images(
    si: ServiceInstance,
    ds_name: str,
    path: str = "",
) -> list[dict]:
    """Scan a datastore for deployable images (OVA, ISO, OVF, VMDK).

    Searches recursively through subdirectories.
    """
    all_images: list[dict] = []
    for pattern in IMAGE_PATTERNS:
        found = browse_datastore(si, ds_name, path=path, pattern=pattern)
        all_images.extend(found)

    return sorted(all_images, key=lambda x: x["name"])


def scan_all_datastores(si: ServiceInstance) -> dict[str, list[dict]]:
    """Scan all accessible datastores for deployable images.

    Returns:
        Dict mapping datastore name to list of image files found.
    """
    from vmware_aiops.ops.inventory import list_datastores

    datastores = list_datastores(si)
    result: dict[str, list[dict]] = {}
    for ds in datastores:
        if not ds["accessible"]:
            _log.info("Skipping inaccessible datastore: %s", ds["name"])
            continue
        try:
            images = scan_images(si, ds["name"])
            if images:
                result[ds["name"]] = images
        except Exception as e:
            _log.warning("Failed to scan datastore %s: %s", ds["name"], e)

    return result


# ─── Image Registry (local cache) ────────────────────────────────────────────


def _load_registry() -> dict:
    """Load the local image registry from disk."""
    if not IMAGE_REGISTRY_FILE.exists():
        return {"images": [], "last_scan": None}
    with open(IMAGE_REGISTRY_FILE) as f:
        return json.load(f)


def _save_registry(registry: dict) -> None:
    """Save the image registry to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(IMAGE_REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def update_registry(si: ServiceInstance) -> dict:
    """Scan all datastores and update the local image registry.

    Returns:
        The updated registry dict.
    """
    scan_result = scan_all_datastores(si)
    images: list[dict] = []
    for ds_name, ds_images in scan_result.items():
        for img in ds_images:
            images.append({
                "datastore": ds_name,
                "name": img["name"],
                "ds_path": img["ds_path"],
                "size_mb": img["size_mb"],
                "type": img["type"],
                "modified": img["modified"],
            })

    registry = {
        "images": images,
        "last_scan": datetime.now(timezone.utc).isoformat(),
    }
    _save_registry(registry)
    _log.info("Image registry updated: %d images across %d datastores",
              len(images), len(scan_result))
    return registry


def get_registry() -> dict:
    """Get the current image registry (from local cache)."""
    return _load_registry()


def list_images(
    image_type: str | None = None,
    datastore: str | None = None,
) -> list[dict]:
    """List images from the local registry, with optional filters.

    Args:
        image_type: Filter by file extension (e.g. "ova", "iso")
        datastore: Filter by datastore name
    """
    registry = _load_registry()
    images = registry.get("images", [])

    if image_type:
        ext = f".{image_type.lower().lstrip('.')}"
        images = [i for i in images if i["name"].lower().endswith(ext)]
    if datastore:
        images = [i for i in images if i["datastore"] == datastore]

    return images
