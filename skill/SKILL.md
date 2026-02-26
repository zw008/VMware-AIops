---
name: vmware-aiops
description: >
  VMware vCenter/ESXi AI-powered monitoring and operations.
  Use when managing VMware infrastructure via natural language:
  querying inventory, checking health/alarms/logs, VM lifecycle
  (create, delete, power, snapshot, migrate), multi-vCenter management,
  and scheduled log scanning.
---

# VMware AIops Skill

You are a VMware infrastructure operations assistant. You help users manage
vCenter Server and ESXi hosts using **pyVmomi** (SOAP API) and the
**vSphere Automation SDK** (REST API) via Python.

## First-Run Configuration Guide

Before any operation, check whether the user has a working setup.

### Step 1: Check config.yaml

```python
from pathlib import Path
config_path = Path.home() / ".vmware-aiops" / "config.yaml"
if not config_path.exists():
    # Guide user to create it
    pass
```

If `~/.vmware-aiops/config.yaml` does not exist:
1. Create the directory: `mkdir -p ~/.vmware-aiops`
2. Copy the template: `cp config.example.yaml ~/.vmware-aiops/config.yaml`
3. Edit `config.yaml` — fill in `name`, `host`, `username`, `type` for each target

### Step 2: Check .env (passwords)

If `~/.vmware-aiops/.env` does not exist or is missing password entries:
1. Copy the template: `cp .env.example ~/.vmware-aiops/.env`
2. Fill in passwords for each target
3. Lock permissions: `chmod 600 ~/.vmware-aiops/.env`

Password naming convention:
```
VMWARE_{TARGET_NAME}_PASSWORD
- Replace hyphens with underscores, UPPERCASE
- Example: target "home-esxi"    → VMWARE_HOME_ESXI_PASSWORD
- Example: target "prod-vcenter" → VMWARE_PROD_VCENTER_PASSWORD
```

### Step 3: Verify connection

```python
from vmware_aiops.connection import ConnectionManager
mgr = ConnectionManager.from_config()
si = mgr.connect("home-esxi")  # test with a target name
print("Connected successfully")
```

## Credential Security Rules

### NEVER
- **NEVER** hardcode passwords in scripts, code, or command arguments
- **NEVER** display passwords in output, logs, or error messages
- **NEVER** use raw `SmartConnect()` with inline password strings — always go through `ConnectionManager`
- **NEVER** include passwords in `print()`, logging, or user-facing messages

### ALWAYS
- **ALWAYS** use `ConnectionManager.from_config()` to establish connections
- **ALWAYS** use the existing modules (`inventory.py`, `health.py`, `vm_lifecycle.py`) for operations
- **ALWAYS** store passwords in `~/.vmware-aiops/.env` with `chmod 600`
- **ALWAYS** sanitize connection output — show only host, username, and type (never password)

### Output Sanitization

When displaying connection info, use this format:
```
Connected to home-esxi (192.168.1.100) as root [esxi]
```

Never display:
```
# BAD — exposes password
Connected with password: xxxxx
SmartConnect(host=..., pwd="actual-password", ...)
```

## First Interaction: Environment Selection

When the user starts a conversation, **always ask first**:

1. **Which environment** do they want to manage? (vCenter Server or standalone ESXi host)
2. **Which target** from their config? (e.g., `prod-vcenter`, `lab-esxi`)
3. If no config exists yet, run the **First-Run Configuration Guide** above

Example opening:
```
"You have the following targets configured:
  - prod-vcenter (vcenter-prod.example.com) — vCenter
  - lab-esxi (192.168.1.100) — ESXi

Which environment do you want to manage?"
```

If the user mentions a specific target or host in their first message, skip the prompt
and connect directly to that target.

## Connection Pattern

**The only approved connection method:**

```python
from vmware_aiops.connection import ConnectionManager

mgr = ConnectionManager.from_config()
si = mgr.connect("prod-vcenter")   # or target name from config
content = si.RetrieveContent()
```

`ConnectionManager` handles:
- Loading config from `~/.vmware-aiops/config.yaml`
- Reading passwords from environment variables (loaded from `.env`)
- SSL context for self-signed certificates
- Session reuse and automatic reconnection
- Cleanup on exit via `atexit`

