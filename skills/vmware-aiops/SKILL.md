---
name: vmware-aiops
description: >
  Use this skill whenever the user needs to manage VMs in VMware/vSphere/ESXi — it's the entry point for all VM operations.
  Directly handles: power on/off, clone, snapshot, migrate, deploy from OVA or templates, run commands inside VMs, batch operations, cluster management, vCenter alarm acknowledgment, and a one-glance cluster-health triage ("is anything on fire?").
  Always use this skill for any "power on", "clone", "deploy", "migrate", "batch", "guest exec", "alarm", or VM lifecycle task, and for a quick "what's wrong in my environment" / "cluster health" / "is anything on fire" triage, when the context is explicitly VMware, vSphere, or ESXi.
  Do NOT use for general read-only queries (inventory/events/VM details — use vmware-monitor), NSX networking (use vmware-nsx), storage/iSCSI/vSAN (use vmware-storage), or Kubernetes cluster lifecycle (use vmware-vks).
  For multi-step workflows use vmware-pilot. For load balancing/AVI/AKO use vmware-avi.
installer:
  kind: uv
  package: vmware-aiops
argument-hint: "[vm-name or describe your task]"
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_AIOPS_CONFIG"],"bins":["vmware-aiops"],"config":["~/.vmware-aiops/config.yaml","~/.vmware-aiops/.env"]},"optional":{"env":["VMWARE_TARGET_PASSWORD","SLACK_WEBHOOK_URL","DISCORD_WEBHOOK_URL"],"bins":["vmware-policy"]},"primaryEnv":"VMWARE_AIOPS_CONFIG","homepage":"https://github.com/zw008/VMware-AIops","emoji":"🖥️","os":["macos","linux"]}}
compatibility: >
  vmware-policy auto-installed as Python dependency (provides @vmware_tool decorator and audit logging). All write operations audited to ~/.vmware/audit.db.
  Credentials: Each vCenter/ESXi target requires a per-target password env var in ~/.vmware-aiops/.env following the pattern VMWARE_<TARGET_NAME_UPPER>_PASSWORD. Passwords are never logged or echoed.
  Destructive operations: All write tools require explicit parameters, pass through @vmware_tool decorator (pre-check + audit + sanitize), and CLI destructive commands require double confirmation + support --dry-run.
  Guest operations: Require explicit vm_name, cmd (full path), args, user parameters — no implicit or background execution.
  Webhooks: Disabled by default. When enabled, send only aggregated alert metadata (alarm counts, event types) to user-configured URLs. No credentials, IPs, or PII in payloads.
  SSL bypass: disableSslCertValidation is off by default; exists only for self-signed certs in isolated lab environments.
  Transitive dependencies: Only vmware-policy (audit/policy). No post-install scripts or background services.
---

