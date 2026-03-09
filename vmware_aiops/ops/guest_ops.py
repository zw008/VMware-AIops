"""Guest Operations: execute commands and transfer files inside VMs.

Requires VMware Tools running inside the guest OS.
Uses the GuestOperationsManager API (VIX-like, over SOAP).
"""

from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.ops.inventory import find_vm_by_name
from vmware_aiops.ops.vm_lifecycle import VMNotFoundError

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2  # seconds
_EXEC_TIMEOUT = 300  # seconds


class GuestOpsError(Exception):
    """Raised when a guest operation fails."""


def _require_vm_with_tools(
    si: ServiceInstance, vm_name: str
) -> vim.VirtualMachine:
    """Find VM and verify VMware Tools is running."""
    vm = find_vm_by_name(si, vm_name)
    if vm is None:
        raise VMNotFoundError(f"VM '{vm_name}' not found")
    if vm.runtime.powerState != vim.VirtualMachine.PowerState.poweredOn:
        raise GuestOpsError(f"VM '{vm_name}' is not powered on")
    tools_status = vm.guest.toolsRunningStatus if vm.guest else None
    if tools_status != "guestToolsRunning":
        raise GuestOpsError(
            f"VMware Tools not running on '{vm_name}' "
            f"(status: {tools_status}). Guest operations require running Tools."
        )
    return vm


def _guest_auth(username: str, password: str) -> vim.vm.guest.NamePasswordAuthentication:
    """Build guest authentication spec."""
    auth = vim.vm.guest.NamePasswordAuthentication()
    auth.username = username
    auth.password = password
    auth.interactiveSession = False
    return auth


def guest_exec(
    si: ServiceInstance,
    vm_name: str,
    command: str,
    username: str,
    password: str,
    arguments: str = "",
    working_directory: str | None = None,
    timeout: int = _EXEC_TIMEOUT,
) -> dict:
    """Execute a command inside a VM via VMware Tools.

    Args:
        si: vSphere ServiceInstance.
        vm_name: Target VM name.
        command: Full path to the program (e.g. "/bin/bash", "C:\\Windows\\System32\\cmd.exe").
        username: Guest OS username.
        password: Guest OS password.
        arguments: Command arguments (e.g. "-c 'ls -la /tmp'").
        working_directory: Working directory inside the guest (optional).
        timeout: Max wait time in seconds (default 300).

    Returns:
        dict with keys: exit_code, stdout, stderr, timed_out.
    """
    vm = _require_vm_with_tools(si, vm_name)
    content = si.RetrieveContent()
    gom = content.guestOperationsManager
    pm = gom.processManager

    auth = _guest_auth(username, password)

    # Build process spec
    spec = vim.vm.guest.ProcessManager.ProgramSpec()
    spec.programPath = command
    spec.arguments = arguments
    if working_directory:
        spec.workingDirectory = working_directory

    # Start the process
    pid = pm.StartProgramInGuest(vm, auth, spec)
    logger.info("Started process PID %d in VM '%s': %s %s", pid, vm_name, command, arguments)

    # Poll for completion
    start = time.time()
    timed_out = False
    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            timed_out = True
            break

        processes = pm.ListProcessesInGuest(vm, auth, pids=[pid])
        if not processes:
            break
        proc = processes[0]
        if proc.exitCode is not None:
            # Process finished
            return {
                "exit_code": proc.exitCode,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "command": f"{command} {arguments}".strip(),
                "pid": pid,
            }
        time.sleep(_POLL_INTERVAL)

    if timed_out:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Process timed out after {timeout}s",
            "timed_out": True,
            "command": f"{command} {arguments}".strip(),
            "pid": pid,
        }

    return {
        "exit_code": -1,
        "stdout": "",
        "stderr": "Process disappeared unexpectedly",
        "timed_out": False,
        "command": f"{command} {arguments}".strip(),
        "pid": pid,
    }


def guest_upload(
    si: ServiceInstance,
    vm_name: str,
    local_path: str,
    guest_path: str,
    username: str,
    password: str,
    overwrite: bool = True,
) -> str:
    """Upload a file from the local machine to a VM via VMware Tools.

    Args:
        si: vSphere ServiceInstance.
        vm_name: Target VM name.
        local_path: Local file path to upload.
        guest_path: Destination path inside the guest.
        username: Guest OS username.
        password: Guest OS password.
        overwrite: Overwrite if file exists (default True).

    Returns:
        Success message string.
    """
    import urllib.request
    import ssl

    vm = _require_vm_with_tools(si, vm_name)
    content = si.RetrieveContent()
    gom = content.guestOperationsManager
    fm = gom.fileManager

    auth = _guest_auth(username, password)

    # Read local file
    with open(local_path, "rb") as f:
        file_data = f.read()

    file_size = len(file_data)

    # Create file attributes
    file_attr = vim.vm.guest.FileManager.FileAttributes()

    # Initiate file transfer (get upload URL)
    transfer_url = fm.InitiateFileTransferToGuest(
        vm, auth, guest_path, file_attr, file_size, overwrite
    )

    # Upload via HTTPS PUT
    # The URL returned may use the vCenter/ESXi hostname; we need to handle
    # self-signed certificates for lab environments
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Lab/ESXi self-signed certs  # nosec B501

    req = urllib.request.Request(transfer_url, data=file_data, method="PUT")
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("Content-Length", str(file_size))

    urllib.request.urlopen(req, context=ctx)  # nosec B310 — URL from vSphere API

    logger.info(
        "Uploaded %d bytes to '%s:%s'", file_size, vm_name, guest_path
    )
    return f"Uploaded {file_size} bytes to {guest_path} on VM '{vm_name}'"


def guest_download(
    si: ServiceInstance,
    vm_name: str,
    guest_path: str,
    local_path: str,
    username: str,
    password: str,
) -> str:
    """Download a file from a VM to the local machine via VMware Tools.

    Args:
        si: vSphere ServiceInstance.
        vm_name: Target VM name.
        guest_path: File path inside the guest to download.
        local_path: Local destination path.
        username: Guest OS username.
        password: Guest OS password.

    Returns:
        Success message string.
    """
    import urllib.request
    import ssl

    vm = _require_vm_with_tools(si, vm_name)
    content = si.RetrieveContent()
    gom = content.guestOperationsManager
    fm = gom.fileManager

    auth = _guest_auth(username, password)

    # Initiate file transfer from guest (get download URL)
    transfer_info = fm.InitiateFileTransferFromGuest(vm, auth, guest_path)

    # Download via HTTPS GET
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Lab/ESXi self-signed certs  # nosec B501

    resp = urllib.request.urlopen(transfer_info.url, context=ctx)  # nosec B310
    file_data = resp.read()

    # Write to local file
    with open(local_path, "wb") as f:
        f.write(file_data)

    logger.info(
        "Downloaded %d bytes from '%s:%s' to '%s'",
        len(file_data), vm_name, guest_path, local_path,
    )
    return (
        f"Downloaded {len(file_data)} bytes from {guest_path} "
        f"on VM '{vm_name}' to {local_path}"
    )