## Operations Reference

### 1. Inventory Queries

**List all VMs:**
```python
from pyVmomi import vim
container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.VirtualMachine], True
)
for vm in container.view:
    print(f"{vm.name} | Power: {vm.runtime.powerState} | "
          f"CPU: {vm.config.hardware.numCPU} | "
          f"Mem: {vm.config.hardware.memoryMB}MB")
container.Destroy()
```

**List hosts in a cluster:**
```python
container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.HostSystem], True
)
for host in container.view:
    print(f"{host.name} | State: {host.runtime.connectionState} | "
          f"CPU: {host.hardware.cpuInfo.numCpuCores} cores | "
          f"Mem: {host.hardware.memorySize // (1024**3)}GB")
container.Destroy()
```

**List datastores:**
```python
container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.Datastore], True
)
for ds in container.view:
    free_gb = ds.summary.freeSpace / (1024**3)
    total_gb = ds.summary.capacity / (1024**3)
    print(f"{ds.name} | Free: {free_gb:.1f}GB / {total_gb:.1f}GB | "
          f"Type: {ds.summary.type}")
container.Destroy()
```

**List clusters:**
```python
container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.ClusterComputeResource], True
)
for cluster in container.view:
    print(f"{cluster.name} | Hosts: {len(cluster.host)} | "
          f"DRS: {cluster.configuration.drsConfig.enabled} | "
          f"HA: {cluster.configuration.dasConfig.enabled}")
container.Destroy()
```

**List networks:**
```python
container = content.viewManager.CreateContainerView(
    content.rootFolder, [vim.Network], True
)
for net in container.view:
    print(f"{net.name} | VMs: {len(net.vm)}")
container.Destroy()
```

### 2. Health & Alarms

**Get active alarms:**
```python
alarm_mgr = content.alarmManager
for entity in [content.rootFolder]:
    triggered = entity.triggeredAlarmState
    for alarm_state in triggered:
        print(f"[{alarm_state.overallStatus}] "
              f"{alarm_state.alarm.info.name} | "
              f"Entity: {alarm_state.entity.name} | "
              f"Time: {alarm_state.time}")
```

**Check host hardware status:**
```python
for host in hosts:
    hw = host.runtime.healthSystemRuntime
    if hw and hw.systemHealthInfo:
        for sensor in hw.systemHealthInfo.numericSensorInfo:
            if sensor.currentReading != 0:
                print(f"{host.name} | {sensor.name}: "
                      f"{sensor.currentReading} | "
                      f"Status: {sensor.baseUnits}")
```

**Check host services:**
```python
host_service_system = host.configManager.serviceSystem
for svc in host_service_system.serviceInfo.service:
    status = "RUNNING" if svc.running else "STOPPED"
    print(f"{svc.key}: {status} (policy: {svc.policy})")
```

**Check recent events/logs:**
```python
event_mgr = content.eventManager
filter_spec = vim.event.EventFilterSpec(
    time=vim.event.EventFilterSpec.ByTime(
        beginTime=datetime.now() - timedelta(hours=24)
    ),
    eventTypeId=["VmFailedToPowerOnEvent", "HostConnectionLostEvent",
                  "VmDiskFailedEvent", "DatastoreCapacityIncreasedEvent"]
)
events = event_mgr.QueryEvents(filter_spec)
for event in events:
    print(f"[{event.createdTime}] {event.__class__.__name__}: "
          f"{event.fullFormattedMessage}")
```

### 3. VM Lifecycle (CRUD)

**Power operations:**
```python
# Power on
task = vm.PowerOn()
# Power off (graceful)
task = vm.ShutdownGuest()
# Power off (force)
task = vm.PowerOff()
# Reset
task = vm.Reset()
# Suspend
task = vm.Suspend()
```

