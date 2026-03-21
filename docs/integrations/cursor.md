# Using vmware-aiops with Cursor

[Cursor](https://www.cursor.com) is an AI-powered code editor with native MCP support. This guide shows how to add `vmware-aiops` as an MCP server so Cursor's AI can manage your VMware infrastructure.

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

## Adding to Cursor

### Option A: Auto-install (recommended)

```bash
vmware-aiops mcp-config install --agent cursor
```

This writes the MCP server config directly into `~/.cursor/mcp.json`.

### Option B: Manual — Cursor Settings UI

1. Open Cursor → **Settings** → **MCP**
2. Click **Add MCP Server**
3. Fill in:
   - **Name**: `vmware-aiops`
   - **Type**: `stdio`
   - **Command**: `python -m mcp_server`
   - **Working Directory**: `/path/to/VMware-AIops`
   - **Env**: `VMWARE_AIOPS_CONFIG=~/.vmware-aiops/config.yaml`

### Option C: Manual — mcp.json

Add to `~/.cursor/mcp.json` (create if it doesn't exist):

```json
{
  "mcpServers": {
    "vmware-aiops": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/VMware-AIops",
      "env": {
        "VMWARE_AIOPS_CONFIG": "~/.vmware-aiops/config.yaml"
      }
    }
  }
}
```

Replace `/path/to/VMware-AIops` with your actual clone path (e.g. `~/myskills/VMware-AIops`).

Or use the template generator:

```bash
vmware-aiops mcp-config generate --agent cursor
```

## Available MCP Tools (31 tools)

| Category | Tools |
|----------|-------|
| Inventory | `list_virtual_machines`, `list_esxi_hosts`, `list_all_datastores`, `list_all_clusters` |
| Health | `get_alarms`, `get_events`, `vm_info` |
| VM Lifecycle | `vm_power_on`, `vm_power_off`, `vm_set_ttl`, `vm_cancel_ttl`, `vm_list_ttl`, `vm_clean_slate` |
| Deployment | `deploy_vm_from_ova`, `deploy_vm_from_template`, `deploy_linked_clone`, `batch_clone_vms` |
| Guest Operations | `vm_guest_exec`, `vm_guest_exec_output`, `vm_guest_upload`, `vm_guest_download` |
| Plan → Apply | `vm_create_plan`, `vm_apply_plan`, `vm_rollback_plan`, `vm_list_plans` |
| Datastore | `browse_datastore`, `scan_datastore_images` |

## Usage Examples

**Example 1: Query infrastructure from Cursor chat**
```
You: How many VMs are powered on in my vCenter?

Cursor: [calls list_virtual_machines with power_state=poweredOn]
Found 42 powered-on VMs across 3 clusters.
```

**Example 2: Run a command inside a VM**
```
You: Check disk usage on vm-linux01

Cursor: [calls vm_guest_exec_output]
Filesystem      Size  Used Avail Use%
/dev/sda1        50G   32G   18G  64%
/dev/sdb1       200G  180G   20G  90% ← nearing capacity
```

**Example 3: Deploy a VM from template**
```
You: Clone dev-template to create a new VM named test-env-01

Cursor: [calls vm_create_plan, then vm_apply_plan]
Plan: clone dev-template → test-env-01
Executing... ✓ VM deployed successfully.
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| MCP server not listed | Reload Cursor window after editing mcp.json |
| Auth failure | Run `vmware-aiops doctor` to verify vCenter connectivity |
| `cwd` path error | Use absolute path, not `~` shorthand in mcp.json |
| Tools not appearing | Check Cursor MCP panel for server status and error logs |
