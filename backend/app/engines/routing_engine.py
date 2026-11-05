def recommend_routing(
    subnet_count: int,
    autonomous_systems: int,
    site_count: int,
    external_routing_domain: bool,
) -> dict:
    if external_routing_domain or autonomous_systems > 1:
        protocol = "eBGP"
        rationale = (
            "eBGP is recommended because the design crosses an external routing-domain/autonomous-system "
            "boundary. It supports policy-based exchange between separate routing domains."
        )
    elif site_count > 1:
        protocol = "Multi-Area OSPF"
        rationale = (
            "Multi-Area OSPF is recommended for this multi-site design within one autonomous system, "
            "allowing the routing domain to be divided into areas."
        )
    elif subnet_count < 50:
        protocol = "OSPF Area 0"
        rationale = (
            f"OSPF Area 0 is selected because the design has one autonomous system and "
            f"{subnet_count} subnets, below the assignment's 50-subnet threshold."
        )
    else:
        protocol = "Multi-Area OSPF"
        rationale = (
            f"Multi-Area OSPF is recommended because the design has {subnet_count} subnets; "
            "area hierarchy can help control routing information."
        )
    return {"protocol": protocol, "rationale": rationale}
