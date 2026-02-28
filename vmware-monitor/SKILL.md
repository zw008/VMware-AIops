---
name: vmware-monitor
description: >
  VMware vCenter/ESXi read-only monitoring skill (safe version).
  Query inventory, check health/alarms/events, view VM info and snapshots,
  monitor vSAN and Aria Operations metrics, scan logs.
  NO destructive operations — no power off, delete, or reconfigure.
  For full operations, use vmware-aiops skill.
---

# VMware Monitor (Read-Only)

Safe, read-only VMware vCenter and ESXi monitoring skill. Query your entire VMware infrastructure using natural language through any AI coding assistant — without risk of accidental modifications.

> **This is the safe version.** For VM lifecycle operations (power, create, delete, snapshot, clone, migrate), use the full [vmware-aiops](../vmware-aiops/SKILL.md) skill.

## When to Use This Skill

- Query VM, host, datastore, cluster, and network inventory
- Check health status, active alarms, hardware sensors, and event logs
- View VM details and list existing snapshots (read-only)
- Monitor vSAN health, capacity, disk groups, and performance
- Access Aria Operations (VCF Operations) for historical metrics, anomaly detection, and capacity planning
- View vSphere Kubernetes Service (VKS) cluster status
- Run scheduled scanning with webhook notifications (Slack, Discord)

## When NOT to Use This Skill

- Power on/off, reset, suspend VMs → use **vmware-aiops**
- Create, delete, reconfigure VMs → use **vmware-aiops**
- Create, revert, delete snapshots → use **vmware-aiops**
- Clone or migrate VMs → use **vmware-aiops**
- Scale VKS worker nodes → use **vmware-aiops**

## Quick Install

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, Kimi, and 30+ AI agents:

```bash
npx skills add zw008/VMware-AIops
```

### Claude Code

```
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
/vmware-ops:vmware-monitor
```

## Capabilities (Read-Only)

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

### 3. VM Info & Snapshot List (Read-Only)

| Feature | Details |
|---------|---------|
| VM Info | Name, power state, guest OS, CPU, memory, IP, VMware Tools, disks |
| Snapshot List | List existing snapshots with name and creation time (no create/revert/delete) |

### 4. vSAN Monitoring (Read-Only)

| Feature | Details |
|---------|---------|
| Health Check | Cluster-wide health summary, per-group test results |
| Capacity | Total/free/used capacity with projections |
| Disk Groups | Cache SSD + capacity disks per host |
| Performance | IOPS, latency, throughput per cluster/host/VM |

### 5. Aria Operations (Read-Only)

| Feature | Details |
|---------|---------|
| Historical Metrics | Time-series CPU, memory, disk, network |
| Anomaly Detection | ML-based dynamic baselines and anomaly alerts |
| Capacity Planning | What-if analysis, time-to-exhaustion, forecasting |
| Right-sizing | CPU/memory recommendations per VM |
| Intelligent Alerts | Root cause analysis, remediation recommendations |

### 6. VKS (Read-Only)

| Feature | Details |
|---------|---------|
| List Clusters | Tanzu Kubernetes clusters with phase status |
| Cluster Health | InfrastructureReady, ControlPlaneAvailable, WorkersAvailable |
| Node Status | Machine status, ready/unhealthy counts |

### 7. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured targets |
| Webhook | Slack, Discord, or any HTTP endpoint |

## Query Audit Trail

All queries are logged to `~/.vmware-aiops/audit.log` (JSONL) for compliance:

```jsonl
{"timestamp": "2025-01-15T10:30:00Z", "target": "vcenter-prod", "operation": "query", "resource": "VirtualMachine", "query_type": "inventory_vms", "skill": "monitor"}
```

This provides a complete record of what was accessed and when — useful for security audits and compliance reporting.

## CLI Reference (Read-Only Only)

```bash
# Inventory
vmware-aiops inventory vms|hosts|datastores|clusters [--target <name>]

# Health
vmware-aiops health alarms [--target <name>]
vmware-aiops health events [--hours 24] [--severity warning]

# VM Info (read-only)
vmware-aiops vm info <vm-name>
vmware-aiops vm snapshot-list <vm-name>

# vSAN (read-only)
vmware-aiops vsan health|capacity|disks|performance [--target <name>]

# Aria Operations (read-only)
vmware-aiops ops alerts|metrics|recommendations|capacity [--target <name>]

# VKS (read-only)
vmware-aiops vks clusters|health|nodes

# Scanning & Daemon
vmware-aiops scan now [--target <name>]
vmware-aiops daemon start|stop|status
```

> **Commands NOT available:** `vm power-on/off`, `vm create/delete/reconfigure`, `vm snapshot-create/revert/delete`, `vm clone/migrate`, `vks scale`. Use **vmware-aiops** for these.

## Setup

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
cp .env.example ~/.vmware-aiops/.env
chmod 600 ~/.vmware-aiops/.env
```

## License

MIT
