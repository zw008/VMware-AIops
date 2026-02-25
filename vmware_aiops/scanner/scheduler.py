"""APScheduler-based daemon for periodic scanning."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from vmware_aiops.config import AppConfig, load_config
from vmware_aiops.connection import ConnectionManager
from vmware_aiops.notify.logger import ScanLogger
from vmware_aiops.notify.webhook import WebhookNotifier
from vmware_aiops.scanner.alarm_scanner import scan_alarms
from vmware_aiops.scanner.log_scanner import scan_host_logs, scan_logs

logger = logging.getLogger("vmware-aiops.scheduler")

PID_FILE = Path.home() / ".vmware-aiops" / "daemon.pid"


def _run_scan(config: AppConfig, conn_mgr: ConnectionManager) -> None:
    """Execute a single scan cycle across all targets."""
    scan_logger = ScanLogger(config.notify.log_file)
    webhook = WebhookNotifier(
        url=config.notify.webhook_url,
        timeout=config.notify.webhook_timeout,
    )

    all_issues: list[dict] = []

    for target_name in conn_mgr.list_targets():
        try:
            si = conn_mgr.connect(target_name)
        except Exception as e:
            issue = {
                "severity": "critical",
                "source": "connection",
                "message": f"Failed to connect to {target_name}: {e}",
                "time": "",
                "entity": target_name,
            }
            all_issues.append(issue)
            continue

        # Scan alarms
        try:
            all_issues.extend(scan_alarms(si))
        except Exception as e:
            logger.error("Alarm scan failed for %s: %s", target_name, e)

        # Scan events/logs
        try:
            all_issues.extend(scan_logs(si, config.scanner))
        except Exception as e:
            logger.error("Log scan failed for %s: %s", target_name, e)

        # Scan host-level logs
        try:
            all_issues.extend(scan_host_logs(si))
        except Exception as e:
            logger.error("Host log scan failed for %s: %s", target_name, e)

    # Log all issues
    for issue in all_issues:
        scan_logger.log_issue(issue)

    # Send webhook if there are critical/warning issues
    important = [i for i in all_issues if i["severity"] in ("critical", "warning")]
    if important and config.notify.webhook_url:
        webhook.send(important)

    if all_issues:
        logger.info("Scan complete: %d issue(s) found", len(all_issues))
    else:
        logger.info("Scan complete: all clear")


def start_scheduler(config_path: Path | None = None) -> None:
    """Start the blocking scheduler daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = load_config(config_path)
    conn_mgr = ConnectionManager(config)

    if not config.scanner.enabled:
        logger.warning("Scanner is disabled in config. Exiting.")
        return

    # Write PID file
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(sys.modules["os"].getpid()))

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_scan,
        trigger=IntervalTrigger(minutes=config.scanner.interval_minutes),
        args=[config, conn_mgr],
        id="vmware_scan",
        name="VMware AIops Scanner",
        max_instances=1,
        next_run_time=None,  # Don't run immediately; let first interval pass
    )

    # Run once immediately on start
    logger.info(
        "Scanner starting. Interval: %dm. Targets: %s",
        config.scanner.interval_minutes,
        ", ".join(conn_mgr.list_targets()),
    )
    _run_scan(config, conn_mgr)

    def _shutdown(signum, frame):
        logger.info("Shutting down scanner...")
        scheduler.shutdown(wait=False)
        PID_FILE.unlink(missing_ok=True)
        conn_mgr.disconnect_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        scheduler.start()
    finally:
        PID_FILE.unlink(missing_ok=True)
        conn_mgr.disconnect_all()
