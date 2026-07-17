"""Host vmk ops: validation, preview/confirm gates, service guard, esxcli
ping arg construction + XML parsing shapes (incl. ESXi's 'Recieved' typo)."""
import types

import pytest

from vmware_aiops.ops import host_network_mgmt as hnm
from vmware_aiops.ops.host_network_mgmt import (
    HostNetworkError,
    HostNotFoundError,
    add_host_vmk,
    list_host_vmks,
    remove_host_vmk,
    vmk_ping,
)


def _vnic(device, ip=None, netmask="255.255.255.0", mtu=1500, mac="00:00:00:00:00:01"):
    spec = types.SimpleNamespace(
        ip=types.SimpleNamespace(ipAddress=ip, subnetMask=netmask, dhcp=False) if ip else None,
        mtu=mtu, mac=mac, distributedVirtualPort=None, netStackInstanceKey="defaultTcpipStack",
    )
    return types.SimpleNamespace(device=device, spec=spec, portgroup="")


class FakeNetworkSystem:
    def __init__(self):
        self.added = []
        self.removed = []

    def AddVirtualNic(self, portgroup, nic):
        self.added.append((portgroup, nic))
        return "vmk2"

    def RemoveVirtualNic(self, device):
        self.removed.append(device)


def _nic_mgr(selected=()):
    """virtualNicManager with vmk0 selected for management when requested."""
    cand = types.SimpleNamespace(key="k-vmk0", device="vmk0")
    cfgs = [
        types.SimpleNamespace(nicType=t, selectedVnic=["k-vmk0"], candidateVnic=[cand])
        for t in selected
    ]
    return types.SimpleNamespace(info=types.SimpleNamespace(netConfig=cfgs))


def _host(vnics, selected_services=("management",)):
    ns = FakeNetworkSystem()
    host = types.SimpleNamespace(
        name="esxi01.lab.example.com",
        _moId="host-123",
        config=types.SimpleNamespace(network=types.SimpleNamespace(vnic=vnics)),
        configManager=types.SimpleNamespace(
            networkSystem=ns, virtualNicManager=_nic_mgr(selected_services)
        ),
    )
    return host, ns


def _pg(name="pg-tep-test"):
    return types.SimpleNamespace(
        name=name,
        key="dvportgroup-42",
        config=types.SimpleNamespace(
            distributedVirtualSwitch=types.SimpleNamespace(uuid="50 11 22 33")
        ),
    )


@pytest.fixture
def env(monkeypatch):
    host, ns = _host([_vnic("vmk0", ip="192.0.2.11"), _vnic("vmk1", ip="192.0.2.21")])
    monkeypatch.setattr(hnm, "find_host_by_name", lambda si, n: host if n == host.name else None)
    monkeypatch.setattr(hnm, "_get_objects", lambda si, t: [_pg()])
    return types.SimpleNamespace(host=host, ns=ns, si=object())


# --- add_host_vmk ---------------------------------------------------------------

def test_add_validates_before_any_write(env):
    cases = [
        dict(ip="not-an-ip", netmask="255.255.255.0", mtu=9000),
        dict(ip="198.51.100.1", netmask="255.0.255.0", mtu=9000),   # non-contiguous mask
        dict(ip="198.51.100.1", netmask="255.255.255.0", mtu=10),   # mtu too small
        dict(ip="198.51.100.1", netmask="255.255.255.0", mtu=10000),
        dict(ip="192.0.2.11", netmask="255.255.255.0", mtu=9000),   # duplicate host IP
    ]
    for kw in cases:
        with pytest.raises(HostNetworkError):
            add_host_vmk(env.si, env.host.name, "pg-tep-test", confirm=True, **kw)
    assert env.ns.added == []


def test_add_unknown_host_and_portgroup(env):
    with pytest.raises(HostNotFoundError):
        add_host_vmk(env.si, "nope-host", "pg-tep-test", "198.51.100.1", "255.255.255.0")
    with pytest.raises(HostNetworkError, match="portgroup"):
        add_host_vmk(env.si, env.host.name, "nope-pg", "198.51.100.1", "255.255.255.0")
    assert env.ns.added == []


