# VMware AIops

English | [中文](README-CN.md)

AI-powered VMware vCenter/ESXi monitoring and operations tool.

> **Need read-only monitoring only?** See [VMware-Monitor](https://github.com/zw008/VMware-Monitor) — an independent repository with code-level safety (zero destructive code in the codebase).

[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-AIops)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-AIops)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### Quick Install (Recommended)

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, and 30+ AI agents:

```bash
npx skills add zw008/VMware-AIops
```

### Claude Code Plugin Install

```bash
# Add marketplace
/plugin marketplace add zw008/VMware-AIops

# Install plugin
/plugin install vmware-ops

# Use the skill
/vmware-ops:vmware-aiops
```

---

## Capabilities Overview

### Architecture

```
User (Natural Language)
  ↓
AI CLI Tool (Claude Code / Gemini / Codex / Aider / Continue / Trae / Kimi)
  ↓ reads SKILL.md / AGENTS.md / rules
  ↓
vmware-aiops CLI
  ↓ pyVmomi (vSphere SOAP API)
  ↓
vCenter Server ──→ ESXi Cluster ──→ VM
    or
ESXi Standalone Host ──→ VM
```

### Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | ✅ Full | `CreateSnapshot_Task` deprecated → use `CreateSnapshotEx_Task` |
| 7.0 / 7.0U1-U3 | ✅ Full | All APIs supported |
| 6.7 | ✅ Compatible | Backward-compatible, tested |
| 6.5 | ✅ Compatible | Backward-compatible, tested |

> pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed. The same codebase manages both 7.0 and 8.0 environments seamlessly.

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
| Event/Log Query | ✅ | ✅ | Filter by time range (--hours), severity level; 50+ event types |
| Hardware Sensors | ✅ | ✅ | Temperature, voltage, fan status |
| Host Services | ✅ | ✅ | hostd, vpxa, etc. running/stopped |

**Monitored Event Types**:

| Category | Events |
|----------|--------|
| VM Failures | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage | `DatastoreCapacityIncreasedEvent`, `NASDatastoreEvent`, SCSI high latency |
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

### 4. Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout, corrupt |
| Structured Log | JSONL output to `~/.vmware-aiops/scan.log` |
| Webhook | Slack, Discord, or any HTTP endpoint |
| Daemon Management | `daemon start/stop/status`, PID file, graceful shutdown |

### 5. Safety Features

| Feature | Details |
|---------|---------|
| **Dry-Run Mode** | `--dry-run` on any destructive command prints exact API calls without executing |
| **Plan → Confirm → Execute → Log** | Structured workflow: show current state, confirm changes, execute, audit log |
| **Double Confirmation** | All destructive ops (power-off, delete, reconfigure, snapshot-revert/delete, clone, migrate) require 2 sequential confirmations — no bypass flags |
| **Rejection Logging** | Declined confirmations are recorded in the audit trail |
| **Audit Trail** | All operations logged to `~/.vmware-aiops/audit.log` (JSONL) with before/after state |
| **Input Validation** | VM name, CPU (1-128), memory (128-1048576 MB), disk (1-65536 GB) validated |
| **Password Protection** | `.env` file loading with permission check; never in shell history |
| **SSL Self-signed Support** | `disableSslCertValidation` for ESXi 8.0 self-signed certs |
| **Task Waiting** | All async operations wait for completion and report result |
| **State Validation** | Pre-operation checks (VM exists, power state correct) |

### 6. vSAN Management

| Feature | Details |
|---------|---------|
| Health Check | Cluster-wide health summary, per-group test results |
| Capacity | Total/free/used capacity with projections |
| Disk Groups | Cache SSD + capacity disks per host |
| Performance | IOPS, latency, throughput per cluster/host/VM |

> Requires pyVmomi 8.0.3+ (vSAN SDK merged). For older versions, install the standalone vSAN Management SDK.

### 7. Aria Operations / VCF Operations

