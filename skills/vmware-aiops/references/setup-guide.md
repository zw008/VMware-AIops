# Setup Guide

## Installation

All install methods fetch from the same source: [github.com/zw008/VMware-AIops](https://github.com/zw008/VMware-AIops) (MIT licensed). We recommend reviewing the source code before installing.

```bash
# Via PyPI (recommended for version pinning)
uv tool install vmware-aiops==1.2.3

# Via Skills.sh (fetches from GitHub)
npx skills add zw008/VMware-AIops

# Via ClawHub (fetches from ClawHub registry snapshot of GitHub)
clawhub install vmware-aiops
```

### Claude Code

```
/plugin marketplace add zw008/VMware-AIops
/plugin install vmware-ops
/vmware-ops:vmware-aiops
```

## Configuration

```bash
# 1. Install from PyPI (source: github.com/zw008/VMware-AIops)
uv tool install vmware-aiops

# 2. Verify installation source
vmware-aiops --version  # confirms installed version

# 3. Configure
mkdir -p ~/.vmware-aiops
vmware-aiops init  # generates config.yaml and .env templates
chmod 600 ~/.vmware-aiops/.env
# Edit ~/.vmware-aiops/config.yaml and .env with your target details
```

### Declare `environment:` on each target

```yaml
targets:
  - name: prod-vcenter
    host: vcenter-prod.example.com
    environment: production   # production | staging | lab | <your own label>
```

Policy scopes its rules by environment, not by the target's name — an
unlabelled target matches none of them. Today an undeclared write still runs
and logs a warning. The next major release refuses it with:

> `'vm_delete' changes state, but its target does not declare which environment it is. Add 'environment: <name>' (e.g. production, staging, lab) to that target's entry in the skill's config.yaml, then retry.`

Declaring it now makes that upgrade a no-op. Read-only operations are never
affected.

## What Gets Installed

The `vmware-aiops` package installs a Python CLI binary and its dependencies (pyVmomi, Click, Rich, APScheduler, python-dotenv). No background services, daemons, or system-level changes are made during installation. The scheduled scanner (`daemon start`) only runs when explicitly started by the user.

## Development Install

```bash
git clone https://github.com/zw008/VMware-AIops.git
cd VMware-AIops
uv venv && source .venv/bin/activate
uv pip install -e .
```

### Password obfuscation at rest

On first load, any plaintext `*_PASSWORD` value in `.env` is automatically
rewritten to a grep-safe `b64:<encoded>` form and decoded transparently at
runtime, so a casual `grep` of the file no longer reveals the password. Values
are read and written through python-dotenv's own parser, so the stored secret
never drifts from what you configured (quotes, inline comments, and trailing
whitespace are handled correctly).

> **This is obfuscation, not encryption.** Anyone who can read the file can
> still decode it. For real secrecy at rest, do not store the password in `.env`
> at all — inject it from a secret manager (HashiCorp Vault, CyberArk, AWS
> Secrets Manager, or a Kubernetes Secret) into the `*_PASSWORD` environment
> variable at process start. The code reads the env var either way.

## Security

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "vSphere" are trademarks of Broadcom.

- **Source Code**: Fully open source at [github.com/zw008/VMware-AIops](https://github.com/zw008/VMware-AIops) (MIT). The `uv` installer fetches the `vmware-aiops` package from PyPI, which is built from this GitHub repository. We recommend reviewing the source code and commit history before deploying in production.
- **TLS Verification**: Enabled by default. The `disableSslCertValidation` option exists solely for ESXi hosts using self-signed certificates in isolated lab/home environments. In production, always use CA-signed certificates with full TLS verification.
- **Credentials & Config**: This skill requires the following secrets, all stored in `~/.vmware-aiops/.env` (`chmod 600`, loaded via `python-dotenv`):
  - `VMWARE_<TARGET>_PASSWORD` — per-target password where `<TARGET>` is the uppercased target name from `config.yaml` (hyphens become underscores). Example: target named `vcenter-prod` uses `VMWARE_VCENTER_PROD_PASSWORD`.
  - (Optional) Webhook URLs for Slack/Discord notifications

  The config file `~/.vmware-aiops/config.yaml` stores only target hostnames, ports, and usernames — it does **not** contain passwords or tokens. The env var `VMWARE_AIOPS_CONFIG` points to this YAML file.
- **Webhook Data Scope**: Webhook notifications are **disabled by default**. When enabled, they send infrastructure health summaries (alarm counts, event types, host status) to **user-configured URLs only** (Slack, Discord, or any HTTP endpoint you control). No data is sent to third-party services. Webhook payloads contain no credentials, IPs, or personally identifiable information — only aggregated alert metadata.
- **Prompt Injection Protection**: All vSphere-sourced content (event messages, host logs) is truncated, stripped of control characters, and wrapped in boundary markers (`[VSPHERE_EVENT]`/`[VSPHERE_HOST_LOG]`) before output to prevent prompt injection when consumed by LLM agents.
- **Least Privilege**: Use a dedicated vCenter service account with minimal permissions. For monitoring-only use cases, prefer the read-only [VMware-Monitor](https://github.com/zw008/VMware-Monitor) skill which has zero destructive code paths.

### Read-only mode

Read-only mode removes all 36 write-effecting tools from the MCP registry before the server accepts a request, so `list_tools()` never offers them. The model cannot call what it cannot see — no prompt discipline required. **Off by default.**

Three ways to enable it, highest precedence first:

| Precedence | Setting | Scope |
|:-:|---|---|
| 1 | `VMWARE_AIOPS_READ_ONLY=true` | This skill only |
| 2 | `VMWARE_READ_ONLY=true` | **Every installed VMware skill** — one setting puts the whole estate in audit posture |
| 3 | `read_only: true` in `~/.vmware-aiops/config.yaml` | This skill only |
| 4 | *(unset)* | Off — write tools exposed |

The env vars come first so a deployment can be locked down from the MCP client's `env` block without editing any config file.

**Fail-closed.** If read-only mode is requested but cannot be *proven* — the tool registry cannot be enumerated, or a removal does not take effect — the server refuses to start rather than serving write tools it promised to withhold. One case does *not* abort: an unrecognised value (`VMWARE_READ_ONLY=ture`) resolves to **on** with a warning, so a typo locks the deployment down instead of leaving it open.

**Verifying it took**:

```bash
vmware-aiops doctor        # reports ON/off, and which of the four sources decided it
```

The MCP server also logs a warning at start-up naming every tool it withheld. The 13 read tools are unaffected in all cases.

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

## MCP Server — Local Agent Compatibility

The MCP server works with any MCP-compatible agent via stdio transport. Config templates in `examples/mcp-configs/`:

| Agent | Local Models | Config Template |
|-------|:----------:|-----------------|
| Goose (Block) | ✅ Ollama, LM Studio | `goose.json` |
| LocalCowork (Liquid AI) | ✅ Fully offline | `localcowork.json` |
| mcp-agent (LastMile AI) | ✅ Ollama, vLLM | `mcp-agent.yaml` |
| VS Code Copilot | — | `vscode-copilot.json` |
| Cursor | — | `cursor.json` |
| Continue | ✅ Ollama | `continue.yaml` |
| Claude Code | — | `claude-code.json` |

```bash
# Example: Aider + Ollama (fully local, no cloud API)
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

## MCP Mode (Optional)

For Claude Code / Cursor users who prefer structured tool calls, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "vmware-aiops",
      "args": ["mcp"],
      "env": {
        "VMWARE_AIOPS_CONFIG": "~/.vmware-aiops/config.yaml"
      }
    }
  }
}
```

> v1.5.15+ recommends the single-command form `vmware-aiops mcp`. Pre-1.5.15 used
> `uvx --from vmware-aiops vmware-aiops-mcp`, which still works but re-resolves from
> PyPI on each launch and breaks behind corporate TLS proxies. The legacy
> `vmware-aiops-mcp` entry point is also kept for backward compatibility.

MCP exposes 49 tools across 9 categories. All accept optional `target` parameter.
