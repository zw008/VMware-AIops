"""Health checks: alarms, events, hardware status, services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

# Event types by severity
CRITICAL_EVENTS = {
    "VmFailedToPowerOnEvent",
    "HostConnectionLostEvent",
    "HostShutdownEvent",
    "VmDiskFailedEvent",
    "DasHostFailedEvent",
    "DatastoreRemovedOnHostEvent",
}

WARNING_EVENTS = {
    "VmFailoverFailed",
    "DrsVmMigratedEvent",
    "DrsSoftRuleViolationEvent",
    "VmFailedToRebootGuestEvent",
    "DVPortGroupReconfiguredEvent",
    "VmGuestShutdownEvent",
    "HostIpChangedEvent",
    "BadUsernameSessionEvent",
}

INFO_EVENTS = {
    "VmPoweredOnEvent",
    "VmPoweredOffEvent",
    "VmMigratedEvent",
    "VmReconfiguredEvent",
    "UserLoginSessionEvent",
    "UserLogoutSessionEvent",
    "VmCreatedEvent",
    "VmRemovedEvent",
    "VmClonedEvent",
}

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def get_active_alarms(si: ServiceInstance) -> list[dict]:
    """Get all active/triggered alarms across the inventory."""
    content = si.RetrieveContent()
    results = []

    def _collect_alarms(entity: vim.ManagedEntity) -> None:
        if not hasattr(entity, "triggeredAlarmState"):
            return
        for alarm_state in entity.triggeredAlarmState:
            severity = str(alarm_state.overallStatus)
            severity_map = {"red": "critical", "yellow": "warning", "green": "info"}
            results.append({
                "severity": severity_map.get(severity, severity),
                "alarm_name": alarm_state.alarm.info.name,
                "entity_name": alarm_state.entity.name,
                "entity_type": type(alarm_state.entity).__name__,
                "time": str(alarm_state.time),
                "acknowledged": alarm_state.acknowledged if hasattr(alarm_state, "acknowledged") else False,
            })

    _collect_alarms(content.rootFolder)
    # Also check datacenters, clusters, hosts
    container_types = [vim.Datacenter, vim.ClusterComputeResource, vim.HostSystem]
    for obj_type in container_types:
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [obj_type], True
        )
        for entity in container.view:
            _collect_alarms(entity)
        container.Destroy()

    # Deduplicate by alarm + entity
    seen = set()
    unique = []
    for a in results:
        key = (a["alarm_name"], a["entity_name"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return sorted(unique, key=lambda x: SEVERITY_ORDER.get(x["severity"], 9))


def get_recent_events(
    si: ServiceInstance,
    hours: int = 24,
    severity: str = "warning",
) -> list[dict]:
    """Get recent events filtered by severity."""
    content = si.RetrieveContent()
    event_mgr = content.eventManager

    now = datetime.now(tz=timezone.utc)
    begin = now - timedelta(hours=hours)

    filter_spec = vim.event.EventFilterSpec(
        time=vim.event.EventFilterSpec.ByTime(beginTime=begin, endTime=now)
    )

    events = event_mgr.QueryEvents(filter_spec)
    min_level = SEVERITY_ORDER.get(severity, 1)

    results = []
    for event in events:
        event_type = type(event).__name__
        if event_type in CRITICAL_EVENTS:
            sev = "critical"
        elif event_type in WARNING_EVENTS:
            sev = "warning"
        elif event_type in INFO_EVENTS:
            sev = "info"
        else:
            sev = "info"

        if SEVERITY_ORDER.get(sev, 2) > min_level:
            continue

        results.append({
            "severity": sev,
            "event_type": event_type,
            "message": event.fullFormattedMessage or str(event),
            "time": str(event.createdTime),
            "username": event.userName if hasattr(event, "userName") else "N/A",
        })

    return sorted(results, key=lambda x: x["time"], reverse=True)


def get_host_hardware_status(si: ServiceInstance) -> list[dict]:
    """Get hardware sensor status for all hosts."""
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    results = []
    for host in container.view:
        runtime_health = host.runtime.healthSystemRuntime
        if not runtime_health or not runtime_health.systemHealthInfo:
            continue
        for sensor in runtime_health.systemHealthInfo.numericSensorInfo:
            status = str(sensor.sensorType) if hasattr(sensor, "sensorType") else "unknown"
            results.append({
                "host": host.name,
                "sensor_name": sensor.name,
                "reading": sensor.currentReading,
                "unit": sensor.baseUnits,
                "status": status,
            })
    container.Destroy()
    return results


def get_host_services(si: ServiceInstance, host_name: str | None = None) -> list[dict]:
    """Get service status for hosts."""
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    results = []
    for host in container.view:
        if host_name and host.name != host_name:
            continue
        svc_system = host.configManager.serviceSystem
        if not svc_system:
            continue
        for svc in svc_system.serviceInfo.service:
            results.append({
                "host": host.name,
                "service": svc.key,
                "label": svc.label,
                "running": svc.running,
                "policy": svc.policy,
            })
    container.Destroy()
    return results