| Feature | Details |
|---------|---------|
| Historical Metrics | Time-series CPU, memory, disk, network with months of history |
| Anomaly Detection | ML-based dynamic baselines and anomaly alerts |
| Capacity Planning | What-if analysis, time-to-exhaustion, forecasting |
| Right-sizing | CPU/memory recommendations per VM |
| Intelligent Alerts | Root cause analysis, remediation recommendations |

> REST API at `/suite-api/`. Auth: `vRealizeOpsToken`. Rebranded as VCF Operations in VCF 9.0.

### 8. vSphere Kubernetes Service (VKS)

| Feature | Details |
|---------|---------|
| List Clusters | Tanzu Kubernetes clusters with phase status |
| Cluster Health | InfrastructureReady, ControlPlaneAvailable, WorkersAvailable conditions |
| Scale Workers | Adjust MachineDeployment replicas |
| Node Status | Machine status, ready/unhealthy counts |

> Kubernetes-native API via kubectl/kubeconfig. VKS 3.6+ uses Cluster API specification.

### 9. vCenter vs ESXi Comparison

| Capability | vCenter | ESXi Standalone |
|------------|:-------:|:----:|
| Full cluster inventory | ✅ | ❌ Single host only |
| DRS/HA management | ✅ | ❌ |
| vMotion migration | ✅ | ❌ |
| Cross-host clone | ✅ | ❌ |
| All VM lifecycle ops | ✅ | ✅ |
| Alarms & events | ✅ | ✅ |
| Hardware sensors | ✅ | ✅ |
| Host services | ✅ | ✅ |
| Snapshots | ✅ | ✅ |
| Scheduled scanning | ✅ | ✅ |

---

## Supported AI Platforms

| Platform | Status | Config File | AI Model |
|----------|--------|-------------|----------|
| **Claude Code** | ✅ Native Skill | `skills/vmware-aiops/SKILL.md` | Anthropic Claude |
| **Gemini CLI** | ✅ Extension | `gemini-extension/GEMINI.md` | Google Gemini |
| **OpenAI Codex CLI** | ✅ Skill + AGENTS.md | `codex-skill/AGENTS.md` | OpenAI GPT |
| **Aider** | ✅ Conventions | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Continue CLI** | ✅ Rules | `codex-skill/AGENTS.md` | Any (cloud + local) |
| **Trae IDE** | ✅ Rules | `trae-rules/project_rules.md` | Claude/DeepSeek/GPT-4o/Doubao |
| **Kimi Code CLI** | ✅ Skill | `kimi-skill/SKILL.md` | Moonshot Kimi |
| **MCP Server** | ✅ MCP Protocol | `mcp_server/` | Any MCP client |
| **Python CLI** | ✅ Standalone | N/A | N/A |

### Platform Comparison

| Feature | Claude Code | Gemini CLI | Codex CLI | Aider | Continue | Trae IDE | Kimi CLI |
|---------|-------------|------------|-----------|-------|----------|----------|----------|
| Cloud AI | Anthropic | Google | OpenAI | Any | Any | Multi | Moonshot |
| Local models | — | — | — | Ollama | Ollama | — | — |
| Skill system | SKILL.md | Extension | SKILL.md | — | Rules | Rules | SKILL.md |
| MCP support | Native | Native | Via Skills | Third-party | Native | — | — |
| Free tier | — | 60 req/min | — | Self-hosted | Self-hosted | — | — |

---

## Installation

### Step 0: Prerequisites

```bash
# Python 3.10+ required
python3 --version

# Node.js 18+ required for Gemini CLI and Codex CLI
node --version
```

### Step 1: Clone & Install Python Backend

All platforms share the same Python backend.

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Step 2: Configure

```bash
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
# Edit config.yaml with your vCenter/ESXi targets
```

Set passwords via `.env` file (recommended):
```bash
# Use the template
cp .env.example ~/.vmware-aiops/.env

# Edit and fill in your passwords, then lock permissions
chmod 600 ~/.vmware-aiops/.env
```

