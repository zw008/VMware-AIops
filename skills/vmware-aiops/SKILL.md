---
name: vmware-aiops
description: >
  VMware family entry point and AI-powered VM lifecycle operations.
  Start here for any VMware/vSphere/ESXi task — routes to the right skill.
  Directly handles: power on/off, snapshot, clone, migrate, deploy OVA/template,
  guest operations, cluster management, plan/apply workflows.
  Use when user asks to "power on/off a VM", "deploy from OVA", "clone a VM",
  "create a cluster", "run a command inside a VM", "batch deploy VMs",
  "migrate a VM", or any VMware/vSphere/ESXi operation.
  Run "vmware-aiops hub status" to see all installed family members.
installer:
  kind: uv
  package: vmware-aiops
argument-hint: "[vm-name or describe your task]"
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_AIOPS_CONFIG"],"bins":["vmware-aiops"],"config":["~/.vmware-aiops/config.yaml","~/.vmware-aiops/.env"]},"optional":{"env":["SLACK_WEBHOOK_URL","DISCORD_WEBHOOK_URL"]},"primaryEnv":"VMWARE_AIOPS_CONFIG","homepage":"https://github.com/zw008/VMware-AIops","emoji":"🖥️","os":["macos","linux"]}}
---

# VMware AIops

VMware family entry point — AI-powered VM lifecycle and deployment — 31 MCP tools.

> **Start here**: install vmware-aiops first, then add modules as needed.
> Run `vmware-aiops hub status` to see which family members are installed.
> **Family**: [vmware-monitor](https://github.com/zw008/VMware-Monitor) (inventory/health), [vmware-storage](https://github.com/zw008/VMware-Storage) (iSCSI/vSAN), [vmware-vks](https://github.com/zw008/VMware-VKS) (Tanzu Kubernetes), [vmware-nsx](https://github.com/zw008/VMware-NSX) (NSX networking), [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity).

## What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **VM Lifecycle** | power on/off, TTL auto-delete, clean slate | 6 |
| **Deployment** | OVA, template, linked clone, batch clone/deploy | 8 |
| **Guest Ops** | exec commands, upload/download files, provision | 5 |
| **Plan/Apply** | multi-step planning with rollback | 4 |
| **Cluster** | create, delete, HA/DRS config, add/remove hosts | 6 |
| **Datastore** | browse files, scan for images | 2 |

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

> Each module stays independent — small tool count keeps local models (Ollama, Qwen) accurate.

## When to Use This Skill

- Power on/off, create, delete, snapshot, clone, or migrate VMs
- Deploy VMs from OVA, templates, linked clones, or batch specs
- Run commands or transfer files inside a VM (Guest Operations)
- Create/configure clusters (HA/DRS)
- Browse datastores for deployable images
- Plan and execute multi-step operations with rollback

**Use companion skills for**:
- Inventory, health, alarms, VM info → `vmware-monitor`
- iSCSI, vSAN, datastore management → `vmware-storage`
- Tanzu Kubernetes (Supervisor, Namespace, TKC) → `vmware-vks`

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

## Common Workflows

### Deploy a Lab Environment
1. Browse datastore for OVA images → `vmware-aiops datastore browse <ds> --pattern "*.ova"`
2. Deploy VM from OVA → `vmware-aiops deploy ova ./image.ova --name lab-vm --datastore ds1`
3. Install software inside VM → `vmware-aiops vm guest-exec lab-vm --cmd /bin/bash --args "-c 'apt-get install -y nginx'" --user root`
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

## MCP Tools (31)

| Category | Tools |
|----------|-------|
| VM Lifecycle (6) | `vm_power_on`, `vm_power_off`, `vm_set_ttl`, `vm_cancel_ttl`, `vm_list_ttl`, `vm_clean_slate` |
| Deployment (8) | `deploy_vm_from_ova`, `deploy_vm_from_template`, `deploy_linked_clone`, `attach_iso_to_vm`, `convert_vm_to_template`, `batch_clone_vms`, `batch_linked_clone_vms`, `batch_deploy_from_spec` |
| Guest Ops (5) | `vm_guest_exec`, `vm_guest_exec_output`, `vm_guest_upload`, `vm_guest_download`, `vm_guest_provision` |
| Plan/Apply (4) | `vm_create_plan`, `vm_apply_plan`, `vm_rollback_plan`, `vm_list_plans` |
| Datastore (2) | `browse_datastore`, `scan_datastore_images` |
| Cluster (6) | `cluster_create`, `cluster_delete`, `cluster_add_host`, `cluster_remove_host`, `cluster_configure`, `cluster_info` |

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
vmware-aiops vm guest-exec <name> --cmd /bin/bash --args "-c 'whoami'" --user root
vmware-aiops vm guest-upload <name> --local ./script.sh --guest /tmp/script.sh --user root

# Deploy
vmware-aiops deploy ova <path> --name <vm> --datastore <ds>
vmware-aiops deploy linked-clone --source <vm> --snapshot <snap> --name <new>

# Cluster
vmware-aiops cluster create <name> --ha --drs
vmware-aiops cluster info <name>

# Datastore
vmware-aiops datastore browse <ds> --pattern "*.ova"

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

> Full setup guide, security details, and AI platform compatibility: see `references/setup-guide.md`

## License

MIT — [github.com/zw008/VMware-AIops](https://github.com/zw008/VMware-AIops)
