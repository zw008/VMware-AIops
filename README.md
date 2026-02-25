# VMware AIops

AI-powered VMware vCenter/ESXi monitoring and operations tool.

Two modes of operation:
- **Claude Code Skill**: Natural language VMware infrastructure management via Claude
- **CLI + Daemon**: Standalone Python tool for operations and scheduled log/alarm scanning

## Features

- **Multi-target**: Connect to multiple vCenter Servers and standalone ESXi hosts
- **Inventory**: List VMs, hosts, datastores, clusters, networks
- **Health checks**: Active alarms, recent events, hardware sensor status, host services
- **VM lifecycle**: Create, delete, power on/off, reset, suspend, reconfigure (CPU/memory)
- **Snapshots**: Create, list, revert, delete
- **Clone & Migrate**: VM cloning and vMotion
- **Scheduled scanning**: APScheduler daemon scans logs and alarms at configurable intervals
- **Notifications**: Structured JSON log files + generic webhook (Slack, Discord, etc.)

## Installation

### Option A: Claude Code Skill (Natural Language Ops)

In Claude Code, run:

```
/install-plugin zw008/VMware-AIops
```

Or manually:

1. Edit `~/.claude/plugins/known_marketplaces.json`, add:
   ```json
   "vmware-aiops": {
     "source": {
       "source": "github",
       "repo": "zw008/VMware-AIops"
     }
   }
   ```
2. Edit `~/.claude/settings.json`, add to `enabledPlugins`:
   ```json
   "vmware-ops@vmware-aiops": true
   ```
3. Restart Claude Code

Then use natural language directly:
```
"Show me all VMs on prod-vcenter"
"Check if there are any active alarms"
"Take a snapshot of prod-db before the upgrade"
```

### Option B: Python CLI + Daemon

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configure (Required for Both)

```bash
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
# Edit config.yaml with your vCenter/ESXi targets
```

Set passwords via environment variables:
```bash
export VMWARE_PROD_VCENTER_PASSWORD="your-password"
export VMWARE_LAB_ESXI_PASSWORD="your-password"
```

## CLI Usage

```bash
# Inventory
vmware-aiops inventory vms
vmware-aiops inventory hosts --target prod-vcenter
vmware-aiops inventory datastores
vmware-aiops inventory clusters

# Health
vmware-aiops health alarms
vmware-aiops health events --hours 24 --severity warning

# VM operations
vmware-aiops vm info my-vm
vmware-aiops vm power-on my-vm
vmware-aiops vm power-off my-vm
vmware-aiops vm power-off my-vm --force
vmware-aiops vm create my-new-vm --cpu 4 --memory 8192 --disk 100
vmware-aiops vm delete my-vm --confirm
vmware-aiops vm reconfigure my-vm --cpu 4 --memory 8192
vmware-aiops vm snapshot-create my-vm --name "before-upgrade"
vmware-aiops vm snapshot-list my-vm
vmware-aiops vm snapshot-revert my-vm --name "before-upgrade"
vmware-aiops vm clone my-vm --new-name my-vm-clone
vmware-aiops vm migrate my-vm --to-host esxi-02

# Run one-time scan
vmware-aiops scan now

# Start scanner daemon
vmware-aiops daemon start
vmware-aiops daemon status
```

## Configuration

See `config.example.yaml` for all options:

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| targets | name | — | Friendly name for the target |
| targets | host | — | vCenter/ESXi hostname or IP |
| targets | type | vcenter | `vcenter` or `esxi` |
| targets | verify_ssl | false | SSL certificate verification |
| scanner | interval_minutes | 15 | Scan frequency |
| scanner | severity_threshold | warning | Min severity: critical/warning/info |
| scanner | lookback_hours | 1 | How far back to scan |
| notify | log_file | ~/.vmware-aiops/scan.log | JSONL log output |
| notify | webhook_url | — | Webhook endpoint for alerts |

## Architecture

```
vmware_aiops/
├── config.py          # YAML + env var configuration
├── connection.py      # Multi-target pyVmomi connection manager
├── cli.py             # Typer CLI entry point
├── ops/
│   ├── inventory.py   # VMs, hosts, datastores, clusters, networks
│   ├── health.py      # Alarms, events, hardware, services
│   └── vm_lifecycle.py # Create, delete, power, snapshot, clone, migrate
├── scanner/
│   ├── log_scanner.py    # Event + host syslog scanning
│   ├── alarm_scanner.py  # Triggered alarm scanning
│   └── scheduler.py      # APScheduler daemon
└── notify/
    ├── logger.py      # JSONL structured logging
    └── webhook.py     # Generic webhook sender
```

## API Coverage

Built on **pyVmomi** (vSphere Web Services API / SOAP). Key managed objects:

- `vim.VirtualMachine` — VM lifecycle and configuration
- `vim.HostSystem` — ESXi host management
- `vim.Datastore` — Storage
- `vim.ClusterComputeResource` — Cluster configuration (DRS, HA)
- `vim.Network` — Networking
- `vim.alarm.AlarmManager` — Alarm management
- `vim.event.EventManager` — Event/log queries

## License

MIT
