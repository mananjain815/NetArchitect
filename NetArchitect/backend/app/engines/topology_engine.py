"""Topology-tier recommendation (collapsed core vs three-tier) with sizing arithmetic."""
import math

ACCESS_PORTS = 48
TARGET_FILL = 0.80


def recommend_topology(endpoints: int, site_count: int, building_count: int, resiliency: str,
                       access_bandwidth_mbps: int, uplink_mbps: int) -> dict:
    three_tier = building_count > 1 or site_count > 1 or endpoints > 500
    access_switches = math.ceil(endpoints / (ACCESS_PORTS * TARGET_FILL))
    dist_per_block = 2 if resiliency != "low" else 1
    dist_blocks = max(building_count, site_count if site_count > 1 else 1)
    core_nodes = (2 if resiliency == "high" else 1) if three_tier else 0
    uplinks = 2 if resiliency != "low" else 1
    down_gbps = ACCESS_PORTS * access_bandwidth_mbps / 1000
    up_gbps = uplinks * uplink_mbps / 1000
    ratio = round(down_gbps / up_gbps, 1)

    if three_tier:
        tier = "Three-tier (access / distribution / core)"
        why = (
            f"Three-tier selected because the design has {building_count} building(s), {site_count} site(s) "
            f"and {endpoints} endpoints: distribution blocks keep each building's / site's L2 domain and "
            "STP topology small and give a summarisation point toward the core."
        )
    else:
        tier = "Collapsed core (two-tier)"
        why = (
            f"Collapsed core selected because a single building with {endpoints} endpoints (<= 500) does "
            "not justify a separate distribution layer; one routed core/distribution pair terminates all VLANs."
        )
    why += (
        f" Sizing: ceil({endpoints} / ({ACCESS_PORTS} ports x {int(TARGET_FILL * 100)}% fill)) = "
        f"{access_switches} access switches. Access oversubscription = {ACCESS_PORTS} x "
        f"{access_bandwidth_mbps / 1000:g}G / ({uplinks} x {uplink_mbps / 1000:g}G uplink) = {ratio}:1"
        + (" (within the common 20:1 access-to-distribution guideline)." if ratio <= 20
           else " (EXCEEDS the common 20:1 guideline - add uplinks or raise uplink speed).")
    )
    res = {
        "low": "Single path at each tier (no redundancy requested).",
        "medium": "Dual uplinks per access switch (LACP EtherChannel) with RSTP as the loop-prevention backstop; single core node.",
        "high": "Redundant uplinks at every tier, dual-homed WAN/MAN links with a cost-based primary/backup path, and redundant core nodes.",
    }[resiliency]
    return {
        "tier": tier, "three_tier": three_tier, "access_switches": access_switches,
        "distribution_blocks": dist_blocks if three_tier else 0,
        "distribution_nodes_per_block": dist_per_block if three_tier else 0,
        "core_nodes": core_nodes, "uplinks_per_access_switch": uplinks,
        "oversubscription_ratio": ratio, "oversubscription_ok": ratio <= 20,
        "rationale": why, "resiliency_rationale": res,
    }
