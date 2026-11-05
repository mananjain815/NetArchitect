# NetArchitect

NetArchitect is a Computer Networks mini-project for CIC-307. It accepts preset or custom enterprise network parameters and generates physical-media recommendations, VLSM allocations, routing recommendations, Cisco IOS configuration templates and explainable decision notes.

## Stack

- Backend: Python, FastAPI, Pydantic
- Frontend: React, Vite, CSS
- Tests: pytest
- Verification target: Cisco Packet Tracer or GNS3

## Requirements

- Python 3.10+
- Node.js 18+
- npm

## Run the backend

Open a terminal in the project root:

```bash
cd backend
python -m venv .venv
```

Activate the environment:

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install and run:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend:
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

## Run the frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually http://localhost:5173.

## Run tests

From the project root:

```bash
cd backend
pip install -r requirements.txt
python -m pytest app/tests -v
```

## Current implementation

- Three presets: Campus LAN, Metro MAN and Global WAN
- Custom network input
- Parameter validation and warnings
- Assignment-based Cat6a / OM4 / OS2 distance rules
- Copper distance boundary error
- IPv4 VLSM allocation, wildcard masks, gateways and broadcast addresses
- Routing recommendations for OSPF Area 0, Multi-Area OSPF and eBGP
- Router, switch and ACL configuration templates
- Natural-language architecture rationale
- Automated tests for core boundaries and API

## Important engineering limitations to resolve before final submission

1. The assignment's media table says 101–400m -> OM4 and >400m -> OS2. The narrative example's 22km comparison is consistent with OS2, but its wording should not be interpreted as a separate rule. This project follows the table.
2. The media recommendation is a simplified decision rule. A real design must check exact Ethernet standard, transceiver reach, connector/splice losses and optical power budget.
3. The generated IOS files are starter templates, not production-ready configurations. Verify device interface names, VLAN design, routing adjacencies, spanning tree, ACL policy and end-to-end reachability in Packet Tracer/GNS3.
4. The preset host requests are practical starting allocations and may not represent every endpoint in the scenario. Review and adjust them with your instructor/team.
5. The routing recommendation is a simplified rule engine based on the assignment conditions; a full design requires topology, area boundaries, AS numbers and routing policies.
6. The current configuration generator uses a simple router-on-a-stick template. It does not yet model redundant links, dual-homed failover, EVPL, QoS, IPsec VPN, BGP neighbors or full multi-area OSPF configuration.

## Repository layout

```text
backend/
  app/
    engines/
    models/
    tests/
frontend/
  src/
presets/
exports/
docs/
ai_audit_log.md
```

## Submission checklist

- [ ] Run all tests and record the result
- [ ] Analyze all three presets
- [ ] Export one router, switch and ACL configuration set per profile
- [ ] Import/verify the configurations in Packet Tracer or GNS3
- [ ] Capture screenshots or verification evidence
- [ ] Complete `ai_audit_log.md` with two genuine AI-generated defects, diagnosis and fixes
- [ ] Update this README with actual test and simulation results
