---
name: vmware-aiops
description: >
  Use this skill whenever the user needs to manage VMs in VMware/vSphere/ESXi — it's the entry point for all VM operations.
  Directly handles: power on/off, clone, snapshot, migrate, deploy from OVA or templates, run commands inside VMs, batch operations, cluster management, and vCenter alarm acknowledgment.
  Always use this skill for any "power on", "clone", "deploy", "migrate", "batch", "guest exec", "alarm", or VM lifecycle task when the context is explicitly VMware, vSphere, or ESXi.
  Do NOT use for read-only queries (use vmware-monitor), NSX networking (use vmware-nsx), storage/iSCSI/vSAN (use vmware-storage), or Kubernetes cluster lifecycle (use vmware-vks).
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
---

# VMware AIops

VMware family entry point — AI-powered VM lifecycle, deployment, and alarm management — 34 MCP tools.

> **Start here**: install vmware-aiops first, then add modules as needed.
> Run `vmware-aiops hub status` to see which family members are installed.
> **Family**: [vmware-monitor](https://github.com/zw008/VMware-Monitor) (inventory/health), [vmware-storage](https://github.com/zw008/VMware-Storage) (iSCSI/vSAN), [vmware-vks](https://github.com/zw008/VMware-VKS) (Tanzu Kubernetes), [vmware-nsx](https://github.com/zw008/VMware-NSX) (NSX networking), [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity), [vmware-avi](https://github.com/zw008/VMware-AVI) (AVI/ALB/AKO).
> | [vmware-pilot](../vmware-pilot/SKILL.md) (workflow orchestration) | [vmware-policy](../vmware-policy/SKILL.md) (audit/policy)

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **VM Lifecycle** | power on/off, TTL auto-delete, clean slate | 6 |
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
- List, acknowledge, and reset vCenter triggered alarms

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
| Load balancer, AVI, ALB, AKO, Ingress | **vmware-avi** (`uv tool install vmware-avi`) |
| Audit log query | **vmware-policy** (`vmware-audit` CLI) |

## Common Workflows

### Deploy a Lab Environment
1. Browse datastore for OVA images → `vmware-aiops datastore browse <ds> --pattern "*.ova"`
2. Deploy VM from OVA → `vmware-aiops deploy ova ./image.ova --name lab-vm --datastore ds1`
3. Run provisioning script inside VM → `vmware-aiops vm guest-exec lab-vm --cmd /usr/bin/python3 --args "setup.py" --user admin`
4. Create baseline snapshot → `vmware-aiops vm snapshot-create lab-vm --name baseline`
5. Set TTL for auto-cleanup → `vmware-aiops vm set-ttl lab-vm --minutes 480`

### Batch Clone for Testing
1. Create plan: `vm_create_plan` with multiple clone + reconfigure steps
2. Review plan with user (shows affected VMs, irreversible warnings)
3. Apply: `vm_apply_plan` executes sequentially, stops on failure
4. If failed: `vm_rollback_plan` reverses executed steps
5. Set TTL on all clones for auto-cleanup

### Migrate VM to Another Host
1. Check VM info via `vmware-monitor` → verify power state and current host
2. Migrate: `vmware-aiops vm migrate my-vm --to-host esxi-02`
3. Verify migration completed

## Usage Mode

| Scenario | Recommended | Why |
|----------|:-----------:|-----|
| Local/small models (Ollama, Qwen) | **CLI** | ~2K tokens vs ~8K for MCP |
| Cloud models (Claude, GPT-4o) | Either | MCP gives structured JSON I/O |
| Automated pipelines | **MCP** | Type-safe parameters, structured output |

## MCP Tools (34 — 20 read, 14 write)

| Category | Tools | R/W |
|----------|-------|:---:|
| VM Lifecycle (6) | `vm_list_ttl` | Read |
| | `vm_power_on`, `vm_power_off`, `vm_set_ttl`, `vm_cancel_ttl`, `vm_clean_slate` | Write |
| Deployment (8) | `deploy_vm_from_ova`, `deploy_vm_from_template`, `deploy_linked_clone`, `attach_iso_to_vm`, `convert_vm_to_template`, `batch_clone_vms`, `batch_linked_clone_vms`, `batch_deploy_from_spec` | Write |
| Guest Ops (5) | `vm_guest_exec_output`, `vm_guest_download` | Read |
| | `vm_guest_exec`, `vm_guest_upload`, `vm_guest_provision` | Write |
| Plan/Apply (4) | `vm_list_plans`, `vm_create_plan` | Read |
| | `vm_apply_plan`, `vm_rollback_plan` | Write |
| Datastore (2) | `browse_datastore`, `scan_datastore_images` | Read |
| Cluster (6) | `cluster_info` | Read |
| | `cluster_create`, `cluster_delete`, `cluster_add_host`, `cluster_remove_host`, `cluster_configure` | Write |
| Alarm Management (3) | `list_vcenter_alarms` | Read |
| | `acknowledge_vcenter_alarm`, `reset_vcenter_alarm` | Write |

**Read/write split**: 20 tools are read-only, 14 modify state. All write tools require explicit parameters and are audit-logged. Destructive operations (delete, force power-off) require double confirmation.

## CLI Quick Reference

```bash
# VM operations
vmware-aiops vm power-on <name> [--target <t>]
vmware-aiops vm power-off <name> [--force]
vmware-aiops vm create <name> --cpu 4 --memory 8192 --disk 100
vmware-aiops vm delete <name>
vmware-aiops vm clone <name> --new-name <new>
vmware-aiops vm migrate <name> --to-host <host>

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
vmware-aiops alarm reset <entity_name> <alarm_name> [--target <t>]

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
