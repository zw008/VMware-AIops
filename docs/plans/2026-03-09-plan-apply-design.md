# Plan → Apply Mode Design

## Overview

Terraform-style plan/apply workflow for multi-step VMware operations. Automatically triggered when an operation involves 2+ steps or 2+ VMs.

## Trigger Rules

| Condition | Mode |
|-----------|------|
| Single step, single VM (e.g. `power_off test-1`) | Existing double-confirm |
| 2+ steps on same VM (e.g. clean_slate = power_off + revert) | **Auto plan** |
| 1+ steps on 2+ VMs (e.g. batch_clone) | **Auto plan** |

## MCP Tools (3)

### `vm_create_plan(operations, target?)`

Input: structured operation list.

```json
{
  "operations": [
    {"action": "power_off", "vm_name": "test-1"},
    {"action": "revert_snapshot", "vm_name": "test-1", "snapshot": "baseline"},
    {"action": "power_on", "vm_name": "test-1"}
  ]
}
```

Behavior:
1. Validate each action name against allowed actions
2. Validate required params per action
3. Connect to vSphere, check target existence (VM, snapshot, host)
4. Generate plan with unique ID, write to `~/.vmware-aiops/plans/{plan_id}.json`
5. Return plan summary with steps, expected impact, and rollback info

### `vm_apply_plan(plan_id)`

Behavior:
1. Load plan from file
2. Execute steps sequentially
3. Record each step result (success/error/skipped) in plan file
4. On failure: stop immediately, ask if user wants to rollback
5. On success: delete plan file, log to `audit.log`

### `vm_list_plans()`

Return all pending (not yet executed) plans from `~/.vmware-aiops/plans/`.

## Allowed Actions

| Action | Required Params | Rollback Action |
|--------|----------------|-----------------|
| `power_on` | `vm_name` | `power_off` |
| `power_off` | `vm_name`, `force?` | `power_on` |
| `reset` | `vm_name` | irreversible |
| `suspend` | `vm_name` | `power_on` |
| `create_vm` | `vm_name`, `cpu?`, `memory_mb?`, `disk_gb?`, `network_name?`, `datastore_name?` | `delete_vm` |
| `delete_vm` | `vm_name` | irreversible |
| `reconfigure` | `vm_name`, `cpu?`, `memory_mb?` | irreversible (original values unknown at plan time) |
| `create_snapshot` | `vm_name`, `snapshot_name`, `description?`, `memory?` | `delete_snapshot` |
| `delete_snapshot` | `vm_name`, `snapshot_name`, `remove_children?` | irreversible |
| `revert_snapshot` | `vm_name`, `snapshot_name` | irreversible |
| `clone` | `vm_name`, `new_name` | `delete_vm(new_name)` |
| `migrate` | `vm_name`, `target_host` | irreversible (original host unknown) |
| `deploy_ova` | `ova_path`, `vm_name`, `datastore_name`, `network_name`, `power_on?`, `snapshot_name?` | `delete_vm` |
| `deploy_template` | `template_name`, `new_name`, `datastore_name?`, `cpu?`, `memory_mb?`, `power_on?`, `snapshot_name?` | `delete_vm(new_name)` |
| `linked_clone` | `source_vm_name`, `snapshot_name`, `new_name`, `cpu?`, `memory_mb?`, `power_on?` | `delete_vm(new_name)` |
| `attach_iso` | `vm_name`, `iso_ds_path` | irreversible |
| `convert_to_template` | `vm_name` | irreversible |

## Plan File Schema

```json
{
  "plan_id": "plan-20260309-143052-a1b2",
  "created_at": "2026-03-09T14:30:52Z",
  "target": "home-vcenter",
  "status": "pending",
  "steps": [
    {
      "index": 0,
      "action": "power_off",
      "params": {"vm_name": "test-1"},
      "rollback_action": "power_on",
      "rollback_params": {"vm_name": "test-1"},
      "status": "pending",
      "result": null,
      "executed_at": null
    }
  ],
  "summary": {
    "total_steps": 3,
    "vms_affected": ["test-1"],
    "irreversible_steps": [],
    "rollback_available": true
  }
}
```

## Status Flow

```
pending → executing → completed (file deleted)
                   → failed (file kept, steps show partial results)
                   → rolled_back (after user confirms rollback)
```

## Rollback Behavior

On failure at step N:
1. Mark step N as `failed`, record error
2. Return plan state to caller with `rollback_available: true/false`
3. If user confirms rollback: execute rollback actions for steps 0..N-1 in reverse order
4. Steps marked `irreversible` are skipped during rollback with a warning
5. Rollback results recorded in plan file

## Storage & Cleanup

- Location: `~/.vmware-aiops/plans/`
- Successful plans: deleted immediately after apply
- Failed plans: kept for debugging
- Stale cleanup: plans older than 24h auto-deleted on next `vm_create_plan` or `vm_list_plans` call

## Files to Create/Modify

| File | Change |
|------|--------|
| `vmware_aiops/ops/planner.py` | **NEW** — plan CRUD, validation, pre-checks |
| `vmware_aiops/ops/plan_executor.py` | **NEW** — sequential execution, rollback |
| `mcp_server/server.py` | Add 3 MCP tools |
| `vmware_aiops/cli.py` | Add `plan list` CLI command (read-only) |
