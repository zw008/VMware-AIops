"""A teaching message the agent never sees is not a teaching message.

``_safe_error`` reduces unrecognised exceptions to ``"<Class>: operation
failed."`` so raw vSphere text cannot leak. The allowlist it checks against was
an enumeration, and an enumeration drifts: two exceptions this skill raises
deliberately were missing from it, so their messages were replaced by their
class names on the way to the agent.

``OSError`` is the one that mattered most. ``config.py`` raises exactly one —
the missing-password error, this family's most common first-run failure — and
its entire remedy is the env var name it names. An MCP agent received
``OSError: operation failed.`` and had nothing to act on. ``TaskStillRunning``
was the second: it exists to say "this is NOT a failure, keep polling", and
arrived as ``TaskStillRunning: operation failed.``

The defect was invisible from the CLI, which prints these messages in full, and
invisible to the error-quality eval, which reads the message at the raise site
rather than what survives the wrapper.

So the rule is the inverse of an enumeration: every exception this skill raises
on purpose passes through, and only genuinely unplanned ones are reduced.
"""

from __future__ import annotations

import pytest

from vmware_aiops.mcp_server._shared import _safe_error
from vmware_aiops.ops.cluster_mgmt import ClusterError, ClusterNotFoundError
from vmware_aiops.ops.guest_ops import GuestOpsError
from vmware_aiops.ops.inventory import InventoryError
from vmware_aiops.ops.iscsi_config import HostNotFoundError, ISCSIError
from vmware_aiops.ops.vm_lifecycle import (
    TaskFailedError,
    TaskStillRunning,
    VMNotFoundError,
)

TEACHING = "VM 'web-99' not found on 'vcenter-prod'. Run vm_list to see available VMs."

ENV_KEY = "VMWARE_VCENTER_PROD_PASSWORD"
MISSING_PASSWORD = (
    f"Password not found for target 'vcenter-prod'. "
    f"Set environment variable {ENV_KEY}, or add "
    f"{ENV_KEY}=<password> to ~/.vmware-aiops/.env (chmod 600). "
    f"Run 'vmware-aiops init' to do both, then 'vmware-aiops doctor' to verify."
)


def test_missing_password_keeps_the_env_var_name():
    """The single OSError config.py raises — and the whole point of it is the name."""
    out = _safe_error(OSError(MISSING_PASSWORD), "vm_list")
    assert ENV_KEY in out
    assert "operation failed" not in out


@pytest.mark.parametrize(
    "exc_type",
    [
        VMNotFoundError,
        GuestOpsError,
        TaskFailedError,
        ClusterNotFoundError,
        ClusterError,
        InventoryError,
        HostNotFoundError,
        ISCSIError,
    ],
)
def test_domain_exceptions_keep_their_message(exc_type):
    assert _safe_error(exc_type(TEACHING), "vm_list") == TEACHING


def test_task_still_running_keeps_its_not_a_failure_message():
    """It exists to say "keep polling"; reduced to a class name it says the opposite."""
    out = _safe_error(TaskStillRunning("task-42", 300), "vm_clone")
    assert "NOT a failure" in out
    assert "task-42" in out


@pytest.mark.parametrize("exc_type", [ValueError, FileNotFoundError, KeyError, PermissionError])
def test_validation_errors_still_pass_through(exc_type):
    assert "web-99" in _safe_error(exc_type(TEACHING), "t")


def test_dropped_connection_surfaces_its_hint():
    """The CLI path catches OSError and prints the hint; the MCP path must match."""
    assert "retry" in _safe_error(ConnectionError("Connection lost — retry the operation."), "t")


def test_unplanned_exceptions_are_still_reduced():
    """The redaction this allowlist exists for has to keep working."""
    out = _safe_error(RuntimeError("https://admin:hunter2@vc.internal/api/task-42"), "t")
    assert out == "RuntimeError: operation failed."
    assert "hunter2" not in out


def test_message_is_still_truncated():
    """Length capping is the other half of the guard."""
    assert len(_safe_error(VMNotFoundError("x" * 900), "t")) <= 300
