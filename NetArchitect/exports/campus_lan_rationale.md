# Architectural Rationale Log - Campus LAN

## Physical media (access runs)
**Decision:** Cat6a - 1000BASE-T

Selected Cat6a because link distance (90 m) is within the 100 m twisted-pair limit of IEEE 802.3an; 1000BASE-T runs over Cat6a at up to 100 m at 1G.

## Physical media (backbone / WAN)
**Decision:** OM4 Multimode Fiber - 10GBASE-SR

Selected OM4 Multimode Fiber because link distance (350 m) exceeds the 100 m copper limit and stays inside the 400 m OM4 reach of 10GBASE-SR (850 nm VCSEL, IEEE 802.3ae); beyond 400 m modal dispersion and attenuation at 850 nm close the eye. Optical budget: 3.5 dB/km x 0.35 km = 1.22 dB fibre + 1.0 dB connectors = 2.22 dB total vs 2.9 dB transceiver budget -> 0.68 dB margin.

## Transceiver
**Decision:** 10GBASE-SR

10G is the smallest standard Ethernet rate >= the requested 10000 Mb/s; the optic is the shortest-reach one that still covers 350 m and closes its optical budget.

## Engineering note
**Decision:** Review

Optical margin is thin (0.68 dB); add attenuation headroom or choose a longer-reach optic.

## Latency
**Decision:** 0.0017 ms one-way propagation

350 m x 5 us/km = 0.0017 ms.

## Topology tier
**Decision:** Three-tier (access / distribution / core)

Three-tier selected because the design has 3 building(s), 1 site(s) and 1600 endpoints: distribution blocks keep each building's / site's L2 domain and STP topology small and give a summarisation point toward the core. Sizing: ceil(1600 / (48 ports x 80% fill)) = 42 access switches. Access oversubscription = 48 x 1G / (2 x 10G uplink) = 2.4:1 (within the common 20:1 access-to-distribution guideline).

## Resiliency
**Decision:** medium

Dual uplinks per access switch (LACP EtherChannel) with RSTP as the loop-prevention backstop; single core node.

## Routing protocol
**Decision:** OSPF Area 0

OSPF Area 0 selected because the design is one autonomous system at one site with 6 subnets (< 50 threshold). Link-state OSPF (RFC 2328) converges faster than distance-vector protocols (it floods an LSA and runs SPF instead of waiting on timers/hold-downs) and at this size a single LSDB is cheap, so extra areas would only add ABR complexity. The 3 buildings share the same area.

## Addressing (VLSM)
**Decision:** 10.10.0.0/16 -> 7 subnets

Hierarchical VLSM: each site gets one power-of-two supernet sized to the sum of its subnet blocks, supernets are placed largest-first on their own size boundary, then subnets are VLSM-allocated largest-first inside each supernet. CAMPUS -> 10.10.0.0/20 (54.69% of block used). INFRA -> 10.10.16.0/30 (100.0% of block used). LAN hosts requested: 1650 in 2228 usable addresses (74.1% host efficiency). 4100 of 65536 addresses of 10.10.0.0/16 are reserved (6.26%).

## Security
**Decision:** Role-based inbound ACLs + hardened trunks

Every SVI carries an extended ACL derived from the subnet role (user / admin / mgmt / iot / guest / server). Trunks use a fixed allowed-VLAN list, an unused native VLAN 999 and `nonegotiate` to stop VLAN hopping/DTP; access ports use PortFast + BPDU guard + port security.

## Warnings

- Optical margin is thin (0.68 dB); add attenuation headroom or choose a longer-reach optic.
