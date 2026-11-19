"""Single pipeline used by the API, the CLI and the tests."""
from app.engines.config_generator import generate_configs, plan_links, resolve_sites
from app.engines.explainability import build_report
from app.engines.media_engine import PhysicalDistanceViolationError, plan_media
from app.engines.parameter_engine import validate_parameters
from app.engines.routing_engine import recommend_routing
from app.engines.topology_engine import recommend_topology
from app.engines.vlsm_engine import allocate_hierarchical
from app.models.schemas import NetworkRequest


def analyze(request: NetworkRequest) -> dict:
    warnings = validate_parameters(request)
    media = plan_media(request.distance_m, request.access_distance_m, request.bandwidth_mbps,
                       request.access_bandwidth_mbps, request.requested_media)
    delay = media["backbone"]["propagation_delay_ms"]
    if request.max_latency_ms is not None and delay > request.max_latency_ms:
        raise PhysicalDistanceViolationError(
            f"One-way fibre propagation over {request.distance_m / 1000:g} km is {delay} ms, which already "
            f"exceeds the {request.max_latency_ms:g} ms latency budget (5 us/km): the budget cannot be met by QoS."
        )
    if media["backbone"]["requires_carrier_service"]:
        warnings.append("No single-span optic reaches the backbone distance: provision carrier service / DWDM "
                        "or regenerate; the generated configs assume a routed Ethernet hand-off.")
    for n in media["backbone"]["notes"] + media["access"]["notes"]:
        warnings.append(n)

    sites = resolve_sites(request)
    if request.site_count > 1 and not request.sites and not any("round-robin" in w for w in warnings):
        warnings.append("Subnets were split round-robin across sites.")
    n_user_subnets = len(request.subnet_requests)
    routing = recommend_routing(n_user_subnets, request.autonomous_systems, len(sites),
                                request.external_routing_domain, request.building_count)
    topology = recommend_topology(request.endpoints, len(sites), request.building_count, request.resiliency,
                                  request.access_bandwidth_mbps, media["backbone"]["rate_mbps"])
    infra = [{"name": L["name"], "hosts": 2} for L in plan_links(sites, request.resiliency)]
    vlsm = allocate_hierarchical(request.root_cidr, sites,
                                 [r.model_dump() for r in request.subnet_requests], infra)
    configs = generate_configs(request, sites, vlsm, routing, media, topology)
    report = build_report(request, media, routing, topology, vlsm, sites, configs, warnings)
    return {"input": request.model_dump(), "media": media["backbone"], "access_media": media["access"],
            "topology": topology, "routing": routing, "vlsm": vlsm, "sites": sites,
            "configs": configs, "report": report, "warnings": warnings}
