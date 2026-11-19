import ipaddress
import random

import pytest

from app.engines.vlsm_engine import (AddressSpaceExhaustedError, allocate_hierarchical, allocate_vlsm,
                                     required_prefix, subnet_mask, wildcard_mask)


@pytest.mark.parametrize("p,w", [(0, "255.255.255.255"), (8, "0.255.255.255"), (16, "0.0.255.255"),
                                 (24, "0.0.0.255"), (25, "0.0.0.127"), (26, "0.0.0.63"), (30, "0.0.0.3"),
                                 (31, "0.0.0.1"), (32, "0.0.0.0")])
def test_wildcard_masks_edge_cases(p, w):
    assert wildcard_mask(p) == w
    assert str(ipaddress.ip_network(f"0.0.0.0/{p}").hostmask) == w   # cross-check vs stdlib


@pytest.mark.parametrize("p", range(0, 33))
def test_mask_and_wildcard_are_bitwise_complements(p):
    m = int(ipaddress.ip_address(subnet_mask(p)))
    w = int(ipaddress.ip_address(wildcard_mask(p)))
    assert m ^ w == 0xFFFFFFFF


@pytest.mark.parametrize("bad", [-1, 33, "24", None])
def test_invalid_prefix_rejected(bad):
    with pytest.raises(ValueError):
        wildcard_mask(bad)


@pytest.mark.parametrize("hosts,prefix", [(1, 30), (2, 30), (3, 29), (6, 29), (7, 28), (254, 24), (255, 23),
                                          (510, 23), (511, 22), (65534, 16)])
def test_required_prefix(hosts, prefix):
    assert required_prefix(hosts) == prefix


def test_zero_hosts_rejected():
    with pytest.raises(ValueError):
        required_prefix(0)


def test_sorted_descending_and_aligned():
    r = allocate_vlsm("192.168.0.0/24", [{"name": "s", "hosts": 10}, {"name": "L", "hosts": 100}, {"name": "m", "hosts": 50}])
    assert [a["name"] for a in r["allocations"]] == ["L", "m", "s"]
    assert [a["cidr"] for a in r["allocations"]] == ["192.168.0.0/25", "192.168.0.128/26", "192.168.0.192/28"]


def test_gateway_broadcast_usable():
    a = allocate_vlsm("10.0.0.0/24", [{"name": "x", "hosts": 50}])["allocations"][0]
    assert (a["gateway"], a["broadcast"], a["last_usable"], a["usable_addresses"]) == \
           ("10.0.0.1", "10.0.0.63", "10.0.0.62", 62)


def test_exhaustion_total():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_vlsm("10.0.0.0/24", [{"name": "a", "hosts": 200}, {"name": "b", "hosts": 100}])


def test_exhaustion_single_request_larger_than_root():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_vlsm("10.0.0.0/24", [{"name": "a", "hosts": 300}])


def test_exact_fill_then_one_more_fails():
    reqs = [{"name": f"n{i}", "hosts": 62} for i in range(4)]
    assert len(allocate_vlsm("10.0.0.0/24", reqs)["allocations"]) == 4
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_vlsm("10.0.0.0/24", reqs + [{"name": "x", "hosts": 1}])


def test_no_wraparound_at_top_of_ipv4_space():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_vlsm("0.0.0.0/0", [{"name": "a", "hosts": 2 ** 31}, {"name": "b", "hosts": 2 ** 31}])


def test_rationale_contains_math_and_utilisation():
    r = allocate_vlsm("10.0.0.0/24", [{"name": "a", "hosts": 100}])
    assert "2^7 - 2 = 126" in r["rationale"] and "host efficiency" in r["rationale"]


def _assert_disjoint(allocs):
    nets = sorted((ipaddress.ip_network(a["cidr"]) for a in allocs), key=lambda n: n.network_address)
    for x, y in zip(nets, nets[1:]):
        assert not x.overlaps(y), (x, y)


def test_random_requests_never_overlap_or_leave_root():
    rnd = random.Random(1234)
    for _ in range(300):
        reqs = [{"name": f"n{i}", "hosts": rnd.choice([1, 2, 5, 14, 30, 60, 120, 250, 500])} for i in range(rnd.randint(1, 12))]
        try:
            r = allocate_vlsm("10.0.0.0/20", reqs)
        except AddressSpaceExhaustedError:
            continue
        _assert_disjoint(r["allocations"])
        root = ipaddress.ip_network("10.0.0.0/20")
        for a in r["allocations"]:
            n = ipaddress.ip_network(a["cidr"])
            assert n.subnet_of(root)
            assert a["usable_addresses"] >= a["requested_hosts"]


def test_hierarchical_site_supernets_contain_their_subnets_and_are_disjoint():
    sites = [{"name": "A", "subnets": ["a1", "a2"], "external": False}, {"name": "B", "subnets": ["b1"], "external": False}]
    reqs = [{"name": "a1", "hosts": 100}, {"name": "a2", "hosts": 30}, {"name": "b1", "hosts": 200}]
    r = allocate_hierarchical("10.1.0.0/16", sites, reqs, [{"name": "L1", "hosts": 2}])
    _assert_disjoint(r["allocations"])
    blocks = {b["site"]: ipaddress.ip_network(b["cidr"]) for b in r["site_blocks"]}
    for a in r["allocations"]:
        assert ipaddress.ip_network(a["cidr"]).subnet_of(blocks[a["site"]])
    nets = list(blocks.values())
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            assert not nets[i].overlaps(nets[j])


def test_hierarchical_exhaustion():
    sites = [{"name": "A", "subnets": ["a"], "external": False}]
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_hierarchical("10.1.0.0/24", sites, [{"name": "a", "hosts": 250}], [{"name": "L", "hosts": 2}] * 3)