def test_add_preview_never_writes(env):
    out = add_host_vmk(env.si, env.host.name, "pg-tep-test",
                       "198.51.100.1", "255.255.255.0", mtu=9000)
    assert out["action"] == "preview"
    assert out["would_create"]["mtu"] == 9000
    assert out["would_create"]["gateway"] is None
    assert out["would_create"]["services"] == []
    assert env.ns.added == []


def test_add_confirm_sends_exact_dvs_spec(env):
    out = add_host_vmk(env.si, env.host.name, "pg-tep-test",
                       "198.51.100.1", "255.255.255.0", mtu=9000, confirm=True)
    assert out["action"] == "created"
    assert out["device"] == "vmk2"
    (portgroup_arg, nic), = env.ns.added
    assert portgroup_arg == ""                       # DVS contract: empty std portgroup
    assert nic.ip.ipAddress == "198.51.100.1"
    assert nic.ip.subnetMask == "255.255.255.0"
    assert nic.ip.dhcp is False
    assert nic.mtu == 9000
    assert nic.distributedVirtualPort.portgroupKey == "dvportgroup-42"
    assert nic.distributedVirtualPort.switchUuid == "50 11 22 33"


# --- remove_host_vmk ------------------------------------------------------------

def test_remove_refuses_service_selected_vmk(env):
    with pytest.raises(HostNetworkError, match="REFUSED"):
        remove_host_vmk(env.si, env.host.name, "vmk0", confirm=True)
    assert env.ns.removed == []


def test_remove_unknown_vmk_lists_present(env):
    with pytest.raises(HostNetworkError, match="vmk9"):
        remove_host_vmk(env.si, env.host.name, "vmk9", confirm=True)


def test_remove_preview_then_confirm(env):
    out = remove_host_vmk(env.si, env.host.name, "vmk1")
    assert out["action"] == "preview"
    assert env.ns.removed == []
    out = remove_host_vmk(env.si, env.host.name, "vmk1", confirm=True)
    assert out["action"] == "removed"
    assert env.ns.removed == ["vmk1"]


# --- list ------------------------------------------------------------------------

def test_list_reports_services_and_shape(env, monkeypatch):
    monkeypatch.setattr(hnm, "_get_objects", lambda si, t: [env.host])
    out = list_host_vmks(env.si)
    by_dev = {v["device"]: v for v in out["vmks"]}
    assert by_dev["vmk0"]["services"] == ["management"]
    assert by_dev["vmk1"]["services"] == []
    assert by_dev["vmk1"]["ip"] == "192.0.2.21"


# --- vmk_ping --------------------------------------------------------------------

MME_RETURN_XML = '<returnval type="ReflectManagedMethodExecuter">ha-mme-123</returnval>'

# esxcli returns the PingOutput XML-escaped inside <response>, with ESXi's
# genuine "Recieved"/"PacketLost" spellings.
PING_OK_XML = (
    "<ExecuteSoapResponse><returnval><response>"
    "&lt;output xsi:type=&quot;vim.EsxCLI.network.diag.ping.PingOutput&quot;&gt;"
    "&lt;Summary&gt;&lt;Duplicated&gt;0&lt;/Duplicated&gt;"
    "&lt;HostAddr&gt;198.51.100.2&lt;/HostAddr&gt;"
    "&lt;PacketLost&gt;0&lt;/PacketLost&gt;&lt;Recieved&gt;3&lt;/Recieved&gt;"
    "&lt;RoundtripAvgMS&gt;512&lt;/RoundtripAvgMS&gt;"
    "&lt;Transmitted&gt;3&lt;/Transmitted&gt;&lt;/Summary&gt;&lt;/output&gt;"
    "</response></returnval></ExecuteSoapResponse>"
)

PING_FAULT_XML = (
    "<ExecuteSoapResponse><returnval><fault>"
    "<faultMsg>sendto() failed (Message too long)</faultMsg>"
    "<faultMsg>sendto() failed (Message too long)</faultMsg>"
    "</fault></returnval></ExecuteSoapResponse>"
)


