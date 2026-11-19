# AI Audit Log — NetArchitect (CIC-307)

**Student:** Manan Jain  **Project:** NetArchitect: Recommendation & Config Engine

Summary:

| # | Defect class | Where | Severity |
|---|---|---|---|
| 1 | Incorrect optical budget / transceiver left unselected | `media_engine.py` | High (link would not come up) |
| 2 | ACL never applied, wrong ACL type, not paste-ready | `config_generator.py` | High (no security enforced) |
| 3 | Unsanitised hostname lets a newline break the config | `config_generator.py` | Medium |
| 4 | Campus LAN gets Multi-Area OSPF instead of Area 0 | `routing_engine.py` | Medium (violates spec rule) |
| 5 | Copper-over-100 m error unreachable (field silently ignored) | `schemas.py` / `main.py` | Medium |

---

## Case 1 — Incorrect optical budget: "10GBASE-LR/ER (select to match reach)"

** prompt:** *"Write a Python function `recommend_media(distance_m)` for a network-design tool. Use the assignment rules: up to 100 m recommend Cat6a (10GBASE-T), 101-400 m recommend OM4 multimode (10GBASE-SR), above 400 m recommend OS2 single-mode (10GBASE-LR/ER). Return the medium, the transceiver and a short justification string."*

**Buggy AI code (original `media_engine.py`):**
```python
    else:
        medium = "OS2 Single-Mode Fiber"
        transceiver = "10GBASE-LR/ER (select to match reach)"
        rationale = (
            f"OS2 single-mode fiber is selected because the {distance_m:g}m run exceeds "
            "the assignment's 400m multimode-fiber band. Verify optical power budget and transceiver reach."
        )
```

**Reproduction (original code):**
```
22000  -> OS2 Single-Mode Fiber | 10GBASE-LR/ER (select to match reach)
100000 -> OS2 Single-Mode Fiber | 10GBASE-LR/ER (select to match reach)
```

**Technical analysis.** The code never selects an optic and never computes a budget; it hands the decision back to the
user. The two optics it names are not interchangeable (IEEE 802.3ae): 10GBASE-**LR** reaches 10 km at 1310 nm with a
~6.2 dB channel budget; 10GBASE-**ER** reaches 40 km at 1550 nm with ~10.9 dB. For the Metro MAN's 22 km link:

| Optic | Reach | Link loss for 22 km | Budget | Result |
|---|---|---|---|---|
| 10GBASE-LR (1310 nm, 0.40 dB/km) | 10 km | 8.8 fibre + 1.0 connectors + 1.1 splices = **10.9 dB** | 6.2 dB | **FAIL by 4.7 dB** and 12 km past its reach |
| 10GBASE-ER (1550 nm, 0.25 dB/km) | 40 km | 5.5 + 1.0 + 1.1 = **7.6 dB** | 10.9 dB | PASS, 3.3 dB margin |

Choosing LR (the first name in the string) would give a link that never comes up: the receiver sees less power than its
sensitivity, so `show interfaces` stays down/down and **no packet flows at all**. For the Global WAN's 100 km the
original also says "LR/ER", but *no* single-span 10G optic reaches 100 km (ZR tops out at ~80 km); the correct answer is a
carrier/DWDM/regenerated path, which the original never flags.

**Fix (`media_engine.py`).** A transceiver table (standard, medium, reach, wavelength, budget) per Ethernet rate;
`_pick_optic()` picks the *shortest-reach optic that satisfies both reach and `loss <= budget`*, records why smaller optics
were rejected, and flags `requires_carrier_service` when none can. The rationale prints the arithmetic.

**Verification.** `pytest app/tests/test_media_engine.py`:
`test_22km_uses_er_not_lr_and_matches_spec_wording`, `test_optical_budget_arithmetic_22km_er` (5.5 / 1.0 / 1.1 / 7.6 dB,
3.3 dB margin), `test_er_fails_budget_near_40km_so_zr_selected`, `test_beyond_single_span_flags_carrier_service`.
New output for 22 km: *"Selected OS2 Single-Mode Fiber because link distance (22 km) exceeds the 400 m attenuation/
dispersion limit of OM4 Multimode Fiber. 10GBASE-ER (1550 nm) reaches 40 km. Rejected smaller optics: 10GBASE-LR: reach
10 km < 22 km. Optical budget: … = 7.6 dB total vs 10.9 dB transceiver budget -> 3.3 dB margin."*

Caveat: attenuation and budget figures are planning values from IEEE 802.3 / TIA-568; the code says so and the real
datasheet of the purchased optic must be checked.

---

## Case 2 — ACL that filters nothing (and is not paste-ready)

