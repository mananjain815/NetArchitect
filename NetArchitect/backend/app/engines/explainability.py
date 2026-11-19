"""Builds the natural-language Architectural Rationale Log from the engine outputs."""
from app.engines.media_engine import fmt_distance


def build_report(request, media, routing, topology, vlsm, sites, configs, warnings) -> dict:
    d = []
    add = lambda area, decision, reason: d.append({"area": area, "decision": decision, "reason": reason})
    b, a = media["backbone"], media["access"]

    add("Physical media (access runs)", f"{a['medium']} - {a['transceiver']}", a["rationale"])
    add("Physical media (backbone / WAN)", f"{b['medium']} - {b['transceiver']}", b["rationale"])
    add("Transceiver", b["transceiver"],
        f"{b['rate_mbps'] // 1000}G is the smallest standard Ethernet rate >= the requested "
        f"{request.bandwidth_mbps} Mb/s; the optic is the shortest-reach one that still covers "
        f"{fmt_distance(request.distance_m)} and closes its optical budget.")
    for n in b["notes"] + a["notes"]:
        add("Engineering note", "Review", n)
    if b["propagation_delay_ms"]:
        extra = ""
        if request.max_latency_ms:
            extra = (f" The {request.max_latency_ms:g} ms budget leaves "
                     f"{round(request.max_latency_ms - b['propagation_delay_ms'], 3)} ms for queueing/serialisation, "
                     "which an LLQ priority class (20%) keeps small for voice/critical traffic.")
        add("Latency", f"{b['propagation_delay_ms']} ms one-way propagation",
            f"{fmt_distance(request.distance_m)} x 5 us/km = {b['propagation_delay_ms']} ms.{extra}")
    add("Topology tier", topology["tier"], topology["rationale"])
    add("Resiliency", request.resiliency, topology["resiliency_rationale"])
    add("Routing protocol", routing["protocol"], routing["rationale"])
    add("Addressing (VLSM)", f"{vlsm['root_network']} -> {len(vlsm['allocations'])} subnets", vlsm["rationale"])
    if len(sites) > 1:
        summ = ", ".join(f"{b['site']}={b['cidr']}" for b in vlsm["site_blocks"] if b["kind"] == "lan")
        add("Route summarisation", "One supernet per site",
            f"Because each site owns one aligned supernet ({summ}), the ABR/border router can advertise a "
            "single prefix per site (OSPF `area range`)" +
            (f" and the corporate AS advertises {configs['aggregate']} to the external AS via BGP." if configs["aggregate"] else "."))
    if request.wan_service == "evpl":
        add("WAN service", "EVPL (802.1Q EVC sub-interfaces)",
            "A point-to-point Ethernet Virtual Private Line gives each remote site a dedicated, "
            "latency-bounded EVC with a CE-VLAN tag, so OSPF runs over it as over a leased line.")
    elif request.wan_service == "ipsec":
        add("WAN service", "IPsec site-to-site VPN",
            "Sites are far apart / cross a provider or cloud boundary, so traffic between site supernets is "
            "protected with IKE + ESP (AES-256, SHA-256, DH14) using mirrored crypto ACLs.")
    add("Security", "Role-based inbound ACLs + hardened trunks",
        "Every SVI carries an extended ACL derived from the subnet role (user / admin / mgmt / iot / guest / "
        "server). Trunks use a fixed allowed-VLAN list, an unused native VLAN 999 and `nonegotiate` to stop VLAN "
        "hopping/DTP; access ports use PortFast + BPDU guard + port security.")
    return {"decisions": d, "warnings": warnings, "markdown": to_markdown(request, d, warnings)}


def to_markdown(request, decisions, warnings) -> str:
    out = [f"# Architectural Rationale Log - {request.name}", ""]
    for x in decisions:
        out += [f"## {x['area']}", f"**Decision:** {x['decision']}", "", x["reason"], ""]
    if warnings:
        out += ["## Warnings", ""] + [f"- {w}" for w in warnings] + [""]
    return "\n".join(out)
