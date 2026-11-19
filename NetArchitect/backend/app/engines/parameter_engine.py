from app.models.schemas import NetworkRequest


def validate_parameters(data: NetworkRequest) -> list[str]:
    """Non-fatal engineering warnings after schema validation (fatal conditions raise elsewhere)."""
    w: list[str] = []
    total_hosts = sum(i.hosts for i in data.subnet_requests)
    if data.endpoints > total_hosts:
        w.append(
            f"Subnet requests provide {total_hosts} hosts but {data.endpoints} endpoints are declared: "
            "address plan is short by {0}.".format(data.endpoints - total_hosts)
        )
    if data.resiliency == "high" and data.site_count < 2 and data.building_count < 2:
        w.append("High resiliency requested for a single site/building: add a second path or device pair.")
    if data.site_count > 1 and not data.sites:
        w.append("No site->subnet mapping supplied: subnets were split round-robin across sites. "
                 "Supply 'sites' for a meaningful hierarchical plan.")
    if data.autonomous_systems > 1 and not data.external_routing_domain and data.site_count == 1:
        w.append("Multiple ASNs on a single site is unusual; confirm the external routing domain.")
    if data.wan_service == "ipsec" and data.distance_m < 1000:
        w.append("IPsec WAN service selected for a short (<1 km) link; private fibre is usually cheaper.")
    if data.requested_media == "auto" and data.access_distance_m > 100:
        w.append(f"Access run of {data.access_distance_m:g} m exceeds 100 m copper: fibre-to-the-desk or an "
                 "intermediate closet is required.")
    if data.endpoints / max(1, data.site_count * data.building_count) > 1000:
        w.append("More than 1,000 endpoints per building/site: consider splitting broadcast domains.")
    return w