** prompt:** *"Write a Python function that generates Cisco IOS configuration for a switch, a router and ACLs from a list of allocated subnets. Create a VLAN per subnet, router sub-interfaces, a trunk port, and an ACL that allows the allocated subnets. Output copy-paste ready configs."*

**Buggy AI code (original `config_generator.py`):**
```python
    acl = [
        "!",
        "! Example source allow-list only; adapt to the actual security policy.",
        "ip access-list standard NETARCHITECT-SUBNET-SOURCES",
    ]
    # ... later: " permit <network> <wildcard>" for every subnet, nothing else
```

**Reproduction (original code, Campus LAN preset):**
```
access-group applied anywhere: False
SVIs: False | router ospf: False | rapid-pvst: False
first lines of acl_config: ['!', '! Example source allow-list only; ...', 'ip access-list standard NETARCHITECT-SUBNET-SOURCES']
```

**Technical analysis — four independent faults.**
1. *Never bound.* No `ip access-group` exists in any generated file, so the ACL is a dead object; IOS only filters when an
   ACL is attached to an interface.
2. *Wrong type.* A **standard** ACL matches the source address only. It cannot express "students may reach the
   server VLAN on 80/443 but not 22", because it has no destination and no port.
3. *Semantically empty.* It permits every internal subnet as a source, then implicit-deny; even if attached it would
   permit all internal sources to all destinations.
4. *Not paste-ready.* The file starts with `!` / `ip access-list` and no `enable` / `configure terminal`, so pasted at a
   user-exec prompt every line errors. Also: the spec requires **SVIs** — the starter has none (no `interface Vlan…`,
   no `ip routing`), no routing process and no RSTP either.

**Packet-flow analysis (student 10.10.0.5 -> server 10.10.8.5, TCP/22 SSH):**

| Version | Hop where ACL is evaluated | Verdict |
|---|---|---|
| Original | none — ACL not applied on `Vlan10` ingress | **forwarded** (SSH reaches the server) |
| Fixed | `Vlan10` inbound `ACL-STUDENTS-IN`: lines 80/443/53/ICMP-echo permitted to the server subnet, then `deny ip <students> <server subnet>` | **denied** |
| Fixed, TCP/443 | same ACL, line `permit tcp <students> <servers> eq 443` | **permitted** |
| Fixed, reply (server 443 -> student, ACK set) | `Vlan50` inbound `ACL-SERVERS-IN`: `permit tcp <servers> any established` | **permitted** |
| Fixed, spoofed source 10.10.4.9 on the student VLAN | no line matches that source -> `deny ip any any` | **denied** |

**Fix.** `build_acls()` derives a role (user / admin / mgmt / iot / guest / server) from each subnet and emits a named
**extended** ACL with DHCP, protected-subnet rules, anti-spoofing through source-bound permits and an explicit final
deny. Each ACL is applied with `ip access-group … in` on its SVI. Every file now starts `enable` / `configure terminal`
and ends `end` / `write memory`. SVIs, `ip routing`, `spanning-tree mode rapid-pvst`, DHCP pools, OSPF (and BGP / IPsec /
EVPL / QoS per profile) are generated.

**Verification.** `app/engines/acl_sim.py` evaluates the generated ACL text with IOS semantics (first match, implicit
deny). `pytest app/tests/test_configs_and_packet_flow.py` — `test_student_to_server_https_permitted_ssh_denied`,
`test_student_cannot_reach_admin_or_mgmt_but_can_reach_internet`, `test_spoofed_source_is_dropped`,
`test_iot_is_quarantined_from_internal_networks`, `test_servers_reply_but_cannot_initiate`,
`test_every_file_is_paste_ready`.

---

## Case 3 — Unsanitised network name inside `hostname`

** prompt:** *"In the config generator, name the router and switch from the network name entered by the user, e.g. `hostname <network name>-Router`, keeping it short enough for a hostname."*

**Buggy AI code (original):**
```python
f"hostname {network_name[:25].replace(' ', '-')}-Router",
```
`network_name` was a free-text API field with no character restriction.

**Reproduction (original, name = `"X\nusername evil privilege 15 secret pw"`):**
```
enable
configure terminal
hostname X
username-evil-privilege-Router
```

**Technical analysis.** The generator turns one user string into *two* config lines. The truncation to 25 characters and the
space-to-dash replacement happened to mangle my test payload into the bogus line `username-evil-privilege-Router`
(IOS would reject it), so in this exact payload it is a malformed config rather than a privilege escalation — but the
newline still escapes the `hostname` line, and any short, space-free payload would survive the mangling. Safety was
accidental, not designed. Identifiers also contained characters IOS does not allow in hostnames.

