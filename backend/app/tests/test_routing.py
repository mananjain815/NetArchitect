from app.engines.routing_engine import recommend_routing


def test_single_as_small_network_uses_area_zero():
    result = recommend_routing(10, 1, 1, False)
    assert result["protocol"] == "OSPF Area 0"


def test_multi_site_uses_multi_area_ospf():
    result = recommend_routing(10, 1, 3, False)
    assert result["protocol"] == "Multi-Area OSPF"


def test_external_domain_uses_ebgp():
    result = recommend_routing(10, 2, 4, True)
    assert result["protocol"] == "eBGP"
