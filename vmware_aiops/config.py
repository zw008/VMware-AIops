"""Configuration management for VMware AIops.

Loads targets and settings from YAML config file + environment variables.
Passwords are NEVER stored in config files — always via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

CONFIG_DIR = Path.home() / ".vmware-aiops"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass(frozen=True)
class TargetConfig:
    """A vCenter or ESXi connection target."""

    name: str
    host: str
    username: str
    type: Literal["vcenter", "esxi"] = "vcenter"
    port: int = 443
    verify_ssl: bool = False

    @property
    def password(self) -> str:
        env_key = f"VMWARE_{self.name.upper().replace('-', '_')}_PASSWORD"
        pw = os.environ.get(env_key, "")
        if not pw:
            raise OSError(
                f"Password not found. Set environment variable: {env_key}"
            )
        return pw


@dataclass(frozen=True)
class ScannerConfig:
    """Scanner daemon settings."""

    enabled: bool = True
    interval_minutes: int = 15
    log_types: tuple[str, ...] = ("vpxd", "hostd", "vmkernel")
    severity_threshold: str = "warning"
    lookback_hours: int = 1


@dataclass(frozen=True)
class NotifyConfig:
    """Notification settings."""

    log_file: str = str(CONFIG_DIR / "scan.log")
    webhook_url: str = ""
    webhook_timeout: int = 10


@dataclass(frozen=True)
class AppConfig:
    """Top-level application config."""

    targets: tuple[TargetConfig, ...] = ()
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)

    def get_target(self, name: str) -> TargetConfig:
        for t in self.targets:
            if t.name == name:
                return t
        available = ", ".join(t.name for t in self.targets)
        raise KeyError(f"Target '{name}' not found. Available: {available}")

    @property
    def default_target(self) -> TargetConfig:
        if not self.targets:
            raise ValueError("No targets configured. Check config.yaml")
        return self.targets[0]


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load config from YAML file, with env var overrides for passwords."""
    path = config_path or CONFIG_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to {CONFIG_FILE} and edit it."
        )

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    targets = tuple(
        TargetConfig(
            name=t["name"],
            host=t["host"],
            username=t.get("username", "administrator@vsphere.local"),
            type=t.get("type", "vcenter"),
            port=t.get("port", 443),
            verify_ssl=t.get("verify_ssl", False),
        )
        for t in raw.get("targets", [])
    )

    scanner_raw = raw.get("scanner", {})
    scanner = ScannerConfig(
        enabled=scanner_raw.get("enabled", True),
        interval_minutes=scanner_raw.get("interval_minutes", 15),
        log_types=tuple(scanner_raw.get("log_types", ["vpxd", "hostd", "vmkernel"])),
        severity_threshold=scanner_raw.get("severity_threshold", "warning"),
        lookback_hours=scanner_raw.get("lookback_hours", 1),
    )

    notify_raw = raw.get("notify", {})
    notify = NotifyConfig(
        log_file=notify_raw.get("log_file", str(CONFIG_DIR / "scan.log")),
        webhook_url=notify_raw.get("webhook_url", ""),
        webhook_timeout=notify_raw.get("webhook_timeout", 10),
    )

    return AppConfig(targets=targets, scanner=scanner, notify=notify)
