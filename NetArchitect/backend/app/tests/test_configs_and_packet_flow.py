"""Config validation + packet-flow verification (ACL simulator) for all three presets."""
import ipaddress
import re

import pytest

from app.engines.acl_sim import Packet, evaluate, extract_acl
from app.engines.config_generator import PLACEHOLDER


def host(res, subnet, n=5):
    a = next(x for x in res["vlsm"]["allocations"] if x["name"] == subnet)
    return str(ipaddress.ip_address(a["network"]) + n)


def verdict(res, subnet, pkt):
    cfg = next(t for f, t in res["configs"]["devices"].items() if "L3SW" in f and f"ACL-{subnet}-IN" in t)
    return evaluate(extract_acl(cfg, f"ACL-{subnet}-IN"), pkt)[0]


# ------------------------------------------------------------------ structural checks
@pytest.mark.parametrize("key", ["campus_lan", "metro_man", "global_wan"])
def test_every_file_is_paste_ready(results, key):
    for fname, text in results[key]["configs"]["devices"].items():
        lines = text.splitlines()
        assert lines[0] == "enable" and lines[1] == "configure terminal", fname
        assert lines[-2:] == ["end", "write memory"], fname
        assert "\r" not in text


@pytest.mark.parametrize("key", ["campus_lan", "metro_man", "global_wan"])
def test_no_duplicate_interface_ip_and_all_inside_allocations(results, key):
    res = results[key]
    seen = {}
    nets = [ipaddress.ip_network(a["cidr"]) for a in res["vlsm"]["allocations"]]
    for fname, text in res["configs"]["devices"].items():
        for m in re.finditer(r"ip address (\S+) (\S+)", text):
            ip = ipaddress.ip_interface(f"{m.group(1)}/{m.group(2)}")
            assert str(ip.ip) not in seen, f"duplicate {ip.ip} in {fname} and {seen.get(str(ip.ip))}"
            seen[str(ip.ip)] = fname
            assert any(ip.network == n for n in nets), f"{ip} not an allocated subnet ({fname})"
            assert ip.ip not in (ip.network.network_address, ip.network.broadcast_address)


@pytest.mark.parametrize("key", ["campus_lan", "metro_man", "global_wan"])
def test_both_ends_of_every_link_share_a_subnet(results, key):
    for c in results[key]["configs"]["cabling"]:
        if c["ip_a"]:
            net = ipaddress.ip_network(c["subnet"])
            assert ipaddress.ip_address(c["ip_a"]) in net and ipaddress.ip_address(c["ip_b"]) in net
            assert c["ip_a"] != c["ip_b"]


@pytest.mark.parametrize("key", ["campus_lan", "metro_man", "global_wan"])
def test_trunk_allowed_vlans_match_on_both_ends_and_are_constrained(results, key):
    devs = results[key]["configs"]["devices"]
    allowed = {f: re.findall(r"switchport trunk allowed vlan (\S+)", t) for f, t in devs.items()}
    sw = [f for f in devs if "L3SW" in f and allowed[f]]
    acc = [f for f in devs if "ACCESS" in f]
    if acc:
        assert set(allowed[sw[0]]) == set(allowed[acc[0]])
    for f, t in devs.items():
        if "switchport mode trunk" in t:
            assert "switchport nonegotiate" in t and "native vlan 999" in t and "allowed vlan" in t
            assert "allowed vlan all" not in t


@pytest.mark.parametrize("key", ["campus_lan", "metro_man", "global_wan"])
def test_hostnames_and_secrets_safe(results, key):
    for fname, text in results[key]["configs"]["devices"].items():
        if fname.startswith("POLICY"):
            continue
        host_ = re.search(r"^hostname (.+)$", text, re.M).group(1)
        assert re.fullmatch(r"[A-Za-z0-9\-]+", host_)
        assert PLACEHOLDER in text
        assert len(re.findall(r"^hostname ", text, re.M)) == 1


def test_campus_uses_single_area_ospf_rstp_and_svis(results):
    r = results["campus_lan"]
    assert r["routing"]["protocol"] == "OSPF Area 0"
    sw = r["configs"]["devices"]["CAMPUS-L3SW.cfg"]
    assert "spanning-tree mode rapid-pvst" in sw and "ip routing" in sw
    assert re.search(r"interface Vlan10\n", sw) and "area 0" in sw and "area 1" not in sw
    assert "ip access-group ACL-STUDENTS-IN in" in sw and "Port-channel1" in sw


def test_metro_has_evpl_qos_dual_homing_and_summaries(results):
    hub = results["metro_man"]["configs"]["devices"]["HQ-RTR.cfg"]
    assert "encapsulation dot1Q" in hub and "priority percent 20" in hub and "service-policy output WAN-QOS" in hub
    assert hub.count("ip ospf cost 10\n") == 2 and hub.count("ip ospf cost 100\n") == 2
    assert re.findall(r"area \d range", hub) and results["metro_man"]["routing"]["protocol"] == "Multi-Area OSPF"


