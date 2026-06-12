"""Regression: `vm set-ttl` is a destructive (unattended-delete) op (issue #25).

Unlike the other destructive commands, set-ttl used to schedule an unattended
auto-delete with neither double-confirmation nor --dry-run. These tests pin the
new behaviour:

- `set-ttl --dry-run` previews without writing a TTL entry.
- `set-ttl` aborts (writes nothing) when the user declines confirmation.
- `set-ttl` with confirmation schedules the entry.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vmware_aiops.cli import app


def _patch_ttl_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the TTL store at an isolated temp file."""
    from vmware_aiops.ops import ttl

    store_file = tmp_path / "ttl.json"
    monkeypatch.setattr(ttl, "_TTL_FILE", store_file)
    return store_file


def test_set_ttl_dry_run_writes_no_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_file = _patch_ttl_store(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        app, ["vm", "set-ttl", "lab-vm-01", "--minutes", "480", "--dry-run"]
    )

    assert result.exit_code == 0
    assert "DRY-RUN" in result.output
    assert "lab-vm-01" in result.output
    # No TTL store written at all.
    assert not store_file.exists()
    from vmware_aiops.ops.ttl import list_ttl

    assert list_ttl() == []


def test_set_ttl_aborts_when_user_declines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_file = _patch_ttl_store(monkeypatch, tmp_path)

    # Decline the first confirmation prompt.
    result = CliRunner().invoke(
        app, ["vm", "set-ttl", "lab-vm-01", "--minutes", "480"], input="n\n"
    )

    assert result.exit_code != 0  # aborted
    assert not store_file.exists()
    from vmware_aiops.ops.ttl import list_ttl

    assert list_ttl() == []


def test_set_ttl_schedules_when_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_ttl_store(monkeypatch, tmp_path)

    # Accept both confirmation prompts.
    result = CliRunner().invoke(
        app, ["vm", "set-ttl", "lab-vm-01", "--minutes", "480"], input="y\ny\n"
    )

    assert result.exit_code == 0
    from vmware_aiops.ops.ttl import list_ttl

    entries = list_ttl()
    assert len(entries) == 1
    assert entries[0]["vm_name"] == "lab-vm-01"
