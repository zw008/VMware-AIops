"""Tests for config module."""

import os
from pathlib import Path

import pytest

from vmware_aiops.config import AppConfig, TargetConfig, load_config


@pytest.fixture()
def sample_config_file(tmp_path: Path) -> Path:
    config = tmp_path / "config.yaml"
    config.write_text("""
targets:
  - name: test-vc
    host: 10.0.0.1
    username: admin@vsphere.local
    type: vcenter
    port: 443
  - name: test-esxi
    host: 10.0.0.2
    username: root
    type: esxi

scanner:
  enabled: true
  interval_minutes: 5
  log_types: [hostd, vmkernel]
  severity_threshold: critical
  lookback_hours: 2

notify:
  log_file: /tmp/test-scan.log
  webhook_url: https://hooks.example.com/test
""")
    return config


@pytest.mark.unit
def test_load_config(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    assert len(cfg.targets) == 2
    assert cfg.targets[0].name == "test-vc"
    assert cfg.targets[0].host == "10.0.0.1"
    assert cfg.targets[0].type == "vcenter"
    assert cfg.targets[1].name == "test-esxi"
    assert cfg.targets[1].type == "esxi"


@pytest.mark.unit
def test_scanner_config(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    assert cfg.scanner.enabled is True
    assert cfg.scanner.interval_minutes == 5
    assert cfg.scanner.log_types == ("hostd", "vmkernel")
    assert cfg.scanner.severity_threshold == "critical"


@pytest.mark.unit
def test_notify_config(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    assert cfg.notify.webhook_url == "https://hooks.example.com/test"
    assert cfg.notify.log_file == "/tmp/test-scan.log"


@pytest.mark.unit
def test_get_target(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    t = cfg.get_target("test-vc")
    assert t.host == "10.0.0.1"


@pytest.mark.unit
def test_get_target_not_found(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    with pytest.raises(KeyError, match="not-exist"):
        cfg.get_target("not-exist")


@pytest.mark.unit
def test_default_target(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    assert cfg.default_target.name == "test-vc"


@pytest.mark.unit
def test_password_from_env(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    target = cfg.get_target("test-vc")
    os.environ["VMWARE_TEST_VC_PASSWORD"] = "secret123"
    try:
        assert target.password == "secret123"
    finally:
        del os.environ["VMWARE_TEST_VC_PASSWORD"]


@pytest.mark.unit
def test_password_missing_env(sample_config_file: Path) -> None:
    cfg = load_config(sample_config_file)
    target = cfg.get_target("test-vc")
    os.environ.pop("VMWARE_TEST_VC_PASSWORD", None)
    with pytest.raises(EnvironmentError, match="VMWARE_TEST_VC_PASSWORD"):
        _ = target.password


@pytest.mark.unit
def test_config_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


@pytest.mark.unit
def test_immutability() -> None:
    t = TargetConfig(name="x", host="h", username="u")
    with pytest.raises(AttributeError):
        t.name = "y"  # type: ignore[misc]
