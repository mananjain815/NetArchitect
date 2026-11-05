from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_campus_preset_analyzes():
    profile = client.get("/api/profiles/campus_lan").json()
    response = client.post("/api/analyze", json=profile)
    assert response.status_code == 200
    data = response.json()
    assert data["vlsm"]["allocations"]
    assert data["architecture_report"]
    assert "router_config" in data["configs"]
