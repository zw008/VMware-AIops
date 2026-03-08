# MCP Configuration Templates

Copy the relevant config snippet into your AI agent's MCP configuration file.

## Prerequisites

```bash
# Install vmware-aiops
uv tool install vmware-aiops
# or: pip install vmware-aiops

# Configure credentials
mkdir -p ~/.vmware-aiops
cp config.example.yaml ~/.vmware-aiops/config.yaml
cp .env.example ~/.vmware-aiops/.env
chmod 600 ~/.vmware-aiops/.env
# Edit config.yaml and .env with your vCenter/ESXi details
```

## Agent Configuration Files

| Agent | Config File | Template |
|-------|------------|----------|
| Claude Code | `~/.claude/settings.json` | [claude-code.json](claude-code.json) |
| Goose | `goose configure` or UI | [goose.json](goose.json) |
| LocalCowork | MCP config panel | [localcowork.json](localcowork.json) |
| mcp-agent | `mcp_agent.config.yaml` | [mcp-agent.yaml](mcp-agent.yaml) |
| VS Code Copilot | `.vscode/mcp.json` | [vscode-copilot.json](vscode-copilot.json) |
| Cursor | Cursor MCP settings | [cursor.json](cursor.json) |
| Continue | `~/.continue/config.yaml` | [continue.yaml](continue.yaml) |

## Using with Local Models (Ollama)

vmware-aiops works with any MCP-compatible agent. For fully local operation (no cloud API):

```bash
# Example: Aider + Ollama + vmware-aiops CLI
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b

# Example: Continue + Ollama + MCP Server
# Configure Continue with Ollama model + vmware-aiops MCP server
```