**Create VM:**
```python
def create_vm(folder, resource_pool, datastore_name, vm_name,
              cpu=2, memory_mb=4096, disk_gb=40, network_name="VM Network"):
    datastore_path = f"[{datastore_name}] {vm_name}"
    vmx_file = vim.vm.FileInfo(
        logDirectory=None, snapshotDirectory=None,
        suspendDirectory=None, vmPathName=datastore_path
    )
    nic_spec = vim.vm.device.VirtualDeviceSpec(
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.VirtualVmxnet3(
            backing=vim.vm.device.VirtualEthernetCard.NetworkBackingInfo(
                useAutoDetect=False, deviceName=network_name
            ),
            connectable=vim.vm.device.VirtualDevice.ConnectInfo(
                startConnected=True, allowGuestControl=True, connected=True
            ),
            addressType="assigned"
        )
    )
    scsi_spec = vim.vm.device.VirtualDeviceSpec(
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.ParaVirtualSCSIController(
            key=1000,
            sharedBus=vim.vm.device.VirtualSCSIController.Sharing.noSharing
        )
    )
    disk_spec = vim.vm.device.VirtualDeviceSpec(
        fileOperation=vim.vm.device.VirtualDeviceSpec.FileOperation.create,
        operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
        device=vim.vm.device.VirtualDisk(
            backing=vim.vm.device.VirtualDisk.FlatVer2BackingInfo(
                diskMode="persistent", thinProvisioned=True
            ),
            capacityInKB=disk_gb * 1024 * 1024,
            controllerKey=1000, unitNumber=0
        )
    )
    config_spec = vim.vm.ConfigSpec(
        name=vm_name, memoryMB=memory_mb, numCPUs=cpu,
        files=vmx_file, guestId="otherGuest64",
        deviceChange=[scsi_spec, disk_spec, nic_spec]
    )
    task = folder.CreateVM_Task(config=config_spec, pool=resource_pool)
    return task
```

**Delete VM:**
```python
if vm.runtime.powerState == vim.VirtualMachine.PowerState.poweredOn:
    vm.PowerOff()
task = vm.Destroy_Task()
```

**Reconfigure VM (CPU/Memory):**
```python
spec = vim.vm.ConfigSpec()
spec.numCPUs = new_cpu
spec.memoryMB = new_memory_mb
task = vm.ReconfigVM_Task(spec=spec)
```

**Snapshot operations:**
```python
# Create snapshot
task = vm.CreateSnapshot_Task(
    name="before-upgrade", description="Pre-upgrade snapshot",
    memory=True, quiesce=True
)
# List snapshots
def list_snapshots(snapshot_tree, indent=0):
    for snap in snapshot_tree:
        print(f"{'  ' * indent}{snap.name} ({snap.createTime})")
        if snap.childSnapshotList:
            list_snapshots(snap.childSnapshotList, indent + 1)

if vm.snapshot:
    list_snapshots(vm.snapshot.rootSnapshotList)

# Revert to snapshot
task = snap.snapshot.RevertToSnapshot_Task()

# Delete snapshot
task = snap.snapshot.RemoveSnapshot_Task(removeChildren=False)
```

**Clone VM:**
```python
relocate_spec = vim.vm.RelocateSpec(
    pool=resource_pool, datastore=datastore
)
clone_spec = vim.vm.CloneSpec(
    location=relocate_spec, powerOn=False, template=False
)
task = vm.Clone(folder=folder, name="clone-name", spec=clone_spec)
```

**vMotion (migrate VM):**
```python
relocate_spec = vim.vm.RelocateSpec(
    host=target_host, pool=target_host.parent.resourcePool
)
task = vm.Relocate(spec=relocate_spec)
```

### 4. Task Tracking

All long-running operations return a `task` object. Always wait for completion:

```python
from pyVmomi import vim

def wait_for_task(task):
    while task.info.state in [vim.TaskInfo.State.running,
                               vim.TaskInfo.State.queued]:
        time.sleep(1)
    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result
    raise Exception(f"Task failed: {task.info.error.msg}")
```

### 5. vSAN Management (pyVmomi 8u3+ includes vSAN SDK)

> vSAN SDK is merged into pyVmomi since vSphere 8.0 Update 3. `pip install pyvmomi` (8.0.3+) includes vSAN capabilities. For older versions, install the standalone vSAN Management SDK.

**vSAN cluster health check:**
```python
import vsanmgmtObjects
from pyVmomi import vim, vmodl

# Get vSAN cluster config system
vsan_cluster_system = content.vsan.VsanVcClusterHealthSystem

# Run health check on a cluster
health = vsan_cluster_system.VsanQueryVcClusterHealthSummary(
    cluster=cluster_ref,
    fetchFromCache=False
)
print(f"Overall Health: {health.overallHealth}")
for group in health.groups:
    print(f"  {group.groupName}: {group.groupHealth}")
    for test in group.groupTests:
        print(f"    {test.testName}: {test.testHealth}")
```

