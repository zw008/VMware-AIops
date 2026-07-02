"""Regression tests — pyVmomi API misuse found in the 2026-06 vim-conformance audit.

Each test guards a verified bug (pyVmomi 8.0.3/9.0 type introspection):

- C1: Folder.MoveInto_Task does not exist — must be MoveIntoFolder_Task(list=[...])
- C2: AlarmManager.SetAlarmStatus does not exist — must be ClearTriggeredAlarms(filter=...)
- H1: Datastore.host is HostMount[] — membership test must unwrap .key (HostSystem)
- H2: sensor status comes from healthState.key (green/yellow/red), not sensorType
- M1: event class is DVPortgroupReconfiguredEvent (lowercase g) — typo'd names never match

See tests/eval/regression/test_vim_attribute_conformance.py for the generic
introspection net that prevents the whole bug class.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# ── C1: remove_host_from_cluster must call Folder.MoveIntoFolder_Task ──


def test_remove_host_uses_move_into_folder_task() -> None:
    """vim.Folder has no MoveInto_Task (that name only exists on
    ClusterComputeResource). The correct Folder method is
    MoveIntoFolder_Task with a single 'list' parameter."""
    from vmware_aiops.ops import cluster_mgmt

    host = MagicMock()
    host.runtime.inMaintenanceMode = True

    member = MagicMock()
    member.name = "esxi-1"
    cluster = MagicMock()
    cluster.host = [member]

    class FakeDatacenter:
        def __init__(self) -> None:
            self.hostFolder = MagicMock()

    dc = FakeDatacenter()
    cluster.parent = dc

    fake_vim = SimpleNamespace(Datacenter=FakeDatacenter)
    with patch.object(cluster_mgmt, "_require_cluster", return_value=cluster), \
         patch.object(cluster_mgmt, "find_host_by_name", return_value=host), \
         patch.object(cluster_mgmt, "_wait_for_task"), \
         patch.object(cluster_mgmt, "vim", fake_vim):
        cluster_mgmt.remove_host_from_cluster(MagicMock(), "cluster1", "esxi-1")

    dc.hostFolder.MoveInto_Task.assert_not_called()  # does not exist on vim.Folder
    dc.hostFolder.MoveIntoFolder_Task.assert_called_once_with([host])


# ── C2: reset_alarm must use AlarmManager.ClearTriggeredAlarms ──


def test_reset_alarm_uses_clear_triggered_alarms() -> None:
    """AlarmManager.SetAlarmStatus does not exist in pyVmomi (verified via
    _methodInfo). reset_alarm must build a vim.alarm.AlarmFilterSpec and call
    ClearTriggeredAlarms. AlarmFilterSpec has only status/typeEntity/typeTrigger
    — no per-entity field — so the filter scopes by entity type + status."""
    from pyVmomi import vim

    from vmware_aiops.ops import alarm_mgmt

    entity = MagicMock()  # not a vim.HostSystem / vim.VirtualMachine → entityTypeAll
    alarm_state = MagicMock()
    alarm_state.overallStatus = "red"

    si = MagicMock()
    content = si.RetrieveContent.return_value

    with patch.object(
        alarm_mgmt, "_find_triggered_alarm", return_value=(entity, alarm_state)
    ):
        result = alarm_mgmt.reset_alarm(si, "esxi-1", "Host memory usage")

    content.alarmManager.SetAlarmStatus.assert_not_called()
    assert content.alarmManager.ClearTriggeredAlarms.called, (
        "reset_alarm must call AlarmManager.ClearTriggeredAlarms "
        "(SetAlarmStatus does not exist in the vSphere API)"
    )
    _, kwargs = content.alarmManager.ClearTriggeredAlarms.call_args
    filt = kwargs["filter"]
    assert isinstance(filt, vim.alarm.AlarmFilterSpec)
    assert filt.typeEntity == "entityTypeAll"
    assert filt.typeTrigger == "triggerTypeAll"
    assert list(filt.status) == ["red"], "filter must narrow to the alarm's current status"
    assert result["action"] == "reset"


def test_reset_alarm_scopes_filter_by_entity_type() -> None:
    """A HostSystem entity must narrow the filter to entityTypeHost."""
    from pyVmomi import vim

    from vmware_aiops.ops import alarm_mgmt

    host_entity = MagicMock(spec=vim.HostSystem)
    alarm_state = MagicMock()
    alarm_state.overallStatus = "yellow"

    si = MagicMock()
    content = si.RetrieveContent.return_value

    with patch.object(
        alarm_mgmt, "_find_triggered_alarm", return_value=(host_entity, alarm_state)
    ):
        alarm_mgmt.reset_alarm(si, "esxi-1", "Host memory usage")

    _, kwargs = content.alarmManager.ClearTriggeredAlarms.call_args
    assert kwargs["filter"].typeEntity == "entityTypeHost"


def test_reset_alarm_fails_fast_before_clearing_on_unknown_alarm() -> None:
    """ClearTriggeredAlarms has a broad blast radius (all alarms matching
    entity type + status), so a typo'd entity/alarm name must raise from the
    lookup and never reach the AlarmManager."""
    import pytest

    from vmware_aiops.ops import alarm_mgmt

    si = MagicMock()
    content = si.RetrieveContent.return_value

    with patch.object(
        alarm_mgmt,
        "_find_triggered_alarm",
        side_effect=ValueError("No triggered alarm 'Hots memory usage' on 'esxi-1'"),
    ):
        with pytest.raises(ValueError):
            alarm_mgmt.reset_alarm(si, "esxi-1", "Hots memory usage")

    content.alarmManager.ClearTriggeredAlarms.assert_not_called()


# ── H1: migrate_vm datastore-access check must unwrap HostMount.key ──


def test_migrate_vm_recognizes_shared_storage_via_hostmount_key() -> None:
    """Datastore.host is vim.Datastore.HostMount[] — each element wraps the
    HostSystem in .key. Comparing the HostSystem against the raw HostMount list
    always misses, so every cross-host vMotion on shared storage was rejected
    with a bogus 'no access to source datastore' error."""
    from vmware_aiops.ops import vm_lifecycle

    target_host = MagicMock()
    target_host.parent.resourcePool = MagicMock()

    vm = MagicMock()
    vm.runtime.host.name = "esxi-office"

    mount = MagicMock()  # vim.Datastore.HostMount
    mount.key = target_host
    src_ds = MagicMock()
    src_ds.name = "shared-nas"
    src_ds.host = [mount]
    vm.datastore = [src_ds]

    class StubRelocateSpec:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    with patch.object(vm_lifecycle, "_require_vm", return_value=vm), \
         patch.object(vm_lifecycle, "find_host_by_name", return_value=target_host), \
         patch.object(vm_lifecycle, "_wait_for_task"), \
         patch.object(vm_lifecycle.vim.vm, "RelocateSpec", StubRelocateSpec):
        result = vm_lifecycle.migrate_vm(MagicMock(), "vm1", "esxi-home")

    assert "no access" not in result.lower(), (
        "target host mounts the source datastore (HostMount.key) — "
        f"migration must proceed, got: {result}"
    )
    assert vm.Relocate.called, "Relocate task was never submitted"


# ── H2: hardware sensor status must come from healthState.key ──


def test_hardware_status_reads_healthstate_not_sensortype() -> None:
    """sensor.sensorType is the category (temperature/voltage/fan...), not the
    health. The green/yellow/red status lives in sensor.healthState.key."""
    from pyVmomi import vim

    from tests.eval.regression._pc_fakes import NoLazyMO, make_si
    from vmware_aiops.ops.health import get_host_hardware_status

    sensor = MagicMock()
    sensor.name = "CPU1 Temp"
    sensor.sensorType = "temperature"
    sensor.healthState.key = "green"
    sensor.currentReading = 4500
    sensor.baseUnits = "C"

    runtime_health = MagicMock()
    runtime_health.systemHealthInfo.numericSensorInfo = [sensor]

    # Hardware status is fetched via batched PropertyCollector, not a lazy walk.
    si = make_si({
        vim.HostSystem: [
            (
                NoLazyMO("host:esxi-1"),
                {"name": "esxi-1", "runtime.healthSystemRuntime": runtime_health},
            )
        ]
    })

    rows = get_host_hardware_status(si)

    assert rows, "expected one sensor row"
    assert rows[0]["status"] == "green", (
        f"status must come from healthState.key, got {rows[0]['status']!r} (sensorType?)"
    )
    assert rows[0]["type"] == "temperature", "sensorType should be kept as the 'type' column"


# ── M1: every event name in the severity sets must exist in vim.event ──


def test_all_event_severity_names_exist_in_pyvmomi() -> None:
    """Typo'd event class names (e.g. DVPortGroupReconfiguredEvent with capital G)
    silently never match type(event).__name__ — events fall through to 'info'."""
    from pyVmomi import vim

    from vmware_aiops.ops.health import CRITICAL_EVENTS, INFO_EVENTS, WARNING_EVENTS

    missing = sorted(
        name
        for name in (CRITICAL_EVENTS | WARNING_EVENTS | INFO_EVENTS)
        if not hasattr(vim.event, name)
    )
    assert not missing, f"event names not found in vim.event (typo?): {missing}"
