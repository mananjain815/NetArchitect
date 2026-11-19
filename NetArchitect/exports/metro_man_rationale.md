# Architectural Rationale Log - Metro MAN

## Physical media (access runs)
**Decision:** Cat6a - 1000BASE-T

Selected Cat6a because link distance (90 m) is within the 100 m twisted-pair limit of IEEE 802.3an; 1000BASE-T runs over Cat6a at up to 100 m at 1G.

## Physical media (backbone / WAN)
**Decision:** OS2 Single-Mode Fiber - 10GBASE-ER

Selected OS2 Single-Mode Fiber because link distance (22 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. 10GBASE-ER (1550 nm) reaches 40 km. Rejected smaller optics: 10GBASE-LR: reach 10 km < 22 km. Optical budget: 0.25 dB/km x 22 km = 5.5 dB fibre + 1.0 dB connectors + 1.1 dB splices = 7.6 dB total vs 10.9 dB transceiver budget -> 3.3 dB margin.

## Transceiver
**Decision:** 10GBASE-ER

10G is the smallest standard Ethernet rate >= the requested 10000 Mb/s; the optic is the shortest-reach one that still covers 22 km and closes its optical budget.

## Latency
**Decision:** 0.11 ms one-way propagation

22 km x 5 us/km = 0.11 ms. The 5 ms budget leaves 4.89 ms for queueing/serialisation, which an LLQ priority class (20%) keeps small for voice/critical traffic.

## Topology tier
**Decision:** Three-tier (access / distribution / core)

Three-tier selected because the design has 1 building(s), 3 site(s) and 450 endpoints: distribution blocks keep each building's / site's L2 domain and STP topology small and give a summarisation point toward the core. Sizing: ceil(450 / (48 ports x 80% fill)) = 12 access switches. Access oversubscription = 48 x 1G / (2 x 10G uplink) = 2.4:1 (within the common 20:1 access-to-distribution guideline).

## Resiliency
**Decision:** high

Redundant uplinks at every tier, dual-homed WAN/MAN links with a cost-based primary/backup path, and redundant core nodes.

## Routing protocol
**Decision:** Multi-Area OSPF

Multi-Area OSPF selected because the design spans 3 separate sites in a single AS. OSPF (RFC 2328) is link-state with fast convergence; giving each site its own area confines LSA flooding and SPF recalculation to that area, and the ABR can summarise each site's supernet into Area 0 with one `area range` (2 remote areas around the Area 0 backbone).

## Addressing (VLSM)
**Decision:** 10.20.0.0/16 -> 12 subnets

Hierarchical VLSM: each site gets one power-of-two supernet sized to the sum of its subnet blocks, supernets are placed largest-first on their own size boundary, then subnets are VLSM-allocated largest-first inside each supernet. HQ -> 10.20.0.0/23 (68.75% of block used). REMOTE_A -> 10.20.2.0/25 (100.0% of block used). REMOTE_B -> 10.20.2.128/25 (100.0% of block used). INFRA -> 10.20.3.0/27 (87.5% of block used). LAN hosts requested: 530 in 598 usable addresses (88.6% host efficiency). 800 of 65536 addresses of 10.20.0.0/16 are reserved (1.22%).

## Route summarisation
**Decision:** One supernet per site

Because each site owns one aligned supernet (HQ=10.20.0.0/23, REMOTE_A=10.20.2.0/25, REMOTE_B=10.20.2.128/25), the ABR/border router can advertise a single prefix per site (OSPF `area range`) and the corporate AS advertises 10.20.0.0/22 to the external AS via BGP.

## WAN service
**Decision:** EVPL (802.1Q EVC sub-interfaces)

A point-to-point Ethernet Virtual Private Line gives each remote site a dedicated, latency-bounded EVC with a CE-VLAN tag, so OSPF runs over it as over a leased line.

## Security
**Decision:** Role-based inbound ACLs + hardened trunks

Every SVI carries an extended ACL derived from the subnet role (user / admin / mgmt / iot / guest / server). Trunks use a fixed allowed-VLAN list, an unused native VLAN 999 and `nonegotiate` to stop VLAN hopping/DTP; access ports use PortFast + BPDU guard + port security.
