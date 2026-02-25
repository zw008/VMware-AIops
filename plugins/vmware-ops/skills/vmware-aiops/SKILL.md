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

## Connection Setup

Before any operation, ensure a connection is established.

### Configuration File

The tool uses `~/.vmware-aiops/config.yaml`:

```yaml
targets:
  - name: prod-vcenter
    host: vcenter-prod.example.com
    port: 443
    username: administrator@vsphere.local
    # password via env: VMWARE_PROD_VCENTER_PASSWORD
    type: vcenter

  - name: lab-esxi
    host: 192.168.1.100
    port: 443
    username: root
    # password via env: VMWARE_LAB_ESXI_PASSWORD
    type: esxi

scanner:
  enabled: true
  interval_minutes: 15
  log_types: [vpxd, hostd, vmkernel]
  severity_threshold: warning

notify:
  log_file: ~/.vmware-aiops/scan.log
  webhook_url: ""  # optional
```

### Connection Pattern (pyVmomi)

```python
from pyVmomi import vim
from pyVmomi.VmomiSupport import VmomiJSONEncoder
from vmware_aiops.connection import ConnectionManager

mgr = ConnectionManager.from_config()
# Connect to a specific target
si = mgr.connect("prod-vcenter")
content = si.RetrieveContent()
```

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

## Safety Rules

1. **NEVER** execute destructive operations (delete VM, power off, remove snapshot) without explicit user confirmation
2. **ALWAYS** show current state before making changes (e.g., show VM config before reconfigure)
3. **ALWAYS** wait for task completion and report the result
4. For bulk operations, show a summary and ask for confirmation before proceeding
5. When connecting to production vCenters, remind the user of the environment
6. **NEVER** store passwords in scripts — always use config + environment variables

## CLI Commands Reference

```bash
# Inventory
vmware-aiops inventory vms [--target prod-vcenter]
vmware-aiops inventory hosts [--target prod-vcenter]
vmware-aiops inventory datastores [--target prod-vcenter]
vmware-aiops inventory clusters [--target prod-vcenter]

# Health
vmware-aiops health alarms [--target prod-vcenter]
vmware-aiops health hardware [--target prod-vcenter]
vmware-aiops health services [--host esxi-01]

# VM operations
vmware-aiops vm info <vm-name> [--target prod-vcenter]
vmware-aiops vm power-on <vm-name>
vmware-aiops vm power-off <vm-name> [--force]
vmware-aiops vm create --name <name> --cpu <n> --memory <mb> --disk <gb>
vmware-aiops vm delete <vm-name> [--confirm]
vmware-aiops vm snapshot create <vm-name> --name <snap-name>
vmware-aiops vm snapshot list <vm-name>
vmware-aiops vm snapshot revert <vm-name> --name <snap-name>
vmware-aiops vm reconfigure <vm-name> --cpu <n> --memory <mb>
vmware-aiops vm clone <vm-name> --new-name <name>
vmware-aiops vm migrate <vm-name> --to-host <host>

# Logs & Scanning
vmware-aiops scan now [--target prod-vcenter]
vmware-aiops scan logs --hours 24 [--severity warning]
vmware-aiops scan events --hours 24

# Daemon
vmware-aiops daemon start
vmware-aiops daemon stop
vmware-aiops daemon status
```
