"""Log scanner: queries vCenter/ESXi events and classifies issues.

Security: All vSphere-sourced content (event messages, host log lines) is
sanitized before output to prevent prompt injection attacks.  Sanitization
includes truncation, control-character removal, and explicit boundary markers
so that downstream consumers (including LLM agents) can distinguish trusted
output from untrusted vSphere data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim
from vmware_policy import sanitize

from vmware_aiops.config import ScannerConfig
from vmware_aiops.ops.health import CRITICAL_EVENTS, WARNING_EVENTS
from vmware_aiops.ops.inventory import _collect

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-aiops.log-scanner")


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

        # Sanitize event message: truncate, strip ALL control characters,
        # and wrap in boundary markers to prevent prompt injection from
        # attacker-controlled vSphere event content.
        raw_msg = event.fullFormattedMessage or str(event)
        safe_msg = sanitize(raw_msg, 500)

        issues.append({
            "severity": severity,
            "source": "event",
            "event_type": event_type,
            "message": f"[VSPHERE_EVENT]{safe_msg}[/VSPHERE_EVENT]",
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
    error_patterns = [
        "error", "fail", "critical", "panic", "lost access",
        "cannot", "timeout", "refused", "corrupt",
    ]

    # Enumerate hosts + name + diagnosticSystem in one batched call, then narrow
    # to host_name before issuing the (inherent) BrowseDiagnosticLog RPCs.
    issues: list[dict] = []
    for _obj, props in _collect(
        si, [vim.HostSystem], ["name", "configManager.diagnosticSystem"]
    ):
        host_name_cur = props.get("name", "")
        if host_name and host_name_cur != host_name:
            continue

        diag_mgr = props.get("configManager.diagnosticSystem")
        if not diag_mgr:
            continue

        for log_key in log_keys:
            try:
                # Probe to discover total line count, then read last N lines
                probe = diag_mgr.BrowseDiagnosticLog(key=log_key, start=999999999)
                total_lines = getattr(probe, "lineEnd", 0) or 0
                start_line = max(1, total_lines - lines + 1) if total_lines > 0 else 1
                log_data = diag_mgr.BrowseDiagnosticLog(
                    key=log_key, start=start_line
                )
            except Exception:
                _log.debug(
                    "Failed to browse %s log on %s", log_key, host_name_cur,
                    exc_info=True,
                )
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
                    # Sanitize host log lines: truncate, strip ALL control
                    # characters, and wrap in boundary markers to prevent
                    # prompt injection from attacker-controlled content.
                    safe_line = sanitize(line.strip(), 200)
                    issues.append({
                        "severity": severity,
                        "source": f"host_log:{log_key}",
                        "message": (
                            f"[VSPHERE_HOST_LOG]{host_name_cur}: "
                            f"{safe_line}[/VSPHERE_HOST_LOG]"
                        ),
                        "time": str(datetime.now(tz=timezone.utc)),
                        "entity": host_name_cur,
                    })

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
        _log.debug("Failed to extract entity name from event", exc_info=True)
    return "N/A"