> **Security note**: Prefer `.env` file over command-line `export` to avoid passwords appearing in shell history. The `.env` file should have `chmod 600` (owner-only read/write).

Password environment variable naming convention:
```
VMWARE_{TARGET_NAME_UPPER}_PASSWORD
# Replace hyphens with underscores, UPPERCASE
# Example: target "home-esxi" → VMWARE_HOME_ESXI_PASSWORD
# Example: target "prod-vcenter" → VMWARE_PROD_VCENTER_PASSWORD
```

### Security Best Practices

- **NEVER** hardcode passwords in scripts or config files
- **NEVER** pass passwords as command-line arguments (visible in `ps`)
- **ALWAYS** use `~/.vmware-aiops/.env` with `chmod 600`
- **ALWAYS** use `ConnectionManager.from_config()` for connections
- Passwords are loaded automatically from `.env` at module import time

### Step 3: Connect Your AI Tool

Choose one (or more) of the following:

---

#### Option A: Claude Code (Marketplace)

**Method 1: Marketplace (recommended)**

In Claude Code, run:
```
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
```

Then use:
```
/vmware-ops:vmware-aiops
> Show me all VMs on esxi-lab.example.com
```

**Method 2: Local install**

```bash
# Clone and symlink
git clone https://github.com/zw008/VMware-AIops.git
ln -sf $(pwd)/VMware-AIops ~/.claude/plugins/marketplaces/vmware-aiops

# Register marketplace
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/plugins/known_marketplaces.json'
d = json.loads(f.read_text()) if f.exists() else {}
d['vmware-aiops'] = {
    'source': {'source': 'github', 'repo': 'zw008/VMware-AIops'},
    'installLocation': str(pathlib.Path.home() / '.claude/plugins/marketplaces/vmware-aiops')
}
f.write_text(json.dumps(d, indent=2))
"

# Enable plugin
python3 -c "
import json, pathlib
f = pathlib.Path.home() / '.claude/settings.json'
d = json.loads(f.read_text()) if f.exists() else {}
d.setdefault('enabledPlugins', {})['vmware-ops@vmware-aiops'] = True
f.write_text(json.dumps(d, indent=2))
"
```

Restart Claude Code, then:
```
/vmware-ops:vmware-aiops
```

**Submit to Official Marketplace**

This plugin can also be submitted to the [Anthropic official plugin directory](https://clau.de/plugin-directory-submission) for public discovery.

---

#### Option B: Gemini CLI

```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Install the extension from the cloned repo
gemini extensions install ./gemini-extension

# Or install directly from GitHub
# gemini extensions install https://github.com/zw008/VMware-AIops
```

Then start Gemini CLI:
```
gemini
> Show me all VMs on my ESXi host
```

---

#### Option C: OpenAI Codex CLI

```bash
# Install Codex CLI
npm i -g @openai/codex
# Or on macOS:
# brew install --cask codex

# Copy skill to Codex skills directory
mkdir -p ~/.codex/skills/vmware-aiops
cp codex-skill/SKILL.md ~/.codex/skills/vmware-aiops/SKILL.md

# Copy AGENTS.md to project root
cp codex-skill/AGENTS.md ./AGENTS.md
```

Then start Codex CLI:
```bash
codex --enable skills
> List all VMs on my ESXi
```

---

#### Option D: Aider (supports local models)

```bash
# Install Aider
pip install aider-chat

# Install Ollama for local models (optional)
# macOS:
brew install ollama
ollama pull qwen2.5-coder:32b

# Run with cloud API
aider --conventions codex-skill/AGENTS.md

# Or with local model via Ollama
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b
```

---

#### Option E: Continue CLI (supports local models)

```bash
# Install Continue CLI
npm i -g @continuedev/cli

# Copy rules file
mkdir -p .continue/rules
cp codex-skill/AGENTS.md .continue/rules/vmware-aiops.md
```

Configure `~/.continue/config.yaml` for local model:
```yaml
models:
  - name: local-coder
    provider: ollama
    model: qwen2.5-coder:32b
```

Then:
```bash
cn
> Check ESXi health and alarms
```

---

#### Option F: Trae IDE

Copy the rules file to your project's `.trae/rules/` directory:

```bash
mkdir -p .trae/rules
cp trae-rules/project_rules.md .trae/rules/project_rules.md
```

Trae IDE's Builder Mode reads `.trae/rules/` Markdown files at startup.

> **Note**: You can also install Claude Code extension in Trae IDE and use `.claude/skills/` format directly.

---

#### Option G: Kimi Code CLI

```bash
# Copy skill file to Kimi skills directory
mkdir -p ~/.kimi/skills/vmware-aiops
cp kimi-skill/SKILL.md ~/.kimi/skills/vmware-aiops/SKILL.md
```

---

#### Option H: MCP Server (Smithery / Glama / Claude Desktop)

The MCP server exposes VMware operations as tools via the [Model Context Protocol](https://modelcontextprotocol.io). Works with any MCP-compatible client (Claude Desktop, Cursor, etc.).

```bash
# Run directly
python -m mcp_server

# Or via the installed entry point
vmware-aiops-mcp

# With a custom config path
VMWARE_AIOPS_CONFIG=/path/to/config.yaml python -m mcp_server
```

**Claude Desktop config** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "env": {
        "VMWARE_AIOPS_CONFIG": "/path/to/config.yaml"
      }
    }
  }
}
```

**Install via Smithery**:
```bash
npx -y @smithery/cli install @zw008/VMware-AIops --client claude
```

---

#### Option I: Standalone CLI (no AI)

```bash
# Already installed in Step 1
source .venv/bin/activate

