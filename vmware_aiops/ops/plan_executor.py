"""Plan → Apply: sequential plan execution with rollback support."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from vmware_aiops.ops.planner import delete_plan, load_plan, save_plan

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action dispatcher — maps action names to ops functions
# ---------------------------------------------------------------------------


def _dispatch(si: ServiceInstance, action: str, params: dict[str, Any]) -> str:
    """Execute a single action. Returns result string."""
    from vmware_aiops.ops.vm_lifecycle import (
        clone_vm,
        create_snapshot,
        create_vm,
        delete_snapshot,
        delete_vm,
        migrate_vm,
        power_off_vm,
        power_on_vm,
        reconfigure_vm,
        reset_vm,
        revert_to_snapshot,
        suspend_vm,
    )
    from vmware_aiops.ops.guest_ops import guest_download, guest_exec, guest_upload
    from vmware_aiops.ops.vm_deploy import (
        attach_iso,
        convert_to_template,
        deploy_from_template,
        deploy_ova,
        linked_clone,
    )

    dispatch_table: dict[str, Any] = {
        "power_on": lambda: power_on_vm(si, params["vm_name"]),
        "power_off": lambda: power_off_vm(si, params["vm_name"], force=params.get("force", False)),
        "reset": lambda: reset_vm(si, params["vm_name"]),
        "suspend": lambda: suspend_vm(si, params["vm_name"]),
        "create_vm": lambda: create_vm(
            si, params["vm_name"],
            cpu=params.get("cpu", 2),
            memory_mb=params.get("memory_mb", 4096),
            disk_gb=params.get("disk_gb", 40),
            network_name=params.get("network_name"),
            datastore_name=params.get("datastore_name"),
            folder_path=params.get("folder_path"),
            guest_id=params.get("guest_id", "otherGuest64"),
        ),
        "delete_vm": lambda: delete_vm(si, params["vm_name"]),
        "reconfigure": lambda: reconfigure_vm(
            si, params["vm_name"],
            cpu=params.get("cpu"),
            memory_mb=params.get("memory_mb"),
        ),
        "create_snapshot": lambda: create_snapshot(
            si, params["vm_name"], params["snapshot_name"],
            description=params.get("description", ""),
            memory=params.get("memory", True),
        ),
        "delete_snapshot": lambda: delete_snapshot(
            si, params["vm_name"], params["snapshot_name"],
            remove_children=params.get("remove_children", False),
        ),
        "revert_snapshot": lambda: revert_to_snapshot(
            si, params["vm_name"], params["snapshot_name"],
        ),
        "clone": lambda: clone_vm(si, params["vm_name"], params["new_name"]),
        "migrate": lambda: migrate_vm(si, params["vm_name"], params["target_host"]),
        "deploy_ova": lambda: deploy_ova(
            si, params["ova_path"], params["vm_name"],
            datastore_name=params["datastore_name"],
            network_name=params["network_name"],
            folder_path=params.get("folder_path"),
            power_on=params.get("power_on", False),
            snapshot_name=params.get("snapshot_name"),
        ),
        "deploy_template": lambda: deploy_from_template(
            si, params["template_name"], params["new_name"],
            datastore_name=params.get("datastore_name"),
            cpu=params.get("cpu"),
            memory_mb=params.get("memory_mb"),
            power_on=params.get("power_on", False),
            snapshot_name=params.get("snapshot_name"),
        ),
        "linked_clone": lambda: linked_clone(
            si, params["source_vm_name"], params["new_name"],
            snapshot_name=params["snapshot_name"],
            cpu=params.get("cpu"),
            memory_mb=params.get("memory_mb"),
            power_on=params.get("power_on", False),
            baseline_snapshot=params.get("baseline_snapshot"),
        ),
        "attach_iso": lambda: attach_iso(si, params["vm_name"], params["iso_ds_path"]),
        "convert_to_template": lambda: convert_to_template(si, params["vm_name"]),
        "guest_exec": lambda: guest_exec(
            si, params["vm_name"], params["command"],
            params["username"], params["password"],
            arguments=params.get("arguments", ""),
            working_directory=params.get("working_directory"),
        ),
        "guest_upload": lambda: guest_upload(
            si, params["vm_name"], params["local_path"],
            params["guest_path"], params["username"], params["password"],
        ),
        "guest_download": lambda: guest_download(
            si, params["vm_name"], params["guest_path"],
            params["local_path"], params["username"], params["password"],
        ),
    }

    handler = dispatch_table.get(action)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    result = handler()
    return str(result) if result is not None else "OK"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_plan(si: ServiceInstance, plan_id: str) -> dict:
    """Execute a plan step by step.

    Returns the final plan state dict with per-step results.
    On success, the plan file is deleted.
    On failure, the plan file is kept with status info and rollback_available flag.
    """
    plan = load_plan(plan_id)
    if plan is None:
        return {"error": f"Plan '{plan_id}' not found"}
    if plan["status"] != "pending":
        return {"error": f"Plan '{plan_id}' status is '{plan['status']}', expected 'pending'"}

    plan["status"] = "executing"
    save_plan(plan)

    failed_index: int | None = None

    for step in plan["steps"]:
        now = datetime.now(timezone.utc).isoformat()
        step["executed_at"] = now
        try:
            result = _dispatch(si, step["action"], step["params"])
            step["status"] = "success"
            step["result"] = result
            logger.info(
                "Plan %s step %d (%s): success",
                plan_id, step["index"], step["action"],
            )
        except Exception as exc:
            step["status"] = "failed"
            step["result"] = str(exc)
            failed_index = step["index"]
            logger.error(
                "Plan %s step %d (%s): FAILED — %s",
                plan_id, step["index"], step["action"], exc,
            )
            break

    # Mark remaining steps as skipped
    if failed_index is not None:
        for step in plan["steps"]:
            if step["index"] > failed_index:
                step["status"] = "skipped"

    if failed_index is None:
        plan["status"] = "completed"
        save_plan(plan)
        delete_plan(plan_id)
        logger.info("Plan %s completed successfully, file deleted", plan_id)
    else:
        plan["status"] = "failed"
        # Check if rollback is possible for executed steps
        executed_steps = [s for s in plan["steps"] if s["status"] == "success"]
        rollback_possible = any(s["rollback_action"] is not None for s in executed_steps)
        plan["rollback_available"] = rollback_possible
        save_plan(plan)

    return plan


def rollback_plan(si: ServiceInstance, plan_id: str) -> dict:
    """Rollback already-executed steps of a failed plan in reverse order.

    Only rolls back steps that have a rollback_action defined.
    Steps marked irreversible are skipped with a warning.
    """
    plan = load_plan(plan_id)
    if plan is None:
        return {"error": f"Plan '{plan_id}' not found"}
    if plan["status"] != "failed":
        return {"error": f"Plan '{plan_id}' status is '{plan['status']}', rollback only available for 'failed' plans"}

    # Get successfully executed steps in reverse order
    executed_steps = [
        s for s in reversed(plan["steps"]) if s["status"] == "success"
    ]

    if not executed_steps:
        return {"error": "No executed steps to rollback"}

    rollback_results: list[dict] = []

    for step in executed_steps:
        rollback_action = step.get("rollback_action")
        rollback_params = step.get("rollback_params")

        if rollback_action is None:
            entry = {
                "step_index": step["index"],
                "action": step["action"],
                "rollback_status": "skipped",
                "reason": "irreversible",
            }
            rollback_results.append(entry)
            logger.warning(
                "Plan %s step %d (%s): irreversible, skipping rollback",
                plan_id, step["index"], step["action"],
            )
            continue

        try:
            result = _dispatch(si, rollback_action, rollback_params)
            step["status"] = "rolled_back"
            entry = {
                "step_index": step["index"],
                "action": step["action"],
                "rollback_action": rollback_action,
                "rollback_status": "success",
                "result": result,
            }
            rollback_results.append(entry)
            logger.info(
                "Plan %s step %d rollback (%s): success",
                plan_id, step["index"], rollback_action,
            )
        except Exception as exc:
            entry = {
                "step_index": step["index"],
                "action": step["action"],
                "rollback_action": rollback_action,
                "rollback_status": "failed",
                "error": str(exc),
            }
            rollback_results.append(entry)
            logger.error(
                "Plan %s step %d rollback (%s): FAILED — %s",
                plan_id, step["index"], rollback_action, exc,
            )
            # Continue rolling back other steps even if one fails

    plan["status"] = "rolled_back"
    plan["rollback_results"] = rollback_results
    save_plan(plan)

    return {
        "plan_id": plan_id,
        "status": "rolled_back",
        "rollback_results": rollback_results,
    }
