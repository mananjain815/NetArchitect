# NetArchitect — Recommendation & Config Engine (CIC-307)

Explainable network-design engine: it takes a preset or custom scenario, runs rule engines for physical media,
topology, routing and bitwise VLSM addressing, explains every decision, and exports Cisco IOS configs.

## Run
```bash
cd backend
pip install -r requirements.txt
python -m pytest app/tests -q                 # 154 tests
uvicorn app.main:app --reload                 # API on :8000
python -m app.cli list                        # CLI
python -m app.cli analyze metro_man           # prints the rationale log
python -m app.cli export --out ../exports     # regenerate the 3 verification exports
cd ../frontend && npm install && npm run dev  # optional web UI on :5173
```

## What it does
| Area | Implementation |
|---|---|
| Presets & validation | 3 presets in `presets.py`; strict Pydantic model (`extra="forbid"`, safe names, CIDR checks); boundary errors `PhysicalDistanceViolationError`, `AddressSpaceExhaustedError` |
| L1 media | `media_engine.py` — Cat6a / OM4 / OS2 bands, bandwidth→Ethernet standard, transceiver by reach **and** optical budget, propagation delay, carrier-service flag |
| Topology | `topology_engine.py` — collapsed core vs three-tier, switch count and oversubscription math |
| L3 routing | `routing_engine.py` — OSPF Area 0 / Multi-Area OSPF / eBGP with RFC rationale |
| VLSM | `vlsm_engine.py` — bitwise allocator (flat + hierarchical per-site supernets for summarisation), wildcard masks, utilisation math |
| Configs | `config_generator.py` — per site router + L3 switch (SVIs, DHCP, RSTP, role-based extended ACLs applied to SVIs, OSPF), access switch, plus EVPL+QoS (MAN) or IPsec+eBGP+aggregate (WAN) |
| Verification | `acl_sim.py` evaluates generated ACLs with IOS semantics for packet-flow tests |
| AI audit | `ai_audit_log.md` |

## Layout
`backend/app/{engines,models,tests}` · `frontend/` · `exports/` (generated configs, rationale logs, cabling plans) · `docs/VERIFICATION.md`

## Honest limitations
* Configs are generated and syntactically self-consistent (unique IPs, matching trunks, mirrored crypto ACLs, tested), but
  have **not** been loaded into Packet Tracer / GNS3 by the generator — do that and fill in the lab table in the audit log.
* Optical constants are planning values; verify with the real optic datasheet.
* Topology is hub-and-spoke; one representative access switch is generated per hub site.
* Placeholder secrets (`CHANGE_ME_BEFORE_DEPLOY`) must be replaced.
