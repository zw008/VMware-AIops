# Using vmware-aiops with mcp-agent

[mcp-agent](https://github.com/lastmile-ai/mcp-agent) is an MCP-native agent framework by LastMile AI. This guide shows how to configure `vmware-aiops` as an MCP server for mcp-agent workflows.

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

## Adding to mcp-agent

Add the following to your `mcp_agent.config.yaml`:

```yaml
mcp:
  servers:
    vmware-aiops:
      command: python
      args:
        - -m
        - mcp_server
      cwd: /path/to/VMware-AIops
      env:
        VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml
```

Replace `/path/to/VMware-AIops` with your actual clone path.

A ready-to-use template is also available at `examples/mcp-configs/mcp-agent.yaml`.

### Full example config

```yaml
# mcp_agent.config.yaml
execution_engine: asyncio

mcp:
  servers:
    vmware-aiops:
      command: python
      args: [-m, mcp_server]
      cwd: /path/to/VMware-AIops
      env:
        VMWARE_AIOPS_CONFIG: ~/.vmware-aiops/config.yaml

anthropic:
  model: claude-sonnet-4-6
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

All tools accept an optional `target` parameter to switch between environments.

## Usage Examples

**Example 1: Automated health check in an agent workflow**
```python
# agent_script.py
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator

app = MCPApp(name="vmware-health-check")

async with app.run() as vmware_app:
    agent = Agent(
        name="vmware-ops",
        instruction="You manage VMware infrastructure. Check health and report issues.",
        server_names=["vmware-aiops"],
    )
    async with agent:
        result = await agent.send("Get all active alarms and summarize by severity")
        print(result)
```

**Example 2: Chained operations**
```
Agent: [calls get_alarms] → Found: datastore01 at 92% capacity
Agent: [calls browse_datastore] → 3 unused ISO files totaling 45GB
Agent: Report: datastore01 critical. 45GB recoverable from unused ISOs.
       Recommended action: Remove stale ISOs or expand datastore.
```

**Example 3: Batch deployment pipeline**
```python
# Deploy 5 VMs from spec and set 24h TTL for auto-cleanup
result = await agent.send(
    "Deploy 5 VMs from template ubuntu-22-base, "
    "name them test-01 through test-05, "
    "set TTL of 24 hours on each"
)
```
