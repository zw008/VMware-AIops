"""A target must declare its environment for policy to scope rules by it.

Regression source: vmware-policy scopes rules by environment ("irreversible
work in production needs a second person"), but ``env`` used to be derived from
the *target's name*. Nobody names a vCenter target the literal string
``production`` — they name it ``prod-vcenter`` — so every environment-scoped
rule was configured and inert. The environment is now an explicit declaration
in config.yaml::

    targets:
      - name: prod-vcenter
        host: vcenter.corp.local
        environment: production   # <- declares which rules apply

vmware-policy cannot read this skill's config itself, so ``vmware_aiops/mcp_server/server.py``
registers a resolver at import. That registration is the whole control: without
it every target reads as undeclared and no environment-scoped rule can ever
fire. These tests pin both halves — the resolver is wired up, and what it
resolves reaches the policy decision.

Enforcement rolls out in two steps. The shipped baseline currently sets
``require_declared_environment: warn`` — an undeclared write runs and logs a
warning naming the fix. The next major release ships ``true`` and refuses it.
Both are pinned here (the ``baseline`` and ``enforcing`` fixtures) so that
release is a one-word change to a path already under test.
"""

import pytest
from vmware_policy.budget import reset_budget
from vmware_policy.decorators import PolicyDenied
from vmware_policy.envelope import paginated
from vmware_policy.environment import resolve_environment, set_environment_resolver
from vmware_policy.policy import reset_policy_engine

from vmware_aiops.config import AppConfig, TargetConfig

import vmware_aiops.mcp_server.server as server
import vmware_aiops.mcp_server.tools.alarm as alarm


@pytest.fixture(autouse=True)
def baseline(tmp_path, monkeypatch):
    """Point harness state at a tmp dir; no rules.yaml means the shipped baseline.

    That baseline is currently in its warn-only migration setting, so this is
    what an operator who has written no rules of their own gets today.
    """
    monkeypatch.setenv("OPS_HOME", str(tmp_path))
    monkeypatch.delenv("VMWARE_AUDIT_APPROVED_BY", raising=False)
    reset_policy_engine()
    reset_budget()
    yield
    # Restore the registration the server made at import, not None — leaving it
    # cleared would hand the rest of the session the unwired state these tests
    # exist to forbid.
    set_environment_resolver(server._environment_for)
    reset_policy_engine()
    reset_budget()


@pytest.fixture
def enforcing(tmp_path):
    """The same requirement switched on, as the next major release ships it."""
    (tmp_path / "rules.yaml").write_text("require_declared_environment: true\n")
    reset_policy_engine()


def _declare(monkeypatch, environment: str) -> None:
    """Register the real server resolver over a config declaring ``environment``."""
    config = AppConfig(
        targets=(
            TargetConfig(
                name="prod-vcenter",
                host="vcenter.example.com",
                config_username="administrator@vsphere.local",
                environment=environment,
            ),
        )
    )
    # Patch the mtime-cached loader the registered resolver calls, so the
    # resolver under test is the one the server actually installed — not a
    # stand-in.
    monkeypatch.setattr(server, "_cached_config", lambda: config)
    set_environment_resolver(server._environment_for)


@pytest.fixture
def stub_vcenter(monkeypatch):
    """Neutralise the vSphere calls; policy runs before the body either way."""
    monkeypatch.setattr(alarm, "_get_connection", lambda target=None: object())
    monkeypatch.setattr(
        alarm,
        "acknowledge_alarm",
        lambda si, entity, name, target_name="": {"acknowledged": True},
    )
    monkeypatch.setattr(
        alarm,
        "list_alarms",
        lambda si, limit=None: paginated([{"alarm_name": "CPU usage"}], total=1),
    )


# ---------------------------------------------------------------------------
# The resolver is registered at all
# ---------------------------------------------------------------------------


def test_server_registers_an_environment_resolver(monkeypatch):
    """The silent-failure mode this change exists to remove.

    With no resolver every target reads as undeclared, so environment-scoped
    rules stay as inert as they were before — and nothing in the operator's
    config can fix it. It must be caught here rather than in the field.
    """
    _declare(monkeypatch, "lab")
    assert resolve_environment("prod-vcenter") == "lab"


def test_undeclared_target_resolves_to_empty(monkeypatch):
    _declare(monkeypatch, "")
    assert resolve_environment("prod-vcenter") == ""


def test_omitted_target_falls_back_to_the_default_target(monkeypatch):
    """Tools take ``target`` as optional; the default target's label must apply."""
    _declare(monkeypatch, "lab")
    assert resolve_environment("") == "lab"


# ---------------------------------------------------------------------------
# Migration window: undeclared writes warn, they do not break
# ---------------------------------------------------------------------------


def test_write_against_undeclared_target_warns_but_runs(monkeypatch, stub_vcenter):
    """The shipped setting is warn, so no existing install breaks on upgrade."""
    _declare(monkeypatch, "")
    assert alarm.acknowledge_vcenter_alarm(
        entity_name="web-01", alarm_name="CPU usage", target="prod-vcenter"
    ) == {"acknowledged": True}


# ---------------------------------------------------------------------------
# Enforcing release: undeclared blocks writes, never reads
# ---------------------------------------------------------------------------


def test_write_against_undeclared_target_is_denied_when_enforcing(
    monkeypatch, enforcing, stub_vcenter
):
    _declare(monkeypatch, "")
    with pytest.raises(PolicyDenied) as excinfo:
        alarm.acknowledge_vcenter_alarm(
            entity_name="web-01", alarm_name="CPU usage", target="prod-vcenter"
        )
    assert excinfo.value.result.rule == "undeclared_environment"


def test_denial_names_the_config_key_to_add(monkeypatch, enforcing, stub_vcenter):
    """The error has to be actionable without opening the docs."""
    _declare(monkeypatch, "")
    with pytest.raises(PolicyDenied) as excinfo:
        alarm.acknowledge_vcenter_alarm(
            entity_name="web-01", alarm_name="CPU usage", target="prod-vcenter"
        )
    reason = str(excinfo.value)
    assert "environment" in reason
    assert "config.yaml" in reason


def test_write_against_declared_lab_target_succeeds(monkeypatch, enforcing, stub_vcenter):
    """Declaring an environment is what unblocks the work."""
    _declare(monkeypatch, "lab")
    assert alarm.acknowledge_vcenter_alarm(
        entity_name="web-01", alarm_name="CPU usage", target="prod-vcenter"
    ) == {"acknowledged": True}


# ---------------------------------------------------------------------------
# Reads are never gated, under either setting
# ---------------------------------------------------------------------------


def test_read_against_undeclared_target_works(monkeypatch, stub_vcenter):
    """Inspection must keep working with no config change at all."""
    _declare(monkeypatch, "")
    assert alarm.list_vcenter_alarms(target="prod-vcenter")["items"] == [
        {"alarm_name": "CPU usage"}
    ]


def test_read_against_undeclared_target_works_when_enforcing(monkeypatch, enforcing, stub_vcenter):
    _declare(monkeypatch, "")
    assert alarm.list_vcenter_alarms(target="prod-vcenter")["items"] == [
        {"alarm_name": "CPU usage"}
    ]


def test_read_against_declared_target_works_when_enforcing(monkeypatch, enforcing, stub_vcenter):
    _declare(monkeypatch, "lab")
    assert alarm.list_vcenter_alarms(target="prod-vcenter")["items"] == [
        {"alarm_name": "CPU usage"}
    ]
