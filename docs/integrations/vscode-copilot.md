# Using vmware-aiops with VS Code Copilot

VS Code's GitHub Copilot supports MCP servers via `.vscode/mcp.json`. This guide shows how to add `vmware-aiops` so Copilot can manage your VMware infrastructure from within VS Code.

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

## Adding to VS Code Copilot

### Option A: Workspace config (`.vscode/mcp.json`)

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "vmware-aiops": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/VMware-AIops",
      "env": {
        "VMWARE_AIOPS_CONFIG": "${env:HOME}/.vmware-aiops/config.yaml"
      }
    }
  }
}
```

### Option B: User-level config (`settings.json`)

Add to your VS Code `settings.json` (`Cmd+Shift+P` → "Open User Settings JSON"):

```json
{
  "github.copilot.chat.mcp.enabled": true,
  "mcp": {
    "servers": {
      "vmware-aiops": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "mcp_server"],
        "cwd": "/path/to/VMware-AIops",
        "env": {
          "VMWARE_AIOPS_CONFIG": "/Users/your-name/.vmware-aiops/config.yaml"
        }
      }
    }
  }
}
```

A ready-to-use template is available at `examples/mcp-configs/vscode-copilot.json`.

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

All tools accept an optional `target` parameter to switch between environments.

## Usage Examples

**Example 1: Check alarms while reviewing code**
```
You: @vmware-aiops Show active alarms in prod-vcenter

Copilot: [calls get_alarms with target=prod-vcenter]
3 active alarms:
- CRITICAL: vm-api-gateway — disk I/O latency > 50ms
- WARNING: esxi-03 — CPU utilization 88%
- WARNING: datastore-nvme — 78% capacity used
```

**Example 2: Deploy a test environment**
```
You: @vmware-aiops Deploy vm-test from template ubuntu-22-base,
     4 vCPU, 8GB RAM, set 8h TTL

Copilot: [calls vm_create_plan → vm_apply_plan → vm_set_ttl]
✓ vm-test deployed to esxi-02 / ssd-ds01
✓ TTL: auto-delete at 20:00 UTC today
IP: 10.0.2.87 (available in ~30s after tools install)
```

**Example 3: Run command on VM**
```
You: @vmware-aiops Run "systemctl status my-service" on vm-backend01

Copilot: [calls vm_guest_exec]
● my-service.service
   Active: failed (Result: exit-code) since ...
   → Service crashed. Check /var/log/my-service/error.log
```
