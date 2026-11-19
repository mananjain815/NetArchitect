"""L3 routing-protocol selection (assignment rules) with RFC-backed rationale."""


def recommend_routing(subnet_count: int, autonomous_systems: int, site_count: int,
                      external_routing_domain: bool, building_count: int = 1) -> dict:
    """Rules, in priority order (CIC-307 section 3):
       1. external routing domain / >1 AS            -> eBGP at the boundary (+ OSPF inside the AS)
       2. multi-site (separate WAN/MAN sites)        -> Multi-Area OSPF
       3. single AS, single site, < 50 subnets       -> OSPF Area 0
       4. single AS, single site, >= 50 subnets      -> Multi-Area OSPF (LSDB scaling)
    Buildings inside one campus are NOT separate routing sites: they share Area 0."""
    if subnet_count < 1 or site_count < 1 or autonomous_systems < 1:
        raise ValueError("subnet_count, site_count and autonomous_systems must be >= 1.")

    if external_routing_domain or autonomous_systems > 1:
        protocol = "eBGP"
        rationale = (
            f"eBGP selected because the design crosses an autonomous-system boundary "
            f"({autonomous_systems} AS / external routing domain). BGP-4 (RFC 4271) carries policy "
            "(prefix-lists, aggregation) between independently administered domains and does not "
            "flood topology, so a failure in one AS does not trigger SPF runs in the other (routing "
            "domain isolation). Inside the corporate AS, multi-area OSPF (RFC 2328) remains the IGP, "
            "private ASNs are taken from RFC 6996 (64512-65534), and the border router advertises one "
            "summary instead of every subnet."
        )
    elif site_count > 1:
        protocol = "Multi-Area OSPF"
        rationale = (
            f"Multi-Area OSPF selected because the design spans {site_count} separate sites in a single "
            "AS. OSPF (RFC 2328) is link-state with fast convergence; giving each site its own area "
            "confines LSA flooding and SPF recalculation to that area, and the ABR can summarise each "
            f"site's supernet into Area 0 with one `area range` ({site_count - 1} remote areas around the "
            "Area 0 backbone)."
        )
    elif subnet_count < 50:
        protocol = "OSPF Area 0"
        extra = f" The {building_count} buildings share the same area." if building_count > 1 else ""
        rationale = (
            f"OSPF Area 0 selected because the design is one autonomous system at one site with "
            f"{subnet_count} subnets (< 50 threshold). Link-state OSPF (RFC 2328) converges faster than "
            "distance-vector protocols (it floods an LSA and runs SPF instead of waiting on timers/hold-"
            f"downs) and at this size a single LSDB is cheap, so extra areas would only add ABR complexity.{extra}"
        )
    else:
        protocol = "Multi-Area OSPF"
        rationale = (
            f"Multi-Area OSPF selected because the single-AS design has {subnet_count} subnets (>= 50): "
            "the Type-1/2 LSDB grows with subnet count, so areas bound flooding and SPF cost "
            "(RFC 2328 section 3)."
        )
    multi_area = protocol == "Multi-Area OSPF" or (protocol == "eBGP" and site_count > 1)
    return {"protocol": protocol, "rationale": rationale, "uses_ospf": True,
            "uses_bgp": protocol == "eBGP", "multi_area": multi_area}