vmware-aiops inventory vms --target home-esxi
vmware-aiops health alarms --target home-esxi
vmware-aiops vm power-on my-vm --target home-esxi
```

---

## Chinese Cloud Models

For users in China who prefer domestic cloud APIs or have limited access to overseas services.

### DeepSeek

Cost-effective, strong coding capability.

```bash
# Set DeepSeek API key (get from https://platform.deepseek.com)
export DEEPSEEK_API_KEY="your-key"

# Run with Aider
aider --conventions codex-skill/AGENTS.md \
  --model deepseek/deepseek-coder
```

Persistent config `~/.aider.conf.yml`:
```yaml
model: deepseek/deepseek-coder
conventions: codex-skill/AGENTS.md
```

### Qwen (Alibaba Cloud)

Alibaba Cloud's coding model, free tier available.

```bash
# Set DashScope API key (get from https://dashscope.console.aliyun.com)
export DASHSCOPE_API_KEY="your-key"

aider --conventions codex-skill/AGENTS.md \
  --model qwen/qwen-coder-plus
```

Or via OpenAI-compatible endpoint:
```bash
export OPENAI_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="your-dashscope-key"

aider --conventions codex-skill/AGENTS.md \
  --model qwen-coder-plus-latest
```

### Doubao (ByteDance)

```bash
export OPENAI_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
export OPENAI_API_KEY="your-ark-key"

aider --conventions codex-skill/AGENTS.md \
  --model your-doubao-endpoint-id
```

### With Continue CLI

Configure `~/.continue/config.yaml`:

```yaml
# DeepSeek
models:
  - name: deepseek-coder
    provider: openai-compatible
    apiBase: https://api.deepseek.com/v1
    apiKey: your-deepseek-key
    model: deepseek-coder

# Qwen
models:
  - name: qwen-coder
    provider: openai-compatible
    apiBase: https://dashscope.aliyuncs.com/compatible-mode/v1
    apiKey: your-dashscope-key
    model: qwen-coder-plus-latest
