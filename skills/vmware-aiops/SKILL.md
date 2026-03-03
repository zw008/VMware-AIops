---
name: vmware-aiops
description: >
  AI-powered VMware vCenter/ESXi monitoring and operations.
  Manage infrastructure via natural language: inventory queries, health monitoring,
  VM lifecycle (create, delete, power, snapshot, clone, migrate), vSAN management,
  Aria Operations analytics, Kubernetes clusters, and scheduled log scanning.
installer:
  kind: uv
  package: vmware-aiops
---

# VMware AIops

AI-powered VMware vCenter and ESXi operations tool. Manage your entire VMware infrastructure using natural language through any AI coding assistant.

> **Need read-only monitoring only?** Use [VMware-Monitor](https://github.com/zw008/VMware-Monitor) — an independent repository with code-level safety (zero destructive code in the codebase). Install: `clawhub install vmware-monitor`

## When to Use This Skill

- Query VM, host, datastore, cluster, and network inventory
- Check health status, active alarms, hardware sensors, and event logs
- Perform VM lifecycle operations: power on/off, create, delete, snapshot, clone, migrate
- Monitor vSAN health, capacity, disk groups, and performance
- Access Aria Operations (VCF Operations) for historical metrics, anomaly detection, and capacity planning
- Manage vSphere Kubernetes Service (VKS) clusters
- Run scheduled scanning with webhook notifications (Slack, Discord)

## Quick Install

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, Kimi, and 30+ AI agents:

```bash
# Via ClawHub (recommended)
clawhub install vmware-aiops

# Via Skills.sh
npx skills add zw008/VMware-AIops
```

### Claude Code

```
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
/vmware-ops:vmware-aiops
```

## Usage Mode: MCP First, CLI Fallback

**Default: MCP mode** — vmware-aiops runs as an MCP Server registered in the AI tool. All queries and operations go through MCP tool calls directly, no manual CLI needed.

**Fallback: CLI mode** — only when MCP connection fails (server crash, config error, etc.), switch to CLI commands via `vmware-aiops` in the terminal.

### MCP Tools (9 tools)

| MCP Tool | Type | Description | Equivalent CLI |
|----------|------|-------------|----------------|
| `list_virtual_machines` | Read | List all VMs | `vmware-aiops inventory vms` |
| `list_esxi_hosts` | Read | List ESXi hosts | `vmware-aiops inventory hosts` |
| `list_all_datastores` | Read | List datastores | `vmware-aiops inventory datastores` |
| `list_all_clusters` | Read | List clusters | `vmware-aiops inventory clusters` |
| `get_alarms` | Read | Active alarms | `vmware-aiops health alarms` |
| `get_events` | Read | Recent events | `vmware-aiops health events` |
| `vm_info` | Read | VM details | `vmware-aiops vm info <name>` |
| `vm_power_on` | **Write** | Power on VM | `vmware-aiops vm power-on <name>` |
| `vm_power_off` | **Write** | Power off VM | `vmware-aiops vm power-off <name>` |

All tools accept optional `target` parameter (e.g., `"home-esxi"`, `"prod-vcenter"`).

### MCP Direct Calling Pattern (Default)

When this skill is activated, **always use direct Python import** to call MCP tools:

```python
# cd /path/to/VMware-AIops

from mcp_server.server import (
    list_virtual_machines,
    list_esxi_hosts,
    list_all_datastores,
    list_all_clusters,
    get_alarms,
    get_events,
    vm_info,
    vm_power_on,
    vm_power_off,
)

# Read operations
result = list_virtual_machines(target='home-esxi')
alarms = get_alarms(target='home-vcenter')
info = vm_info(vm_name='my-vm', target='home-esxi')

# Write operations (require user confirmation)
vm_power_on(vm_name='my-vm', target='home-esxi')
vm_power_off(vm_name='my-vm', force=False, target='home-esxi')
```

**Calling priority:**
1. ✅ Direct import from `mcp_server.server` (fastest, default)
2. ⚠️ CLI fallback: `vmware-aiops inventory vms` (when import fails)

### MCP Setup (Claude Code)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "/path/to/VMware-AIops/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/VMware-AIops",
      "env": {
        "VMWARE_AIOPS_CONFIG": "~/.vmware-aiops/config.yaml"
      }
    }
  }
}
```

### When to Fall Back to CLI

- MCP server fails to start or crashes mid-session
- Need operations not yet exposed via MCP (create, delete, snapshot, clone, migrate, vSAN, Aria, VKS)
- Need daemon/scan features (`scan now`, `daemon start`)
- Debugging connection issues (CLI gives more verbose output)

```bash
# Activate venv and run CLI
source /path/to/VMware-AIops/.venv/bin/activate
vmware-aiops inventory vms --target home-esxi
```

## Architecture

```
User (Natural Language)
  ↓
