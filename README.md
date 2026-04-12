<!-- mcp-name: io.github.zw008/vmware-aiops -->
# VMware AIops

> **Author**: Wei Zhou, VMware by Broadcom — wei-wz.zhou@broadcom.com
> This is a community-driven project by a VMware engineer, not an official VMware product.
> For official VMware developer tools see [developer.broadcom.com](https://developer.broadcom.com).

English | [中文](README-CN.md)

AI-powered VMware vCenter/ESXi VM lifecycle and deployment tool — 31 tools across 6 categories.

> **Companion skills** handle everything else:
>
> | Skill | Scope | Install |
> |-------|-------|---------|
> | **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only: inventory, health, alarms, events, metrics | `uv tool install vmware-monitor` |
> | **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN management | `uv tool install vmware-storage` |
> | **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | `uv tool install vmware-vks` |
>
> **Need read-only monitoring only?** Use [VMware-Monitor](https://github.com/zw008/VMware-Monitor) — zero destructive code in the codebase.

[![ClawHub](https://img.shields.io/badge/ClawHub-vmware--aiops-orange)](https://clawhub.ai/skills/vmware-aiops)
[![Skills.sh](https://img.shields.io/badge/Skills.sh-Install-blue)](https://skills.sh/zw008/VMware-AIops)
[![Claude Code Marketplace](https://img.shields.io/badge/Claude_Code-Marketplace-blueviolet)](https://github.com/zw008/VMware-AIops)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### Quick Install (Recommended)

Works with Claude Code, Cursor, Codex, Gemini CLI, Trae, and 30+ AI agents:

```bash
# Via Skills.sh
npx skills add zw008/VMware-AIops

# Via ClawHub
clawhub install vmware-aiops
```

### PyPI Install (No GitHub Access Required)

```bash
# Install via uv (recommended)
uv tool install vmware-aiops

# Or via pip
pip install vmware-aiops

# China mainland mirror (faster)
pip install vmware-aiops -i https://pypi.tuna.tsinghua.edu.cn/simple
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

### What This Skill Does

| Category | Tools | Count |
|----------|-------|:-----:|
| **VM Lifecycle** | power on/off, TTL auto-delete, clean slate | 6 |
| **Deployment** | OVA, template, linked clone, batch clone/deploy | 8 |
| **Guest Ops** | exec commands, upload/download files, provision | 5 |
| **Plan/Apply** | multi-step planning with rollback | 4 |
| **Cluster** | create, delete, HA/DRS config, add/remove hosts | 6 |
| **Datastore** | browse files, scan for images | 2 |

### CLI vs MCP: Which Mode to Use

| Scenario | Recommended | Why |
|----------|:-----------:|-----|
| **Local/small models** (Ollama, Qwen <32B) | **CLI** | ~2K tokens context vs ~10K for MCP; small models struggle with many tool schemas |
| **Token-sensitive workflows** | **CLI** | SKILL.md + Bash tool = minimal overhead |
| **Cloud models** (Claude, GPT-4o) | Either | Both work; MCP gives structured JSON I/O |
| **Automated pipelines / Agent chaining** | **MCP** | Type-safe parameters, structured output, no shell parsing |
| **Monitoring / storage / K8s** | Companion skills | See [vmware-monitor](https://github.com/zw008/VMware-Monitor), [vmware-storage](https://github.com/zw008/VMware-Storage), [vmware-vks](https://github.com/zw008/VMware-VKS) |

> **Rule of thumb**: Use CLI for cost efficiency and small models. Use MCP for structured automation with large models.

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

---

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

---

## VM Lifecycle

| Operation | Command | Confirmation | vCenter | ESXi |
|-----------|---------|:------------:|:-------:|:----:|
| Power On | `vm power-on <name>` | — | ✅ | ✅ |
| Graceful Shutdown | `vm power-off <name>` | Double | ✅ | ✅ |
| Force Power Off | `vm power-off <name> --force` | Double | ✅ | ✅ |
| Reset | `vm reset <name>` | — | ✅ | ✅ |
| Suspend | `vm suspend <name>` | — | ✅ | ✅ |
| Create VM | `vm create <name> --cpu --memory --disk` | — | ✅ | ✅ |
| Delete VM | `vm delete <name>` | Double | ✅ | ✅ |
| Reconfigure | `vm reconfigure <name> --cpu --memory` | Double | ✅ | ✅ |
| Create Snapshot | `vm snapshot-create <name> --name <snap>` | — | ✅ | ✅ |
| List Snapshots | `vm snapshot-list <name>` | — | ✅ | ✅ |
| Revert Snapshot | `vm snapshot-revert <name> --name <snap>` | — | ✅ | ✅ |
| Delete Snapshot | `vm snapshot-delete <name> --name <snap>` | — | ✅ | ✅ |
| Clone VM | `vm clone <name> --new-name <new>` | — | ✅ | ✅ |
| vMotion | `vm migrate <name> --to-host <host>` | — | ✅ | ❌ |
| **Set TTL** | `vm set-ttl <name> --minutes <n>` | — | ✅ | ✅ |
| **Cancel TTL** | `vm cancel-ttl <name>` | — | ✅ | ✅ |
| **List TTLs** | `vm list-ttl` | — | ✅ | ✅ |
| **Clean Slate** | `vm clean-slate <name> [--snapshot baseline]` | Double | ✅ | ✅ |
| **Guest Exec** | `vm guest-exec <name> --cmd /bin/bash --args "..."` | — | ✅ | ✅ |
| **Guest Exec (with output)** | `vm guest-exec-output <name> --cmd "df -h"` | — | ✅ | ✅ |
| **Guest Upload** | `vm guest-upload <name> --local f.sh --guest /tmp/f.sh` | — | ✅ | ✅ |
| **Guest Download** | `vm guest-download <name> --guest /var/log/syslog --local ./syslog` | — | ✅ | ✅ |

> Guest Operations require VMware Tools running inside the guest OS. `guest-exec-output` auto-detects Linux/Windows shell and captures stdout/stderr.

### Plan → Apply (Multi-step Operations)

For complex operations involving 2+ steps or 2+ VMs, use the plan/apply workflow instead of executing individually:

| Step | What Happens |
|------|-------------|
| 1. **Create Plan** | AI calls `vm_create_plan` — validates actions, checks targets in vSphere, generates plan with rollback info |
| 2. **Review** | AI shows plan to user: steps, affected VMs, irreversible warnings |
| 3. **Apply** | `vm_apply_plan` executes sequentially; stops on failure |
| 4. **Rollback** (if failed) | Asks user whether to rollback, then `vm_rollback_plan` reverses executed steps (irreversible steps skipped) |

Plans stored in `~/.vmware-aiops/plans/`, auto-deleted on success, auto-cleaned after 24h.

## VM Deployment & Provisioning

| Operation | Command | Speed | vCenter | ESXi |
|-----------|---------|:-----:|:-------:|:----:|
| Deploy from OVA | `deploy ova <path> --name <vm>` | Minutes | ✅ | ✅ |
| Deploy from Template | `deploy template <tmpl> --name <vm>` | Minutes | ✅ | ✅ |
| Linked Clone | `deploy linked-clone --source <vm> --snapshot <snap> --name <new>` | Seconds | ✅ | ✅ |
| Attach ISO | `deploy iso <vm> --iso "[ds] path/to.iso"` | Instant | ✅ | ✅ |
| Convert to Template | `deploy mark-template <vm>` | Instant | ✅ | ✅ |
| Batch Clone | `deploy batch-clone --source <vm> --count <n>` | Minutes | ✅ | ✅ |
| Batch Deploy (YAML) | `deploy batch spec.yaml` | Auto | ✅ | ✅ |

## Cluster Management

| Operation | Command | Confirmation | vCenter | ESXi |
|-----------|---------|:------------:|:-------:|:----:|
| Cluster Info | `cluster info <name>` | — | ✅ | ❌ |
| Create Cluster | `cluster create <name> [--ha] [--drs]` | — | ✅ | ❌ |
| Delete Cluster | `cluster delete <name>` | Double | ✅ | ❌ |
| Add Host | `cluster add-host <cluster> --host <host>` | Double | ✅ | ❌ |
| Remove Host | `cluster remove-host <cluster> --host <host>` | Double | ✅ | ❌ |
| Configure HA/DRS | `cluster configure <name> [--ha/--no-ha] [--drs/--no-drs]` | Double | ✅ | ❌ |

## Datastore Browser

| Feature | vCenter | ESXi | Details |
|---------|:-------:|:----:|---------|
| Browse Files | ✅ | ✅ | List files/folders in any datastore path |
| Scan Images | ✅ | ✅ | Discover ISO, OVA, OVF, VMDK across all datastores |

## Scheduled Scanning & Notifications

| Feature | Details |
|---------|---------|
| Daemon | APScheduler-based, configurable interval (default 15 min) |
| Multi-target Scan | Sequentially scan all configured vCenter/ESXi targets |
| Scan Content | Alarms + Events + Host logs (hostd, vmkernel, vpxd) |
| Log Analysis | Regex pattern matching: error, fail, critical, panic, timeout, corrupt |
| Structured Log | JSONL output to `~/.vmware-aiops/scan.log` |
| Webhook | Slack, Discord, or any HTTP endpoint |
| Daemon Management | `daemon start/stop/status`, PID file, graceful shutdown |

## Safety Features

| Feature | Details |
|---------|---------|
| **Dry-Run Mode** | `--dry-run` on any destructive command prints exact API calls without executing |
| **Plan → Confirm → Execute → Log** | Structured workflow: show current state, confirm changes, execute, audit log |
| **Double Confirmation** | All destructive ops (power-off, delete, reconfigure, snapshot-revert/delete, clone, migrate) require 2 sequential confirmations — no bypass flags |
| **Rejection Logging** | Declined confirmations are recorded in the audit trail |
| **Audit Trail** | All operations logged to `~/.vmware-aiops/audit.log` (JSONL) with before/after state |
| **Input Validation** | VM name, CPU (1-128), memory (128-1048576 MB), disk (1-65536 GB) validated |
| **Password Protection** | `.env` file loading with permission check; never in shell history |
| **SSL Self-signed Support** | `disableSslCertValidation` — only for ESXi with self-signed certs in isolated labs; production should use CA-signed certificates |
| **Prompt Injection Protection** | vSphere event messages and host logs are truncated, stripped of control characters, and wrapped in boundary markers before output |
| **Webhook Data Scope** | Sends notifications to user-configured URLs only — no third-party services by default |
| **Task Waiting** | All async operations wait for completion and report result |
| **State Validation** | Pre-operation checks (VM exists, power state correct) |

### vCenter vs ESXi Comparison

| Capability | vCenter | ESXi Standalone |
|------------|:-------:|:----:|
| vMotion migration | ✅ | ❌ |
| Cross-host clone | ✅ | ❌ |
| Cluster management | ✅ | ❌ |
| All VM lifecycle ops | ✅ | ✅ |
| OVA/Template/Linked Clone deploy | ✅ | ✅ |
| Datastore browsing & image scan | ✅ | ✅ |
| Snapshots | ✅ | ✅ |
| Guest operations | ✅ | ✅ |

> Inventory, alarms, events, sensors, host services, and scanning are now in [vmware-monitor](https://github.com/zw008/VMware-Monitor).

---

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

### MCP Server Integrations

The vmware-aiops MCP server works with **any MCP-compatible agent or tool**. Ready-to-use configuration templates are in [`examples/mcp-configs/`](examples/mcp-configs/).

| Agent / Tool | Local Model Support | Config Template | Integration Guide |
|-------------|:-------------------:|-----------------|-------------------|
| **[Goose](https://github.com/block/goose)** | ✅ Ollama, LM Studio | [`goose.json`](examples/mcp-configs/goose.json) | [Guide](docs/integrations/goose.md) |
| **[LocalCowork](https://github.com/Liquid4All/localcowork)** | ✅ Fully offline | [`localcowork.json`](examples/mcp-configs/localcowork.json) | [Guide](docs/integrations/localcowork.md) |
| **[mcp-agent](https://github.com/lastmile-ai/mcp-agent)** | ✅ Ollama, vLLM | [`mcp-agent.yaml`](examples/mcp-configs/mcp-agent.yaml) | [Guide](docs/integrations/mcp-agent.md) |
| **VS Code Copilot** | — | [`vscode-copilot.json`](examples/mcp-configs/vscode-copilot.json) | [Guide](docs/integrations/vscode-copilot.md) |
| **[Cursor](https://www.cursor.com)** | — | [`cursor.json`](examples/mcp-configs/cursor.json) | [Guide](docs/integrations/cursor.md) |
| **Continue** | ✅ Ollama | [`continue.yaml`](examples/mcp-configs/continue.yaml) | [Guide](docs/integrations/continue.md) |
| **Claude Code** | — | [`claude-code.json`](examples/mcp-configs/claude-code.json) | — |

**Fully local operation** (no cloud API required):

```bash
# Aider + Ollama + vmware-aiops (via AGENTS.md)
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b

# Any MCP agent + local model + vmware-aiops MCP server
# See examples/mcp-configs/ for your agent's config format
```

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
- **ALWAYS** configure connections via `config.yaml` — credentials are loaded from `.env` automatically
- **Config File Contents**: `config.yaml` stores target hostnames, ports, and a reference to the `.env` file. It does **not** contain passwords or tokens. All secrets are stored exclusively in `.env`
- **TLS**: Enabled by default. Disable only for ESXi hosts with self-signed certificates in isolated lab environments
- **Webhook**: Disabled by default. When enabled, sends monitoring summaries to your own configured URL only — payloads contain no credentials, IPs, or PII, only aggregated alert metadata. No data sent to third-party services
- **Least Privilege**: Use a dedicated vCenter service account with minimal permissions. For monitoring-only use cases, prefer the read-only [VMware-Monitor](https://github.com/zw008/VMware-Monitor)
- **Prompt Injection Protection**: All vSphere-sourced content is truncated, stripped of control characters, and wrapped in boundary markers before output
- **Code Review**: We recommend reviewing the [source code](https://github.com/zw008/VMware-AIops) and commit history before deploying in production
- **Production Safety**: For production environments, use the read-only [VMware-Monitor](https://github.com/zw008/VMware-Monitor) instead. AI agents can misinterpret context and execute unintended destructive operations — real-world incidents have shown that AI-driven infrastructure tools without proper isolation can delete production databases and entire environments. VMware-Monitor eliminates this risk at the code level: no destructive functions exist in its codebase

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
# Run via uvx (recommended — works with uv tool install)
uvx --from vmware-aiops vmware-aiops-mcp

# With a custom config path
VMWARE_AIOPS_CONFIG=/path/to/config.yaml uvx --from vmware-aiops vmware-aiops-mcp
```

**Claude Desktop config** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "uvx",
      "args": ["--from", "vmware-aiops", "vmware-aiops-mcp"],
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

vmware-aiops vm power-on my-vm --target home-esxi
vmware-aiops deploy ova ./ubuntu.ova --name my-vm --target home-esxi
vmware-aiops datastore browse datastore1 --target home-esxi
```

---

## Update / Upgrade

Already installed? Re-run the install command for your channel to get the latest version:

| Install Channel | Update Command |
|----------------|----------------|
| ClawHub | `clawhub install vmware-aiops` |
| Skills.sh | `npx skills add zw008/VMware-AIops` |
| Claude Code Plugin | `/plugin marketplace add zw008/VMware-AIops` |
| Git clone | `cd VMware-AIops && git pull origin main && uv pip install -e .` |
| uv | `uv tool install vmware-aiops --force` |

Check your current version: `vmware-aiops --version`

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

# Linux — download from https://ollama.com/download and install manually
# See https://github.com/ollama/ollama for platform-specific instructions
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
# Diagnostics
vmware-aiops doctor                   # Check environment, config, connectivity
vmware-aiops doctor --skip-auth       # Skip vSphere auth check (faster)

# MCP Config Generator
vmware-aiops mcp-config generate --agent goose        # Generate config for Goose
vmware-aiops mcp-config generate --agent claude-code  # Generate config for Claude Code
vmware-aiops mcp-config list                          # List all supported agents

# VM operations
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
vmware-aiops vm set-ttl my-vm --minutes 60                     # Auto-delete in 60 min
vmware-aiops vm cancel-ttl my-vm                               # Cancel TTL
vmware-aiops vm list-ttl                                       # Show all TTLs
vmware-aiops vm clean-slate my-vm --snapshot baseline          # Revert to baseline (2x confirm)

# Guest Operations (requires VMware Tools in guest)
vmware-aiops vm guest-exec my-vm --cmd /bin/bash --args "-c 'whoami'" --user root
vmware-aiops vm guest-upload my-vm --local ./script.sh --guest /tmp/script.sh --user root
vmware-aiops vm guest-download my-vm --guest /var/log/syslog --local ./syslog.txt --user root

# Plan → Apply (multi-step operations)
vmware-aiops plan list                                        # List pending/failed plans

# Deploy
vmware-aiops deploy ova ./ubuntu.ova --name my-vm --datastore ds1      # Deploy from OVA
vmware-aiops deploy template golden-ubuntu --name new-vm               # Deploy from template
vmware-aiops deploy linked-clone --source base-vm --snapshot clean --name test-vm  # Linked clone (seconds)
vmware-aiops deploy iso my-vm --iso "[datastore1] iso/ubuntu-22.04.iso"  # Attach ISO
vmware-aiops deploy mark-template golden-vm                            # Convert VM to template
vmware-aiops deploy batch-clone --source base-vm --count 5 --prefix lab  # Batch clone
vmware-aiops deploy batch deploy.yaml                                  # Batch deploy from YAML spec

# Cluster
vmware-aiops cluster info my-cluster                                   # Cluster details (HA/DRS status)
vmware-aiops cluster create my-cluster --ha --drs                      # Create cluster with HA+DRS
vmware-aiops cluster delete my-cluster                                 # Delete cluster (2x confirm)
vmware-aiops cluster add-host my-cluster --host esxi-03                # Add host to cluster (2x confirm)
vmware-aiops cluster remove-host my-cluster --host esxi-03             # Remove host (2x confirm)
vmware-aiops cluster configure my-cluster --ha --drs                   # Configure HA/DRS (2x confirm)

# Datastore (browse and scan only — iSCSI/vSAN moved to vmware-storage)
vmware-aiops datastore browse datastore1 --path "iso/"                 # Browse datastore
vmware-aiops datastore scan-images --target home-esxi                  # Scan all datastores for images

# Scan
vmware-aiops scan now              # One-time scan

# Daemon
vmware-aiops daemon start          # Start scanner
vmware-aiops daemon status         # Check status
vmware-aiops daemon stop           # Stop daemon

# Companion skills for other operations:
#   vmware-monitor: inventory, alarms, events, sensors
#   vmware-storage: datastores, iSCSI, vSAN
#   vmware-vks:     Tanzu/TKC cluster lifecycle
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
│       ├── SKILL.md               # Slimmed-down skill (progressive disclosure)
│       └── references/            # Detailed docs loaded on-demand
│           ├── capabilities.md    # Full capabilities tables
│           ├── cli-reference.md   # Complete CLI reference
│           └── setup-guide.md     # Install, security, AI platforms
├── vmware_aiops/                  # Python backend
│   ├── config.py                  # YAML + .env config
│   ├── connection.py              # Multi-target pyVmomi
│   ├── cli.py                     # Typer CLI (double confirm)
│   ├── ops/                       # Operations
│   │   ├── inventory.py           # VMs, hosts, datastores, clusters
│   │   ├── health.py              # Alarms, events, sensors
│   │   ├── vm_lifecycle.py        # VM CRUD, snapshots, clone, migrate
│   │   ├── vm_deploy.py           # OVA, template, linked clone, batch deploy
│   │   └── datastore_browser.py   # Datastore browsing, image discovery
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
| `vim.host.DatastoreBrowser` | File browsing, image discovery (ISO/OVA/VMDK) |
| `vim.OvfManager` | OVA import and deployment |
| `vim.ClusterComputeResource` | Cluster, DRS, HA |
| `vim.Network` | Network listing |
| `vim.alarm.AlarmManager` | Active alarm monitoring |
| `vim.event.EventManager` | Event/log queries |

## Related Projects

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring, alarms, events | 8 | `uv tool install vmware-monitor` |
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** | VM lifecycle, deployment, guest ops, cluster, datastore browse | 31 | `uv tool install vmware-aiops` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-vks](https://github.com/zw008/VMware-VKS)** | Tanzu Namespaces, TKC cluster lifecycle | 20 | `uv tool install vmware-vks` |

---

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this project!

## License

MIT