```

---

## Local Models (Aider + Ollama)

For fully offline operation — no cloud API, no internet, full privacy.

**Aider + Ollama + local Qwen/DeepSeek** is ideal for air-gapped environments.

### Step 1: Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull a model

| Model | Command | Size | Note |
|-------|---------|------|------|
| **Qwen 2.5 Coder 32B** | `ollama pull qwen2.5-coder:32b` | ~20GB | Best local coding model |
| **Qwen 2.5 Coder 7B** | `ollama pull qwen2.5-coder:7b` | ~4.5GB | Low-memory option |
| **DeepSeek Coder V2** | `ollama pull deepseek-coder-v2` | ~8.9GB | Strong reasoning |
| **CodeLlama 34B** | `ollama pull codellama:34b` | ~19GB | Meta coding model |

> **Hardware**: 32B → ~20GB VRAM (or 32GB RAM for CPU). 7B → 8GB RAM.

### Step 3: Run with Aider

```bash
pip install aider-chat
ollama serve

# Aider + local Qwen (recommended)
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:32b

# Aider + local DeepSeek
aider --conventions codex-skill/AGENTS.md \
  --model ollama/deepseek-coder-v2

# Low-memory option
aider --conventions codex-skill/AGENTS.md \
  --model ollama/qwen2.5-coder:7b
```

Persistent config `~/.aider.conf.yml`:
```yaml
model: ollama/qwen2.5-coder:32b
conventions: codex-skill/AGENTS.md
```

### Local Architecture

```
User → Aider CLI → Ollama (localhost:11434) → Qwen / DeepSeek local model
  │                                                    ↓
  │                                          reads AGENTS.md instructions
  │                                                    ↓
  └──────────────────────────────→ vmware-aiops CLI ──→ ESXi / vCenter
```

> **Tip**: Local models are fully offline — perfect for air-gapped environments or strict data compliance.

---

## CLI Reference

```bash
# Inventory
vmware-aiops inventory vms                          # List VMs
vmware-aiops inventory hosts --target prod-vcenter  # List hosts
vmware-aiops inventory datastores                   # List datastores
vmware-aiops inventory clusters                     # List clusters

# Health
vmware-aiops health alarms                                # Active alarms
vmware-aiops health events --hours 24 --severity warning  # Recent events

# VM operations
vmware-aiops vm info my-vm                                     # VM details
vmware-aiops vm power-on my-vm                                 # Power on
vmware-aiops vm power-off my-vm                                # Graceful shutdown (2x confirm)
vmware-aiops vm power-off my-vm --force                        # Force power off (2x confirm)
vmware-aiops vm create my-new-vm --cpu 4 --memory 8192 --disk 100  # Create VM
vmware-aiops vm delete my-vm --confirm                         # Delete VM (2x confirm)
vmware-aiops vm reconfigure my-vm --cpu 4 --memory 8192        # Reconfigure (2x confirm)
vmware-aiops vm snapshot-create my-vm --name "before-upgrade"  # Create snapshot
vmware-aiops vm snapshot-list my-vm                            # List snapshots
vmware-aiops vm snapshot-revert my-vm --name "before-upgrade"  # Revert snapshot
vmware-aiops vm snapshot-delete my-vm --name "before-upgrade"  # Delete snapshot
vmware-aiops vm clone my-vm --new-name my-vm-clone             # Clone VM
vmware-aiops vm migrate my-vm --to-host esxi-02                # vMotion

# Scan
vmware-aiops scan now              # One-time scan

# Daemon
vmware-aiops daemon start          # Start scanner
vmware-aiops daemon status         # Check status
vmware-aiops daemon stop           # Stop daemon

# vSAN
vmware-aiops vsan health [--target prod-vcenter]                  # vSAN health
vmware-aiops vsan capacity [--target prod-vcenter]                # vSAN capacity
vmware-aiops vsan disks [--target prod-vcenter]                   # Disk groups
vmware-aiops vsan performance [--hours 1] [--target prod-vcenter] # Performance

# Aria Operations / VCF Operations
vmware-aiops ops alerts [--severity critical]                     # Intelligent alerts
vmware-aiops ops metrics <resource-name> [--hours 24]             # Time-series metrics
vmware-aiops ops recommendations [--target prod-vcenter]          # Right-sizing
vmware-aiops ops capacity <cluster-name>                          # Capacity planning