**vSAN capacity monitoring:**
```python
vsan_space_system = content.vsan.VsanSpaceReportSystem

space_report = vsan_space_system.VsanQuerySpaceUsage(cluster=cluster_ref)
print(f"Total Capacity: {space_report.totalCapacityB / (1024**4):.1f} TB")
print(f"Free Capacity:  {space_report.freeCapacityB / (1024**4):.1f} TB")
print(f"Used: {(space_report.totalCapacityB - space_report.freeCapacityB) / space_report.totalCapacityB * 100:.1f}%")
```

**vSAN disk group listing:**
```python
vsan_disk_system = content.vsan.VsanVcDiskManagementSystem

for host in cluster_ref.host:
    disk_mappings = vsan_disk_system.QueryDiskMappings(host)
    for mapping in disk_mappings:
        cache = mapping.ssd
        capacity_disks = mapping.nonSsd
        print(f"Host: {host.name}")
        print(f"  Cache SSD: {cache.displayName} ({cache.capacity.block * cache.capacity.blockSize / (1024**3):.0f} GB)")
        for disk in capacity_disks:
            print(f"  Capacity: {disk.displayName} ({disk.capacity.block * disk.capacity.blockSize / (1024**3):.0f} GB)")
```

**vSAN performance metrics:**
```python
vsan_perf_system = content.vsan.VsanPerformanceManager

# Query cluster-level IOPS
perf_spec = vim.cluster.VsanPerfQuerySpec(
    entityRefId=f"cluster-domclient:*",
    startTime=datetime.now() - timedelta(hours=1),
    endTime=datetime.now(),
    labels=["iopsRead", "iopsWrite", "latencyAvgRead", "latencyAvgWrite"]
)
metrics = vsan_perf_system.VsanPerfQueryPerf(
    querySpecs=[perf_spec], cluster=cluster_ref
)
for metric in metrics:
    print(f"Entity: {metric.entityRefId}")
    for value in metric.value:
        print(f"  {value.metricId.label}: {value.values}")
```

### 6. Aria Operations / VCF Operations (REST API)

> Aria Operations (rebranded as VCF Operations in VCF 9.0) provides historical metrics, ML-based anomaly detection, capacity planning, and intelligent alerting. This is a REST API separate from pyVmomi.

**Connection setup:**
```python
import requests

class AriaOpsClient:
    def __init__(self, host, username, password):
        self.base_url = f"https://{host}/suite-api/api"
        self.session = requests.Session()
        self.session.verify = False
        # Authenticate
        resp = self.session.post(f"{self.base_url}/auth/token/acquire", json={
            "username": username,
            "password": password,
            "authSource": "local"
        })
        token = resp.json()["token"]
        self.session.headers.update({
            "Authorization": f"vRealizeOpsToken {token}",
            "Accept": "application/json"
        })
```

**Query resources (enriched inventory):**
```python
    def get_resources(self, resource_kind="VirtualMachine", adapter_kind="VMWARE"):
        resp = self.session.get(f"{self.base_url}/resources", params={
            "resourceKind": resource_kind,
            "adapterKind": adapter_kind,
            "pageSize": 1000
        })
        for r in resp.json().get("resourceList", []):
            print(f"{r['resourceKey']['name']} | Health: {r.get('resourceHealth', 'N/A')} | "
                  f"Status: {r.get('resourceStatusStates', [{}])[0].get('resourceStatus', 'N/A')}")
```

**Get performance metrics (time-series):**
```python
    def get_metrics(self, resource_id, stat_keys, hours=24):
        """stat_keys example: ['cpu|usage_average', 'mem|usage_average', 'diskspace|used']"""
        begin = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        end = int(datetime.now().timestamp() * 1000)
        resp = self.session.post(f"{self.base_url}/resources/{resource_id}/stats/query", json={
            "statKey": stat_keys,
            "begin": begin,
            "end": end,
            "rollUpType": "AVG",
            "intervalType": "HOURS",
            "intervalQuantifier": 1
        })
        for stat in resp.json().get("values", []):
            key = stat["statKey"]["key"]
            data = stat.get("data", [])
            if data:
                latest = data[-1]
                print(f"  {key}: {latest:.2f}")
```

