import pytest
from app.engines.vlsm_engine import allocate_vlsm, wildcard_mask, AddressSpaceExhaustedError


def test_vlsm_allocates_largest_first_without_overlap():
    result = allocate_vlsm("192.168.0.0/24", [
        {"name": "A", "hosts": 100},
        {"name": "B", "hosts": 50},
        {"name": "C", "hosts": 20},
        {"name": "D", "hosts": 10},
    ])
    allocations = result["allocations"]
    assert [x["cidr"] for x in allocations] == [
        "192.168.0.0/25", "192.168.0.128/26",
        "192.168.0.192/27", "192.168.0.224/28"
    ]
    ranges = []
    for item in allocations:
        start = int(__import__("ipaddress").ip_network(item["cidr"]).network_address)
        end = int(__import__("ipaddress").ip_network(item["cidr"]).broadcast_address)
        ranges.append((start, end))
    for left, right in zip(ranges, ranges[1:]):
        assert left[1] < right[0]


def test_address_space_exhaustion():
    with pytest.raises(AddressSpaceExhaustedError):
        allocate_vlsm("192.168.1.0/28", [{"name": "TOO_BIG", "hosts": 30}])


def test_wildcard_mask():
    assert wildcard_mask(24) == "0.0.0.255"
    assert wildcard_mask(30) == "0.0.0.3"


def test_single_host_gets_minimum_lan_subnet():
    result = allocate_vlsm("10.0.0.0/24", [{"name": "ONE", "hosts": 1}])
    assert result["allocations"][0]["cidr"] == "10.0.0.0/30"
