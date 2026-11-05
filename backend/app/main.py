from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import NetworkRequest
from app.presets import PRESETS
from app.engines.parameter_engine import validate_parameters
from app.engines.media_engine import recommend_media, PhysicalDistanceViolationError
from app.engines.vlsm_engine import allocate_vlsm
from app.engines.routing_engine import recommend_routing
from app.engines.config_generator import generate_cisco_configs
from app.engines.explainability import build_architecture_report

app = FastAPI(
    title="NetArchitect API",
    description="Algorithmic network planning and explainable configuration engine.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "NetArchitect API"}


@app.get("/api/profiles")
def list_profiles():
    return [
        {"id": key, "name": value["name"], "endpoints": value["endpoints"],
         "distance_m": value["distance_m"]}
        for key, value in PRESETS.items()
    ]


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: str):
    if profile_id not in PRESETS:
        raise HTTPException(status_code=404, detail="Unknown network profile.")
    return PRESETS[profile_id]


@app.post("/api/analyze")
def analyze_network(request: NetworkRequest):
    warnings = validate_parameters(request)

    try:
        media = recommend_media(request.distance_m)
        vlsm = allocate_vlsm(
            request.root_cidr,
            [item.model_dump() for item in request.subnet_requests],
        )
        routing = recommend_routing(
            subnet_count=len(vlsm["allocations"]),
            autonomous_systems=request.autonomous_systems,
            site_count=request.site_count,
            external_routing_domain=request.external_routing_domain,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    configs = generate_cisco_configs(request.name, vlsm["allocations"])
    report = build_architecture_report(media, routing, vlsm, warnings)

    return {
        "network": {
            "name": request.name,
            "profile": request.profile,
            "endpoints": request.endpoints,
            "distance_m": request.distance_m,
            "site_count": request.site_count,
            "root_cidr": request.root_cidr,
        },
        "media": media,
        "routing": routing,
        "vlsm": vlsm,
        "configs": configs,
        "architecture_report": report,
        "warnings": warnings,
    }
