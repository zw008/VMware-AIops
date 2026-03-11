# Using vmware-aiops with Goose

[Goose](https://github.com/block/goose) is an open-source AI agent by Block that runs locally on your machine. This guide shows how to add `vmware-aiops` as an MCP extension so Goose can manage your VMware infrastructure using natural language.

## Prerequisites

1. **Install vmware-aiops**
   ```bash
   uv tool install vmware-aiops
   ```

2. **Configure credentials**
   ```bash
   mkdir -p ~/.vmware-aiops
   cat > ~/.vmware-aiops/config.yaml << 'EOF'
   targets:
     my-vcenter:
       host: vcenter.example.com
       username: administrator@vsphere.local
       password_env: VMWARE_PASSWORD
       verify_ssl: false
   EOF

   echo "VMWARE_PASSWORD=your_password" > ~/.vmware-aiops/.env
   chmod 600 ~/.vmware-aiops/.env
   ```

3. **Verify setup**
   ```bash
   vmware-aiops doctor
   ```

## Adding to Goose

### Option A: goose configure (Interactive)

```bash
goose configure
# Select: Add Extension → MCP Server
# Name: vmware-aiops
# Command: python -m mcp_server
# Working directory: /path/to/VMware-AIops
# Env: VMWARE_AIOPS_CONFIG=~/.vmware-aiops/config.yaml
```

### Option B: config.yaml (Manual)

Add to `~/.config/goose/config.yaml`:

```yaml
extensions:
  vmware-aiops:
    type: stdio
    cmd: python
    args:
      - -m
      - mcp_server
    cwd: /path/to/VMware-AIops
    env:
      VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml
    enabled: true
    description: VMware vCenter/ESXi AI-powered operations
```

Replace `/path/to/VMware-AIops` with your actual clone path (e.g. `~/myskills/VMware-AIops`).

### Option C: JSON config

Use the template at `examples/mcp-configs/goose.json`:

```json
{
  "name": "vmware-aiops",
  "description": "VMware vCenter/ESXi AI-powered monitoring and operations",
  "command": "python",
  "args": ["-m", "mcp_server"],
  "cwd": "/path/to/VMware-AIops",
  "env": {
    "VMWARE_AIOPS_CONFIG": "~/.vmware-aiops/config.yaml"
  }
}
```

## Available MCP Tools (31 tools)

| Category | Tools |
|----------|-------|
| Inventory | `list_virtual_machines`, `list_esxi_hosts`, `list_all_datastores`, `list_all_clusters` |
| Health | `get_alarms`, `get_events`, `vm_info` |
| VM Lifecycle | `vm_power_on`, `vm_power_off`, `vm_set_ttl`, `vm_cancel_ttl`, `vm_list_ttl`, `vm_clean_slate` |
| Deployment | `deploy_vm_from_ova`, `deploy_vm_from_template`, `deploy_linked_clone`, `attach_iso_to_vm`, `convert_vm_to_template`, `batch_clone_vms`, `batch_linked_clone_vms`, `batch_deploy_from_spec` |
| Guest Operations | `vm_guest_exec`, `vm_guest_upload`, `vm_guest_download` |
| Plan → Apply | `vm_create_plan`, `vm_apply_plan`, `vm_rollback_plan`, `vm_list_plans` |
| Datastore | `browse_datastore`, `scan_datastore_images`, `list_cached_images` |

All tools accept an optional `target` parameter to switch between vCenter/ESXi environments.

## Usage Examples

**Example 1: Check infrastructure health**
```
You: Show me all active alarms in my vCenter

Goose: [calls get_alarms]
Found 3 active alarms on prod-vcenter:
- vm-web01: CPU usage critical (92%)
- datastore01: Low disk space (85% used)
- host02: Memory balloon active
```

**Example 2: VM lifecycle management**
```
You: Clone vm-template to create 3 new web servers, name them web04/web05/web06

Goose: [calls vm_create_plan, then vm_apply_plan]
Plan created: clone vm-template × 3
Step 1/3: Deploying web04... ✓
Step 2/3: Deploying web05... ✓
Step 3/3: Deploying web06... ✓
```

**Example 3: Guest operations**
```
You: Run "df -h" on vm-linux01 and show disk usage

Goose: [calls vm_guest_exec]
Filesystem      Size  Used Avail Use%
/dev/sda1        50G   32G   18G  64%
/dev/sdb1       200G  180G   20G  90% ← nearing capacity
```

## Local Model Support (Ollama)

`vmware-aiops` works with local models via Goose + Ollama. For smaller models (< 32B parameters), use CLI mode instead of MCP to reduce token overhead:

```yaml
# ~/.config/goose/config.yaml
provider: ollama
model: qwen2.5:32b

extensions:
  vmware-aiops:
    type: stdio
    cmd: python
    args: [-m, mcp_server]
    cwd: /path/to/VMware-AIops
    env:
      VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml
```

See [examples/ollama-local-setup.md](../../examples/ollama-local-setup.md) for full local model setup.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Extension not found | Check `cwd` path is correct and `python -m mcp_server` works from that directory |
| Auth failure | Run `vmware-aiops doctor` to verify vCenter connectivity |
| Tool call timeout | Large inventories may take 10–30s; Goose default timeout may need increasing |
| `VMWARE_AIOPS_CONFIG` not found | Use absolute path, not `~` expansion in config |