**Fix.** (a) Pydantic validators on `name`, subnet names and site names accept only `[A-Za-z0-9 _.-]` and reject
control characters (HTTP 422). (b) Independently, `safe()` / `hostname()` in the generator strip everything outside
`[A-Za-z0-9_.-]` and hostnames use only letters, digits and hyphens. (c) `extra="forbid"` so unknown fields error.

**Verification.** `test_unsafe_names_rejected` (newline, `;`, CRLF, `../`, empty), `test_api_rejects_injection_and_unknown_fields`,
`test_hostnames_and_secrets_safe` (exactly one `hostname` line per file, regex `[A-Za-z0-9-]+`).

---

## Case 4 — Campus LAN routed with Multi-Area OSPF

** prompt:** *"Write `recommend_routing(subnet_count, autonomous_systems, site_count, external_routing_domain)`: for a single AS with fewer than 50 subnets choose OSPF Area 0; for multi-site or multi-cloud choose Multi-Area OSPF or eBGP; include a justification."*

**Buggy AI code (original `routing_engine.py`):** `elif site_count > 1:` -> "Multi-Area OSPF", evaluated *before* the
subnet-count rule, with the Campus preset passing `site_count = 3` (its 3 **buildings**).

**Reproduction (original):** `Campus preset site_count=3 -> Multi-Area OSPF`.

**Analysis.** The assignment gives the Campus LAN *single-area OSPF* and the rule "single AS, < 50 subnets -> OSPF
Area 0". Buildings joined by a routed campus backbone are one routing domain, not separate sites; treating them as sites
violates the spec and would need an ABR and area design for 6 subnets. The original tests only passed `site_count=1`, so
the suite could not see it.

**Fix.** The model separates `site_count` (WAN/MAN sites) from `building_count` (campus buildings). Rule order is now
external/AS>1 -> eBGP, sites>1 -> Multi-Area OSPF, <50 subnets -> Area 0, otherwise Multi-Area. All devices of the Campus
preset sit in `area 0`.

**Verification.** `test_campus_buildings_do_not_force_multi_area`, `test_49_subnets_single_site_is_area0_and_50_is_multi_area`,
`test_campus_uses_single_area_ospf_rstp_and_svis` (asserts `area 0` present and `area 1` absent in the generated switch config).

---

## Case 5 — "Copper over 100 m" error that can never fire

** prompt:** *"Write the FastAPI `/api/analyze` endpoint that validates the network request, calls the media, routing, VLSM and config engines, and returns the results; raise PhysicalDistanceViolationError when copper is requested over 100 m."*

**Buggy AI code:** `recommend_media()` has a branch that raises `PhysicalDistanceViolationError`, but `main.py` calls
`recommend_media(request.distance_m)` and the request model has no `requested_media` field.

**Reproduction (original):** POST the Campus preset with `distance_m=120, requested_media="copper"` ->
`200 OK`, medium `OM4 Multimode Fiber`. The unknown field was silently dropped, so the mandatory boundary error was
unreachable from the API and UI.

**Fix.** Added `requested_media` (`auto|copper|om4|os2`) to the request, passed it to the engine, set
`extra="forbid"` on every model, and map the exception to HTTP 422 with its attenuation explanation. The same pass fixed
two neighbours: bandwidth was ignored by the media engine (Cat6a cannot carry >10 Gb/s) and `access_distance_m` is now a
separate access-layer link.

**Verification.** `test_copper_over_100m_raises_with_attenuation_warning`, `test_copper_exactly_100m_is_ok`,
`test_requested_copper_beyond_100m_raises_through_pipeline`, `test_api_returns_physical_violation_for_copper_120m`.

---

## Lab confirmation (complete after loading the exports)

Python tests prove the logic; the spec also asks for Packet Tracer / GNS3 validation. After building the topology from
`exports/<profile>_cabling.md` and pasting `exports/<profile>/*.cfg`, record:

| Check | Command | Expected | Your result / screenshot |
|---|---|---|---|
| Campus: ACL blocks SSH, allows HTTPS | student PC -> server: `ssh`, browser to :443 | SSH fails, HTTPS works | |
| Campus: hit counters | `show access-lists ACL-STUDENTS-IN` | matches on `deny ip …` after SSH attempt | |
| Campus: single-area OSPF | `show ip ospf neighbor`, `show ip route ospf` | RTR adjacency FULL, all in area 0 | |
| Campus: RSTP / trunk | `show spanning-tree summary`, `show interfaces trunk` | rapid-pvst, native 999, allowed list | |
| Metro: summaries / failover | `show ip route ospf`, shut primary WAN link, `ping` | `O IA` summaries; traffic moves to cost-100 link | |
| WAN: IPsec / BGP | `show crypto isakmp sa`, `show ip bgp summary` | QM_IDLE / Established | |
