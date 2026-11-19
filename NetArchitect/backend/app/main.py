from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.analysis import analyze
from app.engines.media_engine import PhysicalDistanceViolationError
from app.engines.vlsm_engine import AddressSpaceExhaustedError
from app.models.schemas import NetworkRequest
from app.presets import PRESETS

app = FastAPI(title="NetArchitect API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/profiles")
def profiles():
    return {k: {"name": v["name"], "profile": k} for k, v in PRESETS.items()}


@app.get("/api/profiles/{profile}")
def profile(profile: str):
    if profile not in PRESETS:
        raise HTTPException(status_code=404, detail="Unknown profile.")
    return PRESETS[profile]


@app.post("/api/analyze")
def analyze_endpoint(request: NetworkRequest):
    try:
        return analyze(request)
    except PhysicalDistanceViolationError as exc:
        raise HTTPException(status_code=422, detail=f"PhysicalDistanceViolationError: {exc}")
    except AddressSpaceExhaustedError as exc:
        raise HTTPException(status_code=422, detail=f"AddressSpaceExhaustedError: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
