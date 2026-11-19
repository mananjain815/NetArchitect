# Architectural Rationale Log - Global WAN

## Physical media (access runs)
**Decision:** Cat6a - 1000BASE-T

Selected Cat6a because link distance (90 m) is within the 100 m twisted-pair limit of IEEE 802.3an; 1000BASE-T runs over Cat6a at up to 100 m at 1G.

## Physical media (backbone / WAN)
**Decision:** OS2 Single-Mode Fiber - No single-span optic reaches this distance

Selected OS2 Single-Mode Fiber because link distance (100 km) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber. No single-span 10G optic reaches 100 km (longest is ZR/ER-class at 40-80 km): provision the path as carrier-provided service, DWDM with amplification, or regenerate.

## Transceiver
**Decision:** No single-span optic reaches this distance

10G is the smallest standard Ethernet rate >= the requested 10000 Mb/s; the optic is the shortest-reach one that still covers 100 km and closes its optical budget.

## Latency
**Decision:** 0.5 ms one-way propagation

100 km x 5 us/km = 0.5 ms.

## Topology tier
**Decision:** Three-tier (access / distribution / core)

Three-tier selected because the design has 1 building(s), 5 site(s) and 2000 endpoints: distribution blocks keep each building's / site's L2 domain and STP topology small and give a summarisation point toward the core. Sizing: ceil(2000 / (48 ports x 80% fill)) = 53 access switches. Access oversubscription = 48 x 1G / (2 x 10G uplink) = 2.4:1 (within the common 20:1 access-to-distribution guideline).

## Resiliency
**Decision:** high

Redundant uplinks at every tier, dual-homed WAN/MAN links with a cost-based primary/backup path, and redundant core nodes.

## Routing protocol
**Decision:** eBGP

eBGP selected because the design crosses an autonomous-system boundary (2 AS / external routing domain). BGP-4 (RFC 4271) carries policy (prefix-lists, aggregation) between independently administered domains and does not flood topology, so a failure in one AS does not trigger SPF runs in the other (routing domain isolation). Inside the corporate AS, multi-area OSPF (RFC 2328) remains the IGP, private ASNs are taken from RFC 6996 (64512-65534), and the border router advertises one summary instead of every subnet.

## Addressing (VLSM)
**Decision:** 10.30.0.0/16 -> 17 subnets

Hierarchical VLSM: each site gets one power-of-two supernet sized to the sum of its subnet blocks, supernets are placed largest-first on their own size boundary, then subnets are VLSM-allocated largest-first inside each supernet. CITY_1 -> 10.30.0.0/23 (100.0% of block used). CITY_2 -> 10.30.2.0/23 (100.0% of block used). CITY_3 -> 10.30.4.0/23 (100.0% of block used). CITY_4 -> 10.30.6.0/23 (100.0% of block used). CLOUD_VPC -> 10.30.8.0/25 (100.0% of block used). INFRA -> 10.30.8.128/26 (75.0% of block used). LAN hosts requested: 2000 in 2166 usable addresses (92.3% host efficiency). 2240 of 65536 addresses of 10.30.0.0/16 are reserved (3.42%).

## Route summarisation
**Decision:** One supernet per site

Because each site owns one aligned supernet (CITY_1=10.30.0.0/23, CITY_2=10.30.2.0/23, CITY_3=10.30.4.0/23, CITY_4=10.30.6.0/23, CLOUD_VPC=10.30.8.0/25), the ABR/border router can advertise a single prefix per site (OSPF `area range`) and the corporate AS advertises 10.30.0.0/21 to the external AS via BGP.

## WAN service
**Decision:** IPsec site-to-site VPN

Sites are far apart / cross a provider or cloud boundary, so traffic between site supernets is protected with IKE + ESP (AES-256, SHA-256, DH14) using mirrored crypto ACLs.

## Security
**Decision:** Role-based inbound ACLs + hardened trunks

Every SVI carries an extended ACL derived from the subnet role (user / admin / mgmt / iot / guest / server). Trunks use a fixed allowed-VLAN list, an unused native VLAN 999 and `nonegotiate` to stop VLAN hopping/DTP; access ports use PortFast + BPDU guard + port security.

## Warnings

- No single-span optic reaches the backbone distance: provision carrier service / DWDM or regenerate; the generated configs assume a routed Ethernet hand-off.