# VMware AIops

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "vSphere" are trademarks of Broadcom. Source code is publicly auditable at [github.com/zw008/VMware-AIops](https://github.com/zw008/VMware-AIops) under the MIT license.

VMware family entry point — AI-powered VM lifecycle, deployment, and alarm management — 45 MCP tools.

> **Start here**: install vmware-aiops first, then add modules as needed.
> Run `vmware-aiops hub status` to see which family members are installed.
> **Family**: [vmware-monitor](https://github.com/zw008/VMware-Monitor) (inventory/health), [vmware-storage](https://github.com/zw008/VMware-Storage) (iSCSI/vSAN), [vmware-vks](https://github.com/zw008/VMware-VKS) (Tanzu Kubernetes), [vmware-nsx](https://github.com/zw008/VMware-NSX) (NSX networking), [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity), [vmware-avi](https://github.com/zw008/VMware-AVI) (AVI/ALB/AKO), [vmware-harden](https://github.com/zw008/VMware-Harden) (compliance baselines).
> | [vmware-pilot](../vmware-pilot/SKILL.md) (workflow orchestration) | [vmware-policy](../vmware-policy/SKILL.md) (audit/policy)

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **VM Lifecycle** | power on/off, create, reconfigure, clone, migrate, delete, snapshot CRUD, TTL auto-delete, clean slate | 15 |
| **Deployment** | OVA, template, linked clone, batch clone/deploy | 8 |
| **Guest Ops** | exec commands, upload/download files, provision | 5 |
| **Plan/Apply** | multi-step planning with rollback | 4 |
| **Cluster** | create, delete, HA/DRS config, add/remove hosts | 6 |
| **Datastore** | browse files, scan for images | 2 |
| **Alarm Management** | list alarms, acknowledge, reset | 3 |

## Quick Install

```bash
uv tool install vmware-aiops
vmware-aiops doctor
vmware-aiops hub status   # see which family members are installed
```

## VMware Family — Install What You Need

vmware-aiops is the entry point. Add modules for additional capabilities:

| Module | Install | Adds |
|--------|---------|------|
| **vmware-monitor** | `uv tool install vmware-monitor` | Read-only inventory, alarms, events |
| **vmware-storage** | `uv tool install vmware-storage` | iSCSI, vSAN, datastore management |
| **vmware-vks** | `uv tool install vmware-vks` | Tanzu Kubernetes (vSphere 8.x+) |
| **vmware-nsx** | `uv tool install vmware-nsx-mgmt` | NSX networking: segments, gateways, NAT |
| **vmware-nsx-security** | `uv tool install vmware-nsx-security` | DFW microsegmentation, security groups |
| **vmware-aria** | `uv tool install vmware-aria` | Aria Ops metrics, alerts, capacity |
| **vmware-avi** | `uv tool install vmware-avi` | AVI load balancer, ALB, AKO, Ingress |

> Each module stays independent — small tool count keeps local models (Ollama, Qwen) accurate.

## When to Use This Skill

- Power on/off, create, delete, snapshot, clone, or migrate VMs
- Deploy VMs from OVA, templates, linked clones, or batch specs
- Run commands or transfer files inside a VM (Guest Operations)
- Create/configure clusters (HA/DRS)
- Browse datastores for deployable images
- Plan and execute multi-step operations with rollback
- List, acknowledge, and clear vCenter triggered alarms (clear matches by entity type + status — see MCP Tools section)

**Use companion skills for**:
- Inventory, health, alarms, VM info → `vmware-monitor`
- iSCSI, vSAN, datastore management → `vmware-storage`
- Tanzu Kubernetes (Supervisor, Namespace, TKC) → `vmware-vks`
- Load balancing, AVI/ALB, AKO, Ingress → `vmware-avi`

## Related Skills — Skill Routing

| User Intent | Recommended Skill |
|-------------|------------------|
| Read-only monitoring, zero risk | **vmware-monitor** (`uv tool install vmware-monitor`) |
| Storage: iSCSI, vSAN, datastores | **vmware-storage** (`uv tool install vmware-storage`) |
| VM lifecycle, deployment, guest ops | **vmware-aiops** ← this skill |
| Tanzu Kubernetes (vSphere 8.x+) | **vmware-vks** (`uv tool install vmware-vks`) |
| NSX networking: segments, gateways, NAT | **vmware-nsx** (`uv tool install vmware-nsx-mgmt`) |
| NSX security: DFW rules, security groups | **vmware-nsx-security** (`uv tool install vmware-nsx-security`) |
| Aria Ops: metrics, alerts, capacity | **vmware-aria** (`uv tool install vmware-aria`) |
| Multi-step workflows with approval | **vmware-pilot** |
| Compliance baselines (CIS / 等保 / PCI-DSS), drift detection, LLM remediation advisor | **vmware-harden** (`uv tool install vmware-harden`) |
| Load balancer, AVI, ALB, AKO, Ingress | **vmware-avi** (`uv tool install vmware-avi`) |
| Audit log query | **vmware-policy** (`vmware-audit` CLI) |

## Common Workflows

> **Diagnostic investigations**: Before remediating any "why is X slow / failing / down" issue, follow [`references/investigation-protocol.md`](references/investigation-protocol.md). It enforces the four root-cause completeness criteria (falsifiability / sufficiency / necessity / mechanism) and the up-to-three-rounds deepening loop. Only invoke L3+ write tools after the four criteria are satisfied AND the user has approved a remediation plan.

### Cluster Health Triage ("what's wrong right now?")

Start here when the ask is "is anything on fire?" before diving into a specific VM. This is a read-only rollup delegated to vmware-monitor, exposed here so triage-then-act stays in one conversation.

1. One glance --> `cluster_health_summary` (MCP) or `vmware-aiops summary` (CLI). Read `top_issues` first — ranked anomalies (disconnected hosts, red/yellow alarms, capacity pressure), each with a drill-down hint; the per-cluster table is context
2. Act on what it surfaces --> a `host_down` row → investigate the host; an alarm → `acknowledge_vcenter_alarm` / `reset_vcenter_alarm`; a hot VM implicated → `vm_migrate` or `vm_reconfigure` (after the investigation protocol)
3. Save/share a snapshot --> `vmware-aiops summary --html` writes an offline, timestamped HTML file (identical to `vmware-monitor summary --html` — same shared renderer)
4. **If vmware-monitor is not installed** --> this command/tool is unavailable (AIops delegates to it); install `vmware-monitor`, or use the deeper per-object read tools in that skill

### Deploy a Lab Environment

**Pre-flight (judgment, not blind sequence)**:
- Free space: target datastore must have ≥ OVA size × 2 (delta files + thin-provision overhead). If multiple datastores qualify, prefer one with lowest current IOPS pressure (cross-check `vmware-aria` if available).
- Name hygiene: prefix with date or owner (`lab-2026-04-30-alice`) so the TTL cleanup audit trail is meaningful.
- TTL: always set. 480 min for a single test session, 7200 min for a week-long sandbox. **Never deploy a "lab" VM without a TTL** — that is how datastores fill up at 3 AM.
- Snapshot timing: take the baseline **after** provisioning succeeds, not before — a pre-provision snapshot is just an empty checkpoint.

**Steps**:
1. `vmware-aiops datastore browse <ds> --pattern "*.ova"` → confirm image present and size
2. `vmware-aiops deploy ova <path> --name <date>-<owner>-<purpose> --datastore <ds>`
3. `vmware-aiops vm guest-exec <name> --cmd /usr/bin/python3 --args "setup.py" --user admin` → if exit ≠ 0, **stop**, do not snapshot a half-provisioned VM
4. `vmware-aiops vm snapshot-create <name> --name baseline` (only if multi-iteration testing; skip for one-shot)
5. `vmware-aiops vm set-ttl <name> --minutes 480`

### Batch Clone for Testing

**Pre-flight**:
- Source VM state: powered-off is safest. If powered-on, VMware Tools must be running and quiesce-capable, else clones may have inconsistent disk state.
- Capacity math: `free_space ≥ source.size × count × 1.2` (full clone) or `≥ count × 2 GB` (linked clone, delta-only).
- Decision rule: **count > 10 → use linked clones** (`deploy linked-clone`); seconds vs minutes per clone, ~100× less storage. Tradeoff: linked clones depend on source snapshot — deleting the snapshot breaks all children.
- Network exhaustion: each clone gets a unique MAC from the vSphere pool; if you batch > 200, verify pool capacity in advance.
- TTL: every clone must have one. Use the plan's metadata to track ownership.

**Steps**:
1. `vm_create_plan` with clone + reconfigure + set-ttl steps grouped per VM (atomic per clone)
2. Review the plan with the user — surface count, datastore, irreversible warnings
3. `vm_apply_plan` — stops on first failure (intentional, do not auto-resume)
4. On failure: `vm_rollback_plan` → reverses completed clones; manually verify rollback before retrying

### Migrate VM to Another Host

**Pre-flight (ALL must pass before issuing migrate)**:
- CPU compatibility: target host CPU family must match source, OR cluster must be in EVC mode. Live migration across mismatched CPUs **fails mid-flight** and may leave the VM stunned.
- Network parity: every portgroup the VM uses must exist on the target host's vSwitch with the same VLAN. Missing portgroup → vNICs disconnected post-migration.
- Storage visibility: target host must see all of the VM's datastores; otherwise this is a Storage vMotion, not a host migration — different (slower) operation.
- Affinity rules: if the VM is pinned to source by a DRS host-affinity rule, migration silently violates intent. Check `cluster info` first.
- Hardware passthrough: VMs with PCI passthrough (GPU, USB) **cannot live-migrate** — schedule a cold migration window.

**Steps**:
1. Verify VM state and current host via `vmware-monitor vm info <name>`
2. Verify target host: same cluster, EVC compatible, has required networks/datastores
3. `vmware-aiops vm migrate <name> --to-host <target>` — wait for task completion, do not assume success on return
4. Post-check: `vm info` confirms new host AND power state unchanged AND vNICs connected

## Usage Mode

| Scenario | Recommended | Why |
|----------|:-----------:|-----|
| Local/small models (Ollama, Qwen) | **CLI** | ~2K tokens vs ~8K for MCP |
| Cloud models (Claude, GPT-4o) | Either | MCP gives structured JSON I/O |
| Automated pipelines | **MCP** | Type-safe parameters, structured output |

## MCP Tools (45 — 10 read, 35 write)

| Category | Tools | R/W |
|----------|-------|:---:|
| VM Lifecycle (16) | `vm_list_ttl`, `vm_list_snapshots`, `vm_task_status` | Read |
| | `vm_power_on`, `vm_power_off`, `vm_create`, `vm_reconfigure`, `vm_clone`, `vm_migrate`, `vm_delete`, `vm_create_snapshot`, `vm_revert_snapshot`, `vm_delete_snapshot`, `vm_set_ttl`, `vm_cancel_ttl`, `vm_clean_slate` | Write |
| Deployment (8) | `deploy_vm_from_ova`, `deploy_vm_from_template`, `deploy_linked_clone`, `attach_iso_to_vm`, `convert_vm_to_template`, `batch_clone_vms`, `batch_linked_clone_vms`, `batch_deploy_from_spec` | Write |
| Guest Ops (5) | `vm_guest_download` | Read |
| | `vm_guest_exec`, `vm_guest_exec_output`, `vm_guest_upload`, `vm_guest_provision` | Write |
| Plan/Apply (4) | `vm_list_plans` | Read |
| | `vm_create_plan`, `vm_apply_plan`, `vm_rollback_plan` | Write |
| Datastore (2) | `browse_datastore`, `scan_datastore_images` | Read |
| Cluster (6) | `cluster_info` | Read |
| | `cluster_create`, `cluster_delete`, `cluster_add_host`, `cluster_remove_host`, `cluster_configure` | Write |
| Alarm Management (3) | `list_vcenter_alarms` | Read |
| | `acknowledge_vcenter_alarm`, `reset_vcenter_alarm` | Write |
| Cluster Triage (1) | `cluster_health_summary` (delegates to vmware-monitor) | Read |

**Read/write split**: 10 tools are read-only (per `[READ]` docstring marker), 35 modify state. All write tools require explicit parameters and are audit-logged. Destructive operations (`vm_delete`, `vm_revert_snapshot`, `vm_delete_snapshot`, `vm_set_ttl` (schedules an unattended auto-delete), force power-off, cluster delete/remove-host, alarm reset) require double confirmation at the CLI layer and support `--dry-run`.

**Alarm reset blast radius**: vSphere has no per-alarm clear API. `reset_vcenter_alarm` uses `AlarmManager.ClearTriggeredAlarms`, which clears **all** triggered alarms matching the named alarm's entity type (host/VM/all) and current status (red/yellow) — not just the one named. The response's `scope` field states exactly what was cleared. The named alarm is looked up first, so a typo fails fast without clearing anything.

## CLI Quick Reference

```bash
# VM operations
vmware-aiops vm power-on <name> [--target <t>]
vmware-aiops vm power-off <name> [--force]
vmware-aiops vm create <name> --cpu 4 --memory 8192 --disk 100
vmware-aiops vm delete <name>
vmware-aiops vm clone <name> --new-name <new> [--to-host <host>] [--to-datastore <ds>] [--power-on]
vmware-aiops vm migrate <name> --to-host <host> [--to-datastore <ds>]
vmware-aiops vm snapshot-create <name> --name <snap> [--description <text>] [--memory]
vmware-aiops vm snapshot-list <name>
vmware-aiops vm snapshot-revert <name> --name <snap>
vmware-aiops vm snapshot-delete <name> --name <snap> [--remove-children] [--no-wait]
                                                            # waits up to 30 min for delta consolidation;
                                                            # --no-wait returns a task id immediately
vmware-aiops vm task-status <task-id>                      # poll an async (--no-wait) operation by id
vmware-aiops vm set-ttl <name> --minutes 480 [--dry-run]   # double confirm; daemon auto-deletes VM on expiry

# Guest operations (requires VMware Tools)
vmware-aiops vm guest-exec <name> --cmd <script-path> --args "<args>" --user <username>
vmware-aiops vm guest-upload <name> --local ./script.sh --guest /tmp/script.sh --user <username>

# Deploy
vmware-aiops deploy ova <path> --name <vm> --datastore <ds>
vmware-aiops deploy linked-clone --source <vm> --snapshot <snap> --name <new>

# Cluster
vmware-aiops cluster create <name> --ha --drs
vmware-aiops cluster info <name>

# Datastore
vmware-aiops datastore browse <ds> --pattern "*.ova"

# Alarm management
vmware-aiops alarm list [--target <t>]
vmware-aiops alarm acknowledge <entity_name> <alarm_name> [--target <t>]
vmware-aiops alarm reset <entity_name> <alarm_name> [--target <t>]   # double confirm; clears ALL alarms matching entity type + status

# Family
vmware-aiops hub status        # show installed family members + install commands
```

> Full CLI reference: see `references/cli-reference.md`

## Troubleshooting

### "VM not found" error
VM names are case-sensitive in vSphere. Use exact name from `vmware-monitor inventory vms`.

### Guest exec returns empty output
Use `vm_guest_exec_output` instead of `vm_guest_exec` — it auto-captures stdout/stderr. Basic `vm_guest_exec` only returns exit code.

### Deploy OVA times out
Large OVA files (>10GB) may exceed the default 120s timeout. The upload happens via HTTP NFC lease — ensure network between the machine running vmware-aiops and ESXi is stable.

### Snapshot delete is slow / "still running after Ns"
Deleting an old or large snapshot consolidates its delta disk into the parent — the slowest write
operation, often several minutes. `vm snapshot-delete` waits up to 30 min by default; if it still
returns a "still running, NOT failed" message with a task id, the delete did **not** fail — poll it with
`vm task-status <task-id>`. Do not re-issue the delete or hand-roll polling. For very large snapshots,
prefer `vm snapshot-delete <name> --name <snap> --no-wait` to get the task id immediately and poll.

### Plan apply fails mid-way
Run `vmware-aiops plan list` to see failed plan status. Ask user if they want to rollback with `vm_rollback_plan`. Irreversible steps (delete_vm) are skipped during rollback.

### Connection refused / SSL error
1. Verify target is reachable: `vmware-aiops doctor`
2. For self-signed certs: set `disableSslCertValidation: true` in config.yaml (lab environments only)

## Setup

```bash
uv tool install vmware-aiops
mkdir -p ~/.vmware-aiops
vmware-aiops init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-aiops/.env
```

> All tools are automatically audited via vmware-policy. Audit logs: `vmware-audit log --last 20`

> Full setup guide, security details, and AI platform compatibility: see `references/setup-guide.md`

## Audit & Safety

All operations are automatically audited via vmware-policy (`@vmware_tool` decorator):
- Every tool call logged to `~/.vmware/audit.db` (SQLite, framework-agnostic)
- Policy rules enforced via `~/.vmware/rules.yaml` (deny rules, maintenance windows, risk levels)
- Risk classification: each tool tagged as low/medium/high/critical
- View recent operations: `vmware-audit log --last 20`
- View denied operations: `vmware-audit log --status denied`

vmware-policy is automatically installed as a dependency — no manual setup needed.

## License

MIT — [github.com/zw008/VMware-AIops](https://github.com/zw008/VMware-AIops)
