import pytest
from pydantic import ValidationError

from app.analysis import analyze
from app.engines.media_engine import PhysicalDistanceViolationError
from app.engines.routing_engine import recommend_routing
from app.engines.topology_engine import recommend_topology
from app.models.schemas import NetworkRequest


def test_49_subnets_single_site_is_area0_and_50_is_multi_area():
    assert recommend_routing(49, 1, 1, False)["protocol"] == "OSPF Area 0"
    assert recommend_routing(50, 1, 1, False)["protocol"] == "Multi-Area OSPF"


def test_campus_buildings_do_not_force_multi_area():      # regression for starter-code bug (audit case 4)
    assert recommend_routing(6, 1, 1, False, building_count=3)["protocol"] == "OSPF Area 0"


def test_multisite_is_multi_area_and_external_is_bgp():
    assert recommend_routing(5, 1, 3, False)["protocol"] == "Multi-Area OSPF"
    assert recommend_routing(5, 1, 1, True)["protocol"] == "eBGP"
    assert recommend_routing(5, 2, 4, False)["protocol"] == "eBGP"


def test_routing_rationale_cites_rfcs():
    assert "RFC 2328" in recommend_routing(5, 1, 1, False)["rationale"]
    assert "RFC 4271" in recommend_routing(5, 2, 4, True)["rationale"]


@pytest.mark.parametrize("args", [(0, 1, 1, False), (5, 0, 1, False), (5, 1, 0, False)])
def test_routing_rejects_nonsense(args):
    with pytest.raises(ValueError):
        recommend_routing(*args)


def test_topology_tiers_and_math():
    t = recommend_topology(1600, 1, 3, "medium", 1000, 10000)
    assert t["three_tier"] and t["access_switches"] == 42 and t["oversubscription_ratio"] == 2.4
    assert "ceil(1600 / (48 ports x 80% fill)) = 42" in t["rationale"]
    assert not recommend_topology(200, 1, 1, "low", 1000, 10000)["three_tier"]


# ---- schema / parameter engine
def _req(**kw):
    base = dict(endpoints=10, subnet_requests=[{"name": "A", "hosts": 10}])
    base.update(kw)
    return NetworkRequest(**base)


@pytest.mark.parametrize("kw", [
    dict(root_cidr="10.0.0.1/24"), dict(root_cidr="10.0.0.0/30"), dict(root_cidr="::/64"), dict(root_cidr="bogus"),
    dict(endpoints=0), dict(distance_m=0), dict(distance_m=-5), dict(site_count=0),
    dict(subnet_requests=[]), dict(subnet_requests=[{"name": "A", "hosts": 0}]),
    dict(subnet_requests=[{"name": "A", "hosts": 5}, {"name": "a", "hosts": 5}]),
    dict(resiliency="extreme"), dict(requested_media="coax"), dict(unknown_field=1),
])
def test_invalid_parameters_rejected(kw):
    with pytest.raises(ValidationError):
        _req(**kw)


@pytest.mark.parametrize("name", ["x\nusername evil privilege 15 secret pw", "a;b", "bad\r\nname", "../etc", ""])
def test_unsafe_names_rejected(name):                       # regression for config injection (audit case 3)
    with pytest.raises(ValidationError):
        _req(name=name)
    with pytest.raises(ValidationError):
        _req(subnet_requests=[{"name": name, "hosts": 5}])


def test_site_mapping_must_cover_every_subnet_once():
    with pytest.raises(ValidationError):
        _req(site_count=1, sites=[{"name": "S", "subnets": []}])
    with pytest.raises(ValidationError):
        _req(site_count=2, sites=[{"name": "S", "subnets": ["A"]}, {"name": "T", "subnets": ["A"]}])


def test_requested_copper_beyond_100m_raises_through_pipeline():   # regression for audit case 5
    with pytest.raises(PhysicalDistanceViolationError):
        analyze(_req(distance_m=120, requested_media="copper"))


def test_latency_budget_violation_raises():
    with pytest.raises(PhysicalDistanceViolationError):
        analyze(_req(distance_m=900_000, max_latency_ms=1, bandwidth_mbps=10000))


def test_address_exhaustion_through_pipeline():
    from app.engines.vlsm_engine import AddressSpaceExhaustedError
    with pytest.raises(AddressSpaceExhaustedError):
        analyze(_req(root_cidr="10.0.0.0/24", subnet_requests=[{"name": "A", "hosts": 200}, {"name": "B", "hosts": 200}]))


def test_short_endpoint_plan_warns():
    r = analyze(_req(endpoints=500))
    assert any("short by" in w for w in r["warnings"])


def test_presets_have_no_default_warnings(results):
    for k, r in results.items():
        assert not [w for w in r["warnings"] if "short by" in w], k
