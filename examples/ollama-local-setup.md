# Fully Local VMware Operations with Ollama

Run VMware infrastructure operations using a local LLM — no cloud API keys required.

## Prerequisites

- **Ollama** installed: https://ollama.com
- **vmware-aiops** installed: `uv tool install vmware-aiops`
- **VMware config** ready: `~/.vmware-aiops/config.yaml` + `~/.vmware-aiops/.env`

## Step 1: Pull a local model

```bash
# Recommended: Qwen2.5-Coder 32B (best tool-calling accuracy, needs 24GB VRAM)
ollama pull qwen2.5-coder:32b

# Alternative: 14B (needs 10GB VRAM)
ollama pull qwen2.5-coder:14b

# Lightweight: 7B (needs 6GB VRAM, lower accuracy for complex operations)
ollama pull qwen2.5-coder:7b
```

## Step 2: Choose your agent

### Option A: Aider (simplest)

```bash
# Install aider
pip install aider-chat

# Run with Ollama + vmware-aiops conventions
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b
```

Then ask in natural language:
```
> List all VMs on my lab ESXi
> Show active alarms on vcenter-prod
> What's the datastore usage?
```

### Option B: Goose (Block)

Edit `~/.config/goose/config.yaml`:

```yaml
extensions:
  vmware-aiops:
    name: VMware AIops
    cmd: vmware-aiops-mcp
    enabled: true
    type: stdio
    timeout: 300
    envs:
      VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml
```

Then:
```bash
goose session
> Check health status of all my VMware hosts
```

### Option C: Continue (VS Code)

Add to your Continue MCP config:

```yaml
mcpServers:
  - name: vmware-aiops
    command: vmware-aiops-mcp
    env:
      VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml
```

Configure Ollama as your model provider in Continue settings.

## Step 3: Read-only mode (recommended for production)

For production environments, use vmware-monitor instead:

```bash
uv tool install vmware-monitor

# Aider
aider --conventions codex-skill/AGENTS.md --model ollama/qwen2.5-coder:32b

# Or configure MCP with vmware-monitor-mcp instead of vmware-aiops-mcp
```

vmware-monitor has zero destructive operations in its codebase — safe to use with any model.

## Model comparison for VMware operations

| Model | VRAM | Tool calling | Complex ops | Recommended for |
|-------|:----:|:----------:|:-----------:|----------------|
| Qwen2.5-Coder 32B | 24GB | ~90% | Good | Full operations |
| Qwen2.5-Coder 14B | 10GB | ~80% | Fair | Monitoring + simple ops |
| Qwen2.5-Coder 7B | 6GB | ~60% | Poor | Monitoring only |
| DeepSeek-Coder-V2 16B | 12GB | ~75% | Fair | Alternative to Qwen |

## Troubleshooting

```bash
# Verify vmware-aiops config and connection
vmware-aiops inventory vms --target <your-target>

# Verify Ollama is running
ollama list

# Check MCP server works standalone
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | vmware-aiops-mcp
```
