"""Log scanner: queries vCenter/ESXi events and classifies issues."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.config import ScannerConfig
from vmware_aiops.ops.health import CRITICAL_EVENTS, WARNING_EVENTS

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


def scan_logs(
    si: ServiceInstance,
    scanner_config: ScannerConfig,
) -> list[dict]:
    """Scan recent events/logs and return issues above severity threshold.

    Returns a list of issue dicts with keys: severity, source, message, time.
    """
    content = si.RetrieveContent()
    event_mgr = content.eventManager

    now = datetime.now(tz=timezone.utc)
    begin = now - timedelta(hours=scanner_config.lookback_hours)

    filter_spec = vim.event.EventFilterSpec(
        time=vim.event.EventFilterSpec.ByTime(beginTime=begin, endTime=now)
    )

    events = event_mgr.QueryEvents(filter_spec)
    threshold = scanner_config.severity_threshold
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    min_rank = severity_rank.get(threshold, 1)

    issues: list[dict] = []
    for event in events:
        event_type = type(event).__name__

        if event_type in CRITICAL_EVENTS:
            severity = "critical"
        elif event_type in WARNING_EVENTS:
            severity = "warning"
        else:
            continue  # Skip info-level for scanner

        if severity_rank.get(severity, 2) > min_rank:
            continue

        issues.append({
            "severity": severity,
            "source": "event",
            "event_type": event_type,
            "message": event.fullFormattedMessage or str(event),
            "time": str(event.createdTime),
            "entity": _safe_entity_name(event),
        })

    return issues


def scan_host_logs(
    si: ServiceInstance,
    host_name: str | None = None,
    log_keys: tuple[str, ...] = ("hostd", "vmkernel", "vpxa"),
    lines: int = 500,
) -> list[dict]:
    """Scan ESXi host syslog entries for error patterns.

    This connects to host diagnostic systems to read recent log lines.
    """
    content = si.RetrieveContent()
    container = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )

    error_patterns = [
        "error", "fail", "critical", "panic", "lost access",
        "cannot", "timeout", "refused", "corrupt",
    ]

    issues: list[dict] = []
    for host in container.view:
        if host_name and host.name != host_name:
            continue

        diag_mgr = host.configManager.diagnosticSystem
        if not diag_mgr:
            continue

        for log_key in log_keys:
            try:
                log_data = diag_mgr.BrowseDiagnosticLog(
                    key=log_key, start=max(1, lines)
                )
            except Exception:
                continue

            if not log_data or not log_data.lineText:
                continue

            for line in log_data.lineText:
                line_lower = line.lower()
                if any(pattern in line_lower for pattern in error_patterns):
                    severity = (
                        "critical"
                        if any(p in line_lower for p in ("critical", "panic", "corrupt"))
                        else "warning"
                    )
                    issues.append({
                        "severity": severity,
                        "source": f"host_log:{log_key}",
                        "message": f"[{host.name}] {line.strip()[:200]}",
                        "time": str(datetime.now(tz=timezone.utc)),
                        "entity": host.name,
                    })

    container.Destroy()
    return issues


def _safe_entity_name(event) -> str:
    """Safely extract entity name from event."""
    try:
        if hasattr(event, "vm") and event.vm:
            return event.vm.name
        if hasattr(event, "host") and event.host:
            return event.host.name
        if hasattr(event, "ds") and event.ds:
            return event.ds.name
    except Exception:
        pass
    return "N/A"