def _wire_soap(monkeypatch, execute_response):
    """First _soap_post call = RetrieveManagedMethodExecuter; second = ExecuteSoap."""
    bodies = []

    def fake_post(si, body):
        bodies.append(body)
        return MME_RETURN_XML if "RetrieveManagedMethodExecuter" in body else execute_response

    monkeypatch.setattr(hnm, "_soap_post", fake_post)
    return bodies


def test_ping_success_parses_misspelled_received(env, monkeypatch):
    bodies = _wire_soap(monkeypatch, PING_OK_XML)
    out = vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2", size=8972, df=True)
    assert out["success"] is True
    assert out["summary"]["received"] == 3
    assert out["summary"]["transmitted"] == 3
    assert out["summary"]["packet_lost_pct"] == 0
    execute = bodies[1]
    assert "ha-mme-123" in execute
    assert "<moid>ha-cli-handler-network-diag</moid>" in execute
    assert "<method>vim.EsxCLI.network.diag.ping</method>" in execute
    assert "<val>&lt;size&gt;8972&lt;/size&gt;</val>" in execute
    assert "&lt;df&gt;true&lt;/df&gt;" in execute
    assert "&lt;interface&gt;vmk1&lt;/interface&gt;" in execute
    assert "netstack" not in execute


def test_ping_df_too_big_returns_fault_not_error(env, monkeypatch):
    _wire_soap(monkeypatch, PING_FAULT_XML)
    out = vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2", size=8972, df=True)
    assert out["success"] is False
    assert "Message too long" in out["fault"]


def test_ping_netstack_arg_included_when_set(env, monkeypatch):
    bodies = _wire_soap(monkeypatch, PING_OK_XML)
    vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2", netstack="vxlan")
    assert "&lt;netstack&gt;vxlan&lt;/netstack&gt;" in bodies[1]


# Live-verified vCenter shape (2026-07-16): reflect-namespaced <reflect:response>
PING_NS_XML = (
    "<ExecuteSoapResponse><returnval><reflect:response>"
    "&lt;obj&gt;&lt;DataObject&gt;&lt;Summary&gt;"
    "&lt;PacketLost&gt;0&lt;/PacketLost&gt;&lt;Recieved&gt;3&lt;/Recieved&gt;"
    "&lt;RoundtripAvgMS&gt;0&lt;/RoundtripAvgMS&gt;"
    "&lt;Transmitted&gt;3&lt;/Transmitted&gt;&lt;/Summary&gt;"
    "&lt;/DataObject&gt;&lt;/obj&gt;"
    "</reflect:response></returnval></ExecuteSoapResponse>"
)


def test_ping_parses_namespace_prefixed_response(env, monkeypatch):
    _wire_soap(monkeypatch, PING_NS_XML)
    out = vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2")
    assert out["success"] is True
    assert out["summary"]["received"] == 3
    assert "raw_response" not in out


def test_ping_ns_prefixed_fault_still_detected(env, monkeypatch):
    _wire_soap(monkeypatch,
               "<returnval><reflect:fault><reflect:faultMsg>sendto() failed "
               "(Message too long)</reflect:faultMsg></reflect:fault></returnval>")
    out = vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2", df=True, size=8972)
    assert out["success"] is False
    assert "Message too long" in out["fault"]


def test_ping_soap_fault_raises(env, monkeypatch):
    def fake_post(si, body):
        raise HostNetworkError("SOAP fault: The session is not authenticated")

    monkeypatch.setattr(hnm, "_soap_post", fake_post)
    with pytest.raises(HostNetworkError, match="not authenticated"):
        vmk_ping(env.si, env.host.name, "vmk1", "198.51.100.2")


def test_ping_validation_fires_before_soap(env, monkeypatch):
    bodies = _wire_soap(monkeypatch, PING_OK_XML)
    for kw in (dict(dest_ip="bad"), dict(dest_ip="1.2.3.4", size=0),
               dict(dest_ip="1.2.3.4", count=0)):
        with pytest.raises(HostNetworkError):
            vmk_ping(env.si, env.host.name, "vmk1", **kw)
    with pytest.raises(HostNetworkError, match="vmk7"):
        vmk_ping(env.si, env.host.name, "vmk7", "1.2.3.4")
    assert bodies == []