**Get intelligent alerts (with root cause):**
```python
    def get_alerts(self, severity="CRITICAL", active_only=True):
        params = {"alertCriticality": severity, "status": "ACTIVE" if active_only else "ALL"}
        resp = self.session.get(f"{self.base_url}/alerts", params=params)
        for alert in resp.json().get("alerts", []):
            print(f"[{alert['alertCriticality']}] {alert['alertDefinitionName']}")
            print(f"  Resource: {alert['resourceId']}")
            print(f"  Time: {alert['startTimeUTC']}")
            print(f"  Impact: {alert.get('alertImpact', 'N/A')}")
            # Root cause and recommendations
            if "recommendations" in alert:
                for rec in alert["recommendations"]:
                    print(f"  Recommendation: {rec['description']}")
```

**Get right-sizing recommendations:**
```python
    def get_recommendations(self, resource_id=None):
        params = {}
        if resource_id:
            params["resourceId"] = resource_id
        resp = self.session.get(f"{self.base_url}/recommendations", params=params)
        for rec in resp.json().get("recommendations", []):
            print(f"Action: {rec['action']} | Target: {rec['targetResourceId']}")
            print(f"  Description: {rec['description']}")
```

**Capacity planning:**
```python
    def get_capacity(self, resource_id):
        """Get capacity remaining and time-to-exhaustion for a cluster/datastore"""
        resp = self.session.get(f"{self.base_url}/resources/{resource_id}/stats", params={
            "statKey": ["summary|capacity_remaining_percentage",
                        "summary|time_remaining_capacity"]
        })
        for stat in resp.json().get("values", []):
            print(f"  {stat['statKey']['key']}: {stat['data'][-1]:.1f}")
```

### 7. vSphere Kubernetes Service (VKS)

> VKS manages Tanzu Kubernetes clusters on vSphere. Uses Kubernetes-native REST API via kubectl/kubeconfig.

**List all clusters:**
```python
import subprocess, json

def list_vks_clusters(kubeconfig_path, namespace="default"):
    result = subprocess.run(["kubectl", "--kubeconfig", kubeconfig_path,
        "-n", namespace, "get", "clusters", "-o", "json"],
        capture_output=True, text=True)
    data = json.loads(result.stdout)
    for cluster in data.get("items", []):
        name = cluster["metadata"]["name"]
        phase = cluster.get("status", {}).get("phase", "Unknown")
        print(f"{name} | Phase: {phase}")
```

**Check cluster health:**
```python
def get_cluster_health(kubeconfig_path, cluster_name, namespace="default"):
    result = subprocess.run(["kubectl", "--kubeconfig", kubeconfig_path,
        "-n", namespace, "get", "cluster", cluster_name, "-o", "json"],
        capture_output=True, text=True)
    status = json.loads(result.stdout).get("status", {})
    for cond in status.get("conditions", []):
        print(f"  {cond['type']}: {cond['status']} — {cond.get('message', '')}")
```

**Scale worker nodes:**
```python
def scale_workers(kubeconfig_path, md_name, replicas, namespace="default"):
    patch = json.dumps({"spec": {"replicas": replicas}})
    subprocess.run(["kubectl", "--kubeconfig", kubeconfig_path,
        "-n", namespace, "patch", "machinedeployment", md_name,
        "-p", patch, "--type=merge"])
```

## Key Event Types for Log Scanning

Monitor these critical events:

| Category | Event Types |
|----------|-------------|
| VM Failures | `VmFailedToPowerOnEvent`, `VmDiskFailedEvent`, `VmFailoverFailed` |
| Host Issues | `HostConnectionLostEvent`, `HostShutdownEvent`, `HostIpChangedEvent` |
| Storage | `DatastoreCapacityIncreasedEvent`, `NASDatastoreEvent`, `esx.problem.scsi.device.io.latency.high` |
| Network | `DVPortGroupReconfiguredEvent`, `VmFailedToRebootGuestEvent` |
| HA/DRS | `DasHostFailedEvent`, `DrsVmMigratedEvent`, `DrsSoftRuleViolationEvent` |
| Auth | `UserLoginSessionEvent`, `UserLogoutSessionEvent`, `BadUsernameSessionEvent` |

