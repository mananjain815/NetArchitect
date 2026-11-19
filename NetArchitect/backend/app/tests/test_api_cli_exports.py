import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cli import export_all, main
from app.main import app
from app.presets import PRESETS

client = TestClient(app)
REPO_EXPORTS = Path(__file__).resolve().parents[3] / "exports"


def test_health_and_profiles():
    assert client.get("/api/health").json() == {"status": "ok"}
    assert set(client.get("/api/profiles").json()) == {"campus_lan", "metro_man", "global_wan"}
    assert client.get("/api/profiles/nope").status_code == 404


@pytest.mark.parametrize("key", list(PRESETS))
def test_analyze_each_preset(key):
    r = client.post("/api/analyze", json=PRESETS[key])
    assert r.status_code == 200
    body = r.json()
    assert body["configs"]["devices"] and body["report"]["decisions"] and body["warnings"] is not None


def test_api_returns_physical_violation_for_copper_120m():
    p = dict(PRESETS["campus_lan"], distance_m=120, requested_media="copper")
    r = client.post("/api/analyze", json=p)
    assert r.status_code == 422 and "PhysicalDistanceViolationError" in r.json()["detail"]


def test_api_rejects_injection_and_unknown_fields():
    p = dict(PRESETS["campus_lan"], name="X\nusername evil privilege 15 secret pw")
    assert client.post("/api/analyze", json=p).status_code == 422
    assert client.post("/api/analyze", json=dict(PRESETS["campus_lan"], bogus=1)).status_code == 422


def test_api_address_exhaustion_is_422():
    p = dict(PRESETS["campus_lan"], root_cidr="10.10.0.0/22")
    r = client.post("/api/analyze", json=p)
    assert r.status_code == 422 and "AddressSpaceExhaustedError" in r.json()["detail"]


def test_cli_list_and_error_exit_code(capsys, tmp_path):
    assert main(["list"]) == 0 and "campus_lan" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(PRESETS["campus_lan"], distance_m=120, requested_media="copper")))
    assert main(["analyze", str(bad)]) == 2


def test_committed_exports_match_generator(tmp_path):
    """The files in /exports must be exactly what the engine generates today."""
    export_all(tmp_path)
    for key in PRESETS:
        assert (REPO_EXPORTS / f"{key}_full_config.txt").exists(), key
        assert (REPO_EXPORTS / f"{key}_full_config.txt").read_text() == (tmp_path / f"{key}_full_config.txt").read_text()
