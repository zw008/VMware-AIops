"""Log scanner: queries vCenter/ESXi events and classifies issues.

Security: All vSphere-sourced content (event messages, host log lines) is
sanitized before output to prevent prompt injection attacks.  Sanitization
includes truncation, control-character removal, and explicit boundary markers
so that downstream consumers (including LLM agents) can distinguish trusted
output from untrusted vSphere data.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pyVmomi import vim

from vmware_aiops.config import ScannerConfig
from vmware_aiops.ops.health import CRITICAL_EVENTS, WARNING_EVENTS

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-aiops.log-scanner")

# Regex to strip ALL control characters (C0, C1, DEL) except newline/tab
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


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
        safe_msg = _sanitize(raw_msg, max_len=500)

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
                _log.debug("Failed to browse %s log on %s", log_key, host.name, exc_info=True)
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
                    safe_line = _sanitize(line.strip(), max_len=200)
                    issues.append({
                        "severity": severity,
                        "source": f"host_log:{log_key}",
                        "message": (
                            f"[VSPHERE_HOST_LOG]{host.name}: "
                            f"{safe_line}[/VSPHERE_HOST_LOG]"
                        ),
                        "time": str(datetime.now(tz=timezone.utc)),
                        "entity": host.name,
                    })

    container.Destroy()
    return issues


def _sanitize(text: str, *, max_len: int) -> str:
    """Truncate and strip control characters from untrusted vSphere text.

    Removes all C0/C1 control characters (except \\n and \\t) to prevent
    prompt injection when the output is consumed by LLM agents.
    """
    truncated = text[:max_len]
    return _CONTROL_CHAR_RE.sub("", truncated)


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