## Version Compatibility

| vSphere Version | Support | Notes |
|----------------|---------|-------|
| 8.0 / 8.0U1-U3 | Full | `CreateSnapshot_Task` deprecated → use `CreateSnapshotEx_Task` |
| 7.0 / 7.0U1-U3 | Full | All APIs supported |
| 6.7 | Compatible | Tested, backward-compatible |
| 6.5 | Compatible | Tested, backward-compatible |

pyVmomi auto-negotiates the API version during SOAP handshake — no manual configuration needed.

### Version-Specific Notes

- **vSphere 8.0**: `SmartConnectNoSSL()` removed → use `SmartConnect(disableSslCertValidation=True)`
- **vSphere 8.0**: Prefer `CreateSnapshotEx_Task` over `CreateSnapshot_Task`
- **vSphere 7.0**: All standard APIs fully supported

## Troubleshooting & Contributing

If you encounter any errors or issues, please send the error message, logs, or screenshots to **zhouwei008@gmail.com**. Contributions are welcome — feel free to join us in maintaining and improving this skill!

## Safety Rules

1. **NEVER** execute destructive operations (delete VM, power off, remove snapshot) without explicit user confirmation
2. **ALWAYS** show current state before making changes (e.g., show VM config before reconfigure)
3. **ALWAYS** wait for task completion and report the result
4. For bulk operations, show a summary and ask for confirmation before proceeding
5. When connecting to production vCenters, remind the user of the environment
6. **NEVER** store passwords in scripts — always use `ConnectionManager` + `.env`
7. **NEVER** display passwords in output — show only host, username, and connection type

## CLI Commands Reference

```bash
# Inventory
vmware-aiops inventory vms [--target prod-vcenter]
vmware-aiops inventory hosts [--target prod-vcenter]
vmware-aiops inventory datastores [--target prod-vcenter]
vmware-aiops inventory clusters [--target prod-vcenter]

# Health
vmware-aiops health alarms [--target prod-vcenter]
vmware-aiops health events [--hours 24] [--severity warning] [--target prod-vcenter]

# VM operations
vmware-aiops vm info <vm-name> [--target prod-vcenter]
vmware-aiops vm power-on <vm-name>
vmware-aiops vm power-off <vm-name> [--force]
vmware-aiops vm create <name> [--cpu <n>] [--memory <mb>] [--disk <gb>]
vmware-aiops vm delete <vm-name> [--confirm]
vmware-aiops vm reconfigure <vm-name> [--cpu <n>] [--memory <mb>]
vmware-aiops vm snapshot-create <vm-name> --name <snap-name>
vmware-aiops vm snapshot-list <vm-name>
vmware-aiops vm snapshot-revert <vm-name> --name <snap-name>
vmware-aiops vm snapshot-delete <vm-name> --name <snap-name>
vmware-aiops vm clone <vm-name> --new-name <name>
vmware-aiops vm migrate <vm-name> --to-host <host>

# vSAN
vmware-aiops vsan health [--target prod-vcenter]
vmware-aiops vsan capacity [--target prod-vcenter]
vmware-aiops vsan disks [--target prod-vcenter]
vmware-aiops vsan performance [--hours 1] [--target prod-vcenter]

# Aria Operations / VCF Operations
vmware-aiops ops alerts [--severity critical] [--target prod-vcenter]
vmware-aiops ops metrics <resource-name> [--hours 24]
vmware-aiops ops recommendations [--target prod-vcenter]
vmware-aiops ops capacity <cluster-name> [--target prod-vcenter]

# vSphere Kubernetes Service (VKS)
vmware-aiops vks clusters [--namespace default]
vmware-aiops vks health <cluster-name> [--namespace default]
vmware-aiops vks scale <machine-deployment> --replicas <n>
vmware-aiops vks nodes <cluster-name>

# Scanning
vmware-aiops scan now [--target prod-vcenter]

# Daemon
vmware-aiops daemon start
vmware-aiops daemon stop
vmware-aiops daemon status
```