# vSphere Kubernetes Service (VKS)
vmware-aiops vks clusters [--namespace default]                   # List K8s clusters
vmware-aiops vks health <cluster-name>                            # Cluster health
vmware-aiops vks scale <machine-deployment> --replicas <n>        # Scale workers
vmware-aiops vks nodes <cluster-name>                             # Node status
```

---

## Configuration

See `config.example.yaml` for all options.

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| targets | name | — | Friendly name |
| targets | host | — | vCenter/ESXi hostname or IP |
| targets | type | vcenter | `vcenter` or `esxi` |
| targets | port | 443 | Connection port |
| targets | verify_ssl | false | SSL certificate verification |
| scanner | interval_minutes | 15 | Scan frequency |
| scanner | severity_threshold | warning | Min severity: critical/warning/info |
| scanner | lookback_hours | 1 | How far back to scan |
| scanner | log_types | [vpxd, hostd, vmkernel] | Log sources |
| notify | log_file | ~/.vmware-aiops/scan.log | JSONL log output |
| notify | webhook_url | — | Webhook endpoint (Slack, Discord, etc.) |

---

## Project Structure

```
VMware-AIops/
├── .claude-plugin/                # Claude Code marketplace manifest
│   └── marketplace.json
├── plugins/                       # Claude Code plugin
│   └── vmware-ops/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       └── skills/
│           └── vmware-aiops/
│               └── SKILL.md       # Full operations skill
├── skills/                        # Skills index (npx skills add)
│   └── vmware-aiops/
│       └── SKILL.md
├── vmware_aiops/                  # Python backend
│   ├── config.py                  # YAML + .env config
│   ├── connection.py              # Multi-target pyVmomi
│   ├── cli.py                     # Typer CLI (double confirm)
│   ├── ops/                       # Operations
│   │   ├── inventory.py           # VMs, hosts, datastores, clusters
│   │   ├── health.py              # Alarms, events, sensors
│   │   └── vm_lifecycle.py        # VM CRUD, snapshots, clone, migrate
│   ├── scanner/                   # Log scanning daemon
│   └── notify/                    # Notifications (JSONL + webhook)
├── gemini-extension/              # Gemini CLI extension
│   ├── gemini-extension.json
│   └── GEMINI.md
├── codex-skill/                   # Codex + Aider + Continue
│   ├── SKILL.md
│   └── AGENTS.md
├── trae-rules/                    # Trae IDE rules
│   └── project_rules.md
├── kimi-skill/                    # Kimi Code CLI skill
│   └── SKILL.md
├── mcp_server/                    # MCP server wrapper
│   ├── server.py                  # FastMCP server with tools
│   └── __main__.py
├── smithery.yaml                  # Smithery marketplace config
├── RELEASE_NOTES.md
├── config.example.yaml
└── pyproject.toml
```

## API Coverage

Built on **pyVmomi** (vSphere Web Services API / SOAP).

| API Object | Usage |
|------------|-------|
| `vim.VirtualMachine` | VM lifecycle, snapshots, clone, migrate |
| `vim.HostSystem` | ESXi host info, sensors, services |
| `vim.Datastore` | Storage capacity, type, accessibility |
| `vim.ClusterComputeResource` | Cluster, DRS, HA |
| `vim.Network` | Network listing |
| `vim.alarm.AlarmManager` | Active alarm monitoring |
| `vim.event.EventManager` | Event/log queries |

## Related Projects

| Project | Description | Install |
|---------|-------------|---------|
| **[VMware-Monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring — code-level enforced safety, zero destructive operations | `npx skills add zw008/VMware-Monitor` |
| **VMware-AIops** (this repo) | Full AI-powered operations — monitoring + VM lifecycle management | `npx skills add zw008/VMware-AIops` |

> **Choosing between them**: Use **VMware-Monitor** if you only need read-only monitoring with zero risk of accidental changes. Use **VMware-AIops** if you need full operations (create, delete, power, snapshot, clone, migrate).

---

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this project!

## License

MIT
