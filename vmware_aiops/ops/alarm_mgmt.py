"""vCenter alarm management: list, acknowledge, reset.

Acknowledge marks an alarm as seen without clearing it.
Reset clears triggered alarms back to normal via
AlarmManager.ClearTriggeredAlarms (the vSphere API has no per-alarm
status setter).
Both write operations are audit-logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyVmomi import vim
from vmware_policy import sanitize

from vmware_aiops.ops.health import get_active_alarms

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

    from vmware_aiops.notify.audit import AuditLogger


# ---------------------------------------------------------------------------
# list_alarms — thin wrapper around health.get_active_alarms
# ---------------------------------------------------------------------------


def list_alarms(si: ServiceInstance) -> list[dict]:
    """List all active/triggered alarms across the vCenter inventory.

    Returns:
        List of alarm dicts with severity, alarm_name, entity_name,
        entity_type, time, and acknowledged flag.
    """
    return get_active_alarms(si)


# ---------------------------------------------------------------------------
# Internal: find a specific triggered alarm state
# ---------------------------------------------------------------------------


def _find_triggered_alarm(
    si: ServiceInstance,
    entity_name: str,
    alarm_name: str,
) -> tuple[Any, Any]:
    """Locate an entity and its triggered alarm state by name.

    Searches VMs, hosts, clusters, and datacenters.

    Returns:
        (entity, alarm_state) tuple.

    Raises:
        ValueError: If no matching alarm is found.
    """
    content = si.RetrieveContent()
    search_types = [
        vim.VirtualMachine,
        vim.HostSystem,
        vim.ClusterComputeResource,
        vim.Datacenter,
        vim.Datastore,
    ]
    for obj_type in search_types:
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [obj_type], True
        )
        try:
            for entity in container.view:
                if entity.name != entity_name:
                    continue
                if not hasattr(entity, "triggeredAlarmState"):
                    continue
                for alarm_state in entity.triggeredAlarmState:
                    if alarm_state.alarm.info.name == alarm_name:
                        return entity, alarm_state
        finally:
            container.Destroy()

    raise ValueError(
        f"Triggered alarm '{alarm_name}' on entity '{entity_name}' not found. "
        "Use list_vcenter_alarms to see current active alarms."
    )


# ---------------------------------------------------------------------------
# acknowledge_alarm
# ---------------------------------------------------------------------------


def acknowledge_alarm(
    si: ServiceInstance,
    entity_name: str,
    alarm_name: str,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Acknowledge a triggered vCenter alarm.

    Marks the alarm as acknowledged without clearing it. The alarm
    remains visible but is flagged as seen by an operator.

    Args:
        si: pyVmomi ServiceInstance.
        entity_name: Name of the entity with the alarm (VM/host/cluster name).
        alarm_name: Exact alarm definition name.
        audit_logger: Optional audit logger.
        target_name: Target name for audit log.

    Returns:
        Dict with entity_name, alarm_name, action, acknowledged.
    """
    entity, alarm_state = _find_triggered_alarm(si, entity_name, alarm_name)
    content = si.RetrieveContent()
    content.alarmManager.AcknowledgeAlarm(
        alarm=alarm_state.alarm,
        entity=entity,
    )

    result = {
        "entity_name": sanitize(entity_name),
        "alarm_name": sanitize(alarm_name),
        "action": "acknowledged",
        "acknowledged": True,
    }

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="acknowledge_alarm",
            resource=f"alarm/{entity_name}/{alarm_name}",
            parameters={"entity_name": entity_name, "alarm_name": alarm_name},
            result="ok",
        )

    return result


# ---------------------------------------------------------------------------
# reset_alarm
# ---------------------------------------------------------------------------


def reset_alarm(
    si: ServiceInstance,
    entity_name: str,
    alarm_name: str,
    audit_logger: AuditLogger | None = None,
    target_name: str = "default",
) -> dict:
    """Clear triggered vCenter alarms back to normal state.

    Uses AlarmManager.ClearTriggeredAlarms with a vim.alarm.AlarmFilterSpec.
    The vSphere API has no per-alarm clear: the filter can only scope by
    entity type (host/VM/all) and alarm status, so this clears ALL triggered
    alarms matching the named alarm's entity type and current status —
    including the one requested. The named alarm is looked up first, so a
    typo'd entity/alarm name fails fast instead of clearing anything.

    Args:
        si: pyVmomi ServiceInstance.
        entity_name: Name of the entity with the alarm.
        alarm_name: Exact alarm definition name.
        audit_logger: Optional audit logger.
        target_name: Target name for audit log.

    Returns:
        Dict with entity_name, alarm_name, action, status, scope.
    """
    entity, alarm_state = _find_triggered_alarm(si, entity_name, alarm_name)
    content = si.RetrieveContent()

    entity_types = vim.alarm.AlarmFilterSpec.AlarmTypeByEntity
    if isinstance(entity, vim.HostSystem):
        type_entity = entity_types.entityTypeHost
    elif isinstance(entity, vim.VirtualMachine):
        type_entity = entity_types.entityTypeVm
    else:
        type_entity = entity_types.entityTypeAll

    filter_spec = vim.alarm.AlarmFilterSpec(
        status=[alarm_state.overallStatus],
        typeEntity=type_entity,
        typeTrigger=vim.alarm.AlarmFilterSpec.AlarmTypeByTrigger.triggerTypeAll,
    )
    content.alarmManager.ClearTriggeredAlarms(filter=filter_spec)

    result = {
        "entity_name": sanitize(entity_name),
        "alarm_name": sanitize(alarm_name),
        "action": "reset",
        "status": "cleared",
        "scope": (
            f"all triggered alarms with status={alarm_state.overallStatus} "
            f"on {type_entity} entities (vSphere has no per-alarm clear)"
        ),
    }

    if audit_logger:
        audit_logger.log(
            target=target_name,
            operation="reset_alarm",
            resource=f"alarm/{entity_name}/{alarm_name}",
            parameters={"entity_name": entity_name, "alarm_name": alarm_name},
            result="ok",
        )

    return result