AI CLI Tool (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓
  ├─ MCP mode (default): MCP Server (stdio) ──→ pyVmomi ──→ vSphere API
  │
  └─ CLI fallback: vmware-aiops CLI ──→ pyVmomi ──→ vSphere API
  ↓
vCenter Server ──→ ESXi Clusters ──→ VMs
    or
ESXi Standalone ──→ VMs
```

## Capabilities

### 1. Inventory

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| List VMs | ✅ | ✅ | Name, power state, CPU, memory, guest OS, IP |
| List Hosts | ✅ | ⚠️ Self only | CPU cores, memory, ESXi version, VM count, uptime |
| List Datastores | ✅ | ✅ | Capacity, free/used, type (VMFS/NFS), usage % |
| List Clusters | ✅ | ❌ | Host count, DRS/HA status |
| List Networks | ✅ | ✅ | Network name, associated VM count |

### 2. Health & Monitoring

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| Active Alarms | ✅ | ✅ | Severity, alarm name, entity, timestamp |
| Event/Log Query | ✅ | ✅ | Filter by time range, severity; 50+ event types |
| Hardware Sensors | ✅ | ✅ | Temperature, voltage, fan status |
| Host Services | ✅ | ✅ | hostd, vpxa running/stopped status |

**Monitored Event Types:**

| Category | Events |
|----------|--------|
| VM Failures | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage | `DatastoreCapacityIncreasedEvent`, SCSI high latency |
| HA/DRS | `DasHostFailedEvent`, `DrsVmMigratedEvent`, `DrsSoftRuleViolationEvent` |
| Auth | `UserLoginSessionEvent`, `BadUsernameSessionEvent` |

### 3. VM Lifecycle

| Operation | Command | Confirmation | vCenter | ESXi |
|-----------|---------|:------------:|:-------:|:----:|
| Power On | `vm power-on <name>` | — | ✅ | ✅ |
| Graceful Shutdown | `vm power-off <name>` | Double | ✅ | ✅ |
| Force Power Off | `vm power-off <name> --force` | Double | ✅ | ✅ |
| Reset | `vm reset <name>` | — | ✅ | ✅ |
| Suspend | `vm suspend <name>` | — | ✅ | ✅ |
| VM Info | `vm info <name>` | — | ✅ | ✅ |
| Create VM | `vm create <name> --cpu --memory --disk` | — | ✅ | ✅ |
| Delete VM | `vm delete <name>` | Double | ✅ | ✅ |
| Reconfigure | `vm reconfigure <name> --cpu --memory` | Double | ✅ | ✅ |
| Create Snapshot | `vm snapshot-create <name> --name <snap>` | — | ✅ | ✅ |
| List Snapshots | `vm snapshot-list <name>` | — | ✅ | ✅ |
| Revert Snapshot | `vm snapshot-revert <name> --name <snap>` | — | ✅ | ✅ |
| Delete Snapshot | `vm snapshot-delete <name> --name <snap>` | — | ✅ | ✅ |
| Clone VM | `vm clone <name> --new-name <new>` | — | ✅ | ✅ |
| vMotion | `vm migrate <name> --to-host <host>` | — | ✅ | ❌ |

### 4. vSAN Management

| Feature | Details |
|---------|---------|
| Health Check | Cluster-wide health summary, per-group test results |
| Capacity | Total/free/used capacity with projections |
| Disk Groups | Cache SSD + capacity disks per host |
| Performance | IOPS, latency, throughput per cluster/host/VM |

> Requires pyVmomi 8.0.3+ (vSAN SDK merged). For older versions, install the standalone vSAN Management SDK.

### 5. Aria Operations (VCF Operations)

| Feature | Details |
|---------|---------|
| Historical Metrics | Time-series CPU, memory, disk, network with months of history |
| Anomaly Detection | ML-based dynamic baselines and anomaly alerts |
| Capacity Planning | What-if analysis, time-to-exhaustion, forecasting |
| Right-sizing | CPU/memory recommendations per VM |
| Intelligent Alerts | Root cause analysis, remediation recommendations |

> REST API at `/suite-api/`. Auth: `vRealizeOpsToken`. Rebranded as VCF Operations in VCF 9.0.

### 6. vSphere Kubernetes Service (VKS)

| Feature | Details |
|---------|---------|
| List Clusters | Tanzu Kubernetes clusters with phase status |
| Cluster Health | InfrastructureReady, ControlPlaneAvailable, WorkersAvailable |
| Scale Workers | Adjust MachineDeployment replicas |
| Node Status | Machine status, ready/unhealthy counts |

> Kubernetes-native API via kubectl/kubeconfig. VKS 3.6+ uses Cluster API specification.

### 7. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout |
| Webhook | Slack, Discord, or any HTTP endpoint |

## Safety Features

| Feature | Details |
|---------|---------|
| Plan → Confirm → Execute → Log | Structured workflow: show current state, confirm changes, execute, audit log |
| Double Confirmation | All destructive ops (power-off, delete, reconfigure, snapshot-revert/delete, clone, migrate) require 2 sequential confirmations — no bypass flags |
| Rejection Logging | Declined confirmations are recorded in the audit trail for security review |
| Audit Trail | All operations logged to `~/.vmware-aiops/audit.log` (JSONL) with before/after state |
| Input Validation | VM name length/format, CPU (1-128), memory (128-1048576 MB), disk (1-65536 GB) validated before execution |
| Password Protection | `.env` file loading, never in command line or shell history; file permission check at startup |
| SSL Self-signed Support | `disableSslCertValidation` — **only** for ESXi hosts with self-signed certificates in isolated lab/home environments. Production environments should use CA-signed certificates with full TLS verification enabled. |
| Task Waiting | All async operations wait for completion and report result |
| State Validation | Pre-operation checks (VM exists, power state correct) |

## Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | `CreateSnapshot_Task` deprecated → use `CreateSnapshotEx_Task` |
| 7.0 / 7.0U1-U3 | ✅ Full | All APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed.

## Supported AI Platforms

| Platform | Status | Config File |
|----------|--------|-------------|
| Claude Code | ✅ Native Skill | `plugins/.../SKILL.md` |
| Gemini CLI | ✅ Extension | `gemini-extension/GEMINI.md` |
| OpenAI Codex CLI | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` |
| Aider | ✅ Conventions | `codex-skill/AGENTS.md` |
| Continue CLI | ✅ Rules | `codex-skill/AGENTS.md` |
| Trae IDE | ✅ Rules | `trae-rules/project_rules.md` |
| Kimi Code CLI | ✅ Skill | `kimi-skill/SKILL.md` |
| MCP Server | ✅ MCP Protocol | `mcp_server/` |
| Python CLI | ✅ Standalone | N/A |

## CLI Reference

```bash
# Inventory
vmware-aiops inventory vms [--target <name>]
vmware-aiops inventory hosts [--target <name>]
vmware-aiops inventory datastores [--target <name>]
vmware-aiops inventory clusters [--target <name>]

# Health
vmware-aiops health alarms [--target <name>]
vmware-aiops health events [--hours 24] [--severity warning]

# VM Operations
vmware-aiops vm info <vm-name>
vmware-aiops vm power-on <vm-name>
vmware-aiops vm power-off <vm-name> [--force]
vmware-aiops vm create <name> [--cpu <n>] [--memory <mb>] [--disk <gb>]
vmware-aiops vm delete <vm-name> [--confirm]
vmware-aiops vm reconfigure <vm-name> [--cpu <n>] [--memory <mb>]
vmware-aiops vm snapshot-create <vm-name> --name <snap-name>
vmware-aiops vm snapshot-list <vm-name>
vmware-aiops vm snapshot-revert <vm-name> --name <snap-name>
vmware-aiops vm snapshot-delete <vm-name> --name <snap-name>
vmware-aiops vm clone <vm-name> --new-name <name>
vmware-aiops vm migrate <vm-name> --to-host <host>

# vSAN
vmware-aiops vsan health [--target <name>]
vmware-aiops vsan capacity [--target <name>]
vmware-aiops vsan disks [--target <name>]
vmware-aiops vsan performance [--hours 1]

# Aria Operations
vmware-aiops ops alerts [--severity critical]
vmware-aiops ops metrics <resource-name> [--hours 24]
vmware-aiops ops recommendations [--target <name>]
vmware-aiops ops capacity <cluster-name>

# VKS (Kubernetes)
vmware-aiops vks clusters [--namespace default]
vmware-aiops vks health <cluster-name>
vmware-aiops vks scale <machine-deployment> --replicas <n>
vmware-aiops vks nodes <cluster-name>

# Scanning & Daemon
vmware-aiops scan now [--target <name>]
vmware-aiops daemon start
vmware-aiops daemon stop
vmware-aiops daemon status
```

## Setup

```bash
# 1. Install via uv (recommended) or pip
uv tool install vmware-aiops
# Or: pip install vmware-aiops

# 2. Configure
mkdir -p ~/.vmware-aiops
vmware-aiops init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-aiops/.env
# Edit ~/.vmware-aiops/config.yaml and .env with your target details
```

### Development Install

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Security

- **TLS Verification**: Enabled by default. The `disableSslCertValidation` option exists solely for ESXi hosts using self-signed certificates (common in home labs). In production, always use CA-signed certificates with full TLS verification.
- **Credentials**: Loaded exclusively from environment variables via `.env` file (`chmod 600`). Never passed in CLI arguments, config files, or MCP messages.
- **Webhook Data Scope**: Webhook notifications send infrastructure summaries to **user-configured URLs only** (Slack, Discord, or any HTTP endpoint you control). No data is sent to third-party services by default.
- **Prompt Injection Protection**: All vSphere-sourced content (event messages, host logs) is truncated, stripped of control characters, and wrapped in boundary markers before output.
- **Code Review**: We recommend reviewing the source code and commit history before deploying in production. Run in an isolated environment for initial evaluation.

## License

MIT
