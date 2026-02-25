"""Alarm scanner: checks for active/triggered alarms across the inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vmware_aiops.ops.health import get_active_alarms

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


def scan_alarms(si: ServiceInstance) -> list[dict]:
    """Scan for active alarms and return as issue list.

    Returns issues compatible with the notification pipeline.
    """
    alarms = get_active_alarms(si)
    issues: list[dict] = []

    for alarm in alarms:
        # Skip acknowledged alarms
        if alarm.get("acknowledged"):
            continue

        issues.append({
            "severity": alarm["severity"],
            "source": "alarm",
            "message": (
                f"[{alarm['entity_type']}:{alarm['entity_name']}] "
                f"{alarm['alarm_name']}"
            ),
            "time": alarm["time"],
            "entity": alarm["entity_name"],
        })

    return issues