def test_wan_has_ipsec_bgp_aggregate_and_prefix_lists(results):
    r = results["global_wan"]
    hub = r["configs"]["devices"]["CITY-1-RTR.cfg"]
    assert r["routing"]["protocol"] == "eBGP"
    assert "crypto map" in hub and "router bgp 65001" in hub and "neighbor" in hub
    assert r["configs"]["aggregate"] == "10.30.0.0/21"
    assert "ip route 10.30.0.0 255.255.248.0 Null0" in hub and "ip prefix-list PL-OUT" in hub
    cloud = r["configs"]["devices"]["CLOUD-VPC-RTR.cfg"]
    assert "router bgp 65002" in cloud and "remote-as 65001" in cloud


def test_ipsec_crypto_acls_are_mirror_images(results):
    devs = results["global_wan"]["configs"]["devices"]
    hub = devs["CITY-1-RTR.cfg"]
    spoke = devs["CITY-2-RTR.cfg"]
    h = re.findall(r"access-list 10\d permit ip (\S+ \S+) (\S+ \S+)", hub)[0]
    s = re.findall(r"access-list 10\d permit ip (\S+ \S+) (\S+ \S+)", spoke)[0]
    assert (h[0], h[1]) == (s[1], s[0])


# ------------------------------------------------------------------ packet-flow verification
def test_student_to_server_https_permitted_ssh_denied(results):
    r = results["campus_lan"]
    stu, srv = host(r, "STUDENTS"), host(r, "SERVERS")
    assert verdict(r, "STUDENTS", Packet("tcp", stu, srv, 50000, 443)) == "permit"
    assert verdict(r, "STUDENTS", Packet("tcp", stu, srv, 50000, 80)) == "permit"
    assert verdict(r, "STUDENTS", Packet("tcp", stu, srv, 50000, 22)) == "deny"
    assert verdict(r, "STUDENTS", Packet("icmp", stu, srv, icmp_type="echo")) == "permit"


def test_student_cannot_reach_admin_or_mgmt_but_can_reach_internet(results):
    r = results["campus_lan"]
    stu = host(r, "STUDENTS")
    for target in ("STAFF_ADMIN", "MGMT"):
        assert verdict(r, "STUDENTS", Packet("tcp", stu, host(r, target), 50000, 443)) == "deny"
    assert verdict(r, "STUDENTS", Packet("tcp", stu, "8.8.8.8", 50000, 443)) == "permit"


def test_spoofed_source_is_dropped(results):
    r = results["campus_lan"]
    assert verdict(r, "STUDENTS", Packet("ip", "10.10.4.9", host(r, "SERVERS"))) == "deny"


def test_dhcp_discover_permitted(results):
    r = results["campus_lan"]
    assert verdict(r, "STUDENTS", Packet("udp", "0.0.0.0", "255.255.255.255", 68, 67)) == "permit"


def test_iot_is_quarantined_from_internal_networks(results):
    r = results["campus_lan"]
    iot = host(r, "IOT_AP")
    assert verdict(r, "IOT_AP", Packet("tcp", iot, host(r, "SERVERS"), 40000, 8883)) == "permit"
    assert verdict(r, "IOT_AP", Packet("tcp", iot, host(r, "STUDENTS"), 40000, 445)) == "deny"
    assert verdict(r, "IOT_AP", Packet("tcp", iot, "1.1.1.1", 40000, 443)) == "permit"


def test_servers_reply_but_cannot_initiate(results):
    r = results["campus_lan"]
    srv, stu = host(r, "SERVERS"), host(r, "STUDENTS")
    assert verdict(r, "SERVERS", Packet("tcp", srv, stu, 443, 50000, established=True)) == "permit"
    assert verdict(r, "SERVERS", Packet("tcp", srv, stu, 40000, 3389)) == "deny"
    assert verdict(r, "SERVERS", Packet("icmp", srv, stu, icmp_type="echo-reply")) == "permit"


def test_fintech_servers_protected_in_metro(results):
    r = results["metro_man"]
    usr, fin = host(r, "REMOTE_A_USERS"), host(r, "FINTECH_SERVERS")
    assert verdict(r, "REMOTE_A_USERS", Packet("tcp", usr, fin, 50000, 443)) == "permit"
    assert verdict(r, "REMOTE_A_USERS", Packet("tcp", usr, fin, 50000, 22)) == "deny"


def test_acl_sim_first_match_and_implicit_deny():
    rules = [__import__("app.engines.acl_sim", fromlist=["parse_rule"]).parse_rule(l) for l in
             ["permit tcp 10.0.0.0 0.0.0.255 any eq 80", "deny ip any any"]]
    assert evaluate(rules, Packet("tcp", "10.0.0.7", "1.1.1.1", 1, 80))[0] == "permit"
    assert evaluate(rules[:1], Packet("tcp", "10.0.0.7", "1.1.1.1", 1, 81)) == ("deny", "implicit deny")
