import pytest
from app.engines.media_engine import recommend_media, PhysicalDistanceViolationError


def test_cat6a_at_100m():
    assert recommend_media(100)["medium"] == "Cat6a"


def test_om4_at_101m():
    assert recommend_media(101)["medium"] == "OM4 Multimode Fiber"


def test_os2_above_400m():
    assert recommend_media(401)["medium"] == "OS2 Single-Mode Fiber"


def test_copper_over_100m_raises():
    with pytest.raises(PhysicalDistanceViolationError):
        recommend_media(120, requested_media="copper")


def test_negative_distance_raises():
    with pytest.raises(ValueError):
        recommend_media(-1)
