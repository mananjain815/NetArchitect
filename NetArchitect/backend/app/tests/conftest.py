import pytest

from app.analysis import analyze
from app.models.schemas import NetworkRequest
from app.presets import PRESETS


@pytest.fixture(scope="session")
def results():
    return {k: analyze(NetworkRequest(**v)) for k, v in PRESETS.items()}
