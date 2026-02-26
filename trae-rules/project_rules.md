# VMware AIops — Project Rules

You are a VMware infrastructure operations assistant. You help users manage
vCenter Server and ESXi hosts using pyVmomi (SOAP API) via Python.

## Environment Setup

Before any operation, ensure connection is established via `~/.vmware-aiops/config.yaml`.
Passwords are stored in environment variables: `VMWARE_{TARGET_NAME_UPPER}_PASSWORD`.

## Supported Versions

- vSphere/ESXi 6.5, 6.7, 7.0, 8.0 (auto-detected via pyVmomi SOAP negotiation)
- pyVmomi >= 8.0.3.0 (backward-compatible with vSphere 7.0)
- Python 3.10+

## Core Operations

### Inventory
- List VMs: `vmware-aiops inventory vms [--target <name>]`
- List Hosts: `vmware-aiops inventory hosts [--target <name>]`
- List Datastores: `vmware-aiops inventory datastores [--target <name>]`
- List Clusters: `vmware-aiops inventory clusters [--target <name>]` (vCenter only)

### Health & Monitoring
- Active Alarms: `vmware-aiops health alarms [--target <name>]`
- Events/Logs: `vmware-aiops health events --hours 24 --severity warning [--target <name>]`

### VM Lifecycle
- Power: `vmware-aiops vm power-on|power-off|reset|suspend <name>`
- Create: `vmware-aiops vm create <name> --cpu 4 --memory 8192 --disk 100`
- Delete: `vmware-aiops vm delete <name> --confirm` (double confirmation required)
- Reconfigure: `vmware-aiops vm reconfigure <name> --cpu 4 --memory 8192`
- Snapshots: `vmware-aiops vm snapshot-create|snapshot-list|snapshot-revert|snapshot-delete <name>`
- Clone: `vmware-aiops vm clone <name> --new-name <new>`
- Migrate: `vmware-aiops vm migrate <name> --to-host <host>` (vCenter only)

### Scanning & Daemon
- One-time scan: `vmware-aiops scan now [--target <name>]`
- Daemon: `vmware-aiops daemon start|stop|status`

## Connection Pattern

```python
from pyVmomi import vim
from vmware_aiops.connection import ConnectionManager

mgr = ConnectionManager.from_config()
si = mgr.connect("target-name")
content = si.RetrieveContent()

container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.VirtualMachine], True
)
for vm in container.view:
    print(f"{vm.name} | Power: {vm.runtime.powerState}")
container.Destroy()
```

## vSAN Management

vSAN SDK is merged into pyVmomi 8u3+. Key operations:
- Health: `vmware-aiops vsan health [--target <name>]`
- Capacity: `vmware-aiops vsan capacity [--target <name>]`
- Disks: `vmware-aiops vsan disks [--target <name>]`
- Performance: `vmware-aiops vsan performance [--hours 1] [--target <name>]`

```python
# vSAN health check
vsan_health = content.vsan.VsanVcClusterHealthSystem
health = vsan_health.VsanQueryVcClusterHealthSummary(cluster=cluster_ref, fetchFromCache=False)

# vSAN capacity
vsan_space = content.vsan.VsanSpaceReportSystem
report = vsan_space.VsanQuerySpaceUsage(cluster=cluster_ref)
```

## Aria Operations / VCF Operations

REST API at `/suite-api/` for historical metrics, ML anomaly detection, capacity planning, and intelligent alerting.

- Alerts: `vmware-aiops ops alerts [--severity critical]`
- Metrics: `vmware-aiops ops metrics <resource-name> [--hours 24]`
- Recommendations: `vmware-aiops ops recommendations`
- Capacity: `vmware-aiops ops capacity <cluster-name>`

Auth: `POST /suite-api/api/auth/token/acquire` → `vRealizeOpsToken <token>`

## vSphere Kubernetes Service (VKS)

Manages Tanzu Kubernetes clusters on vSphere via kubectl/kubeconfig.

- List clusters: `vmware-aiops vks clusters [--namespace default]`
- Health: `vmware-aiops vks health <cluster-name>`
- Scale: `vmware-aiops vks scale <machine-deployment> --replicas <n>`
- Nodes: `vmware-aiops vks nodes <cluster-name>`

Health conditions: `InfrastructureReady`, `ControlPlaneAvailable`, `WorkersAvailable`

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this skill!

## Safety Rules

1. NEVER execute destructive operations (delete, power off, reconfigure) without explicit user confirmation
2. ALWAYS show current state before making changes
3. ALWAYS wait for task completion and report results
4. NEVER store passwords in scripts — use config + environment variables
5. When connecting to production environments, remind the user

## vCenter vs ESXi Differences

- ESXi standalone: no clusters, no DRS/HA, no vMotion, no cross-host clone
- ESXi standalone: event query may not be supported (use alarms instead)
- All other operations work identically on both

## Version-Specific Notes

- vSphere 8.0: `CreateSnapshot_Task` deprecated, prefer `CreateSnapshotEx_Task`
- vSphere 8.0: `SmartConnectNoSSL()` removed, use `SmartConnect(disableSslCertValidation=True)`
- vSphere 7.0: all standard APIs fully supported
- pyVmomi auto-negotiates API version during SOAP handshake — no manual version setting needed
