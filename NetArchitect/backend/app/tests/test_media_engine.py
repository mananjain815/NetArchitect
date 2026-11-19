import pytest

from app.engines.media_engine import PhysicalDistanceViolationError, recommend_media, snap_rate


@pytest.mark.parametrize("d,medium", [(1, "Cat6a"), (100, "Cat6a"), (100.01, "OM4 Multimode Fiber"),
                                      (400, "OM4 Multimode Fiber"), (400.01, "OS2 Single-Mode Fiber")])
def test_distance_band_boundaries(d, medium):
    assert recommend_media(d, "auto", 1000)["medium"] == medium


def test_copper_over_100m_raises_with_attenuation_warning():
    with pytest.raises(PhysicalDistanceViolationError) as e:
        recommend_media(101, "copper", 1000)
    assert "100 m" in str(e.value) and "crosstalk" in str(e.value)


def test_copper_exactly_100m_is_ok():
    assert recommend_media(100, "copper", 10000)["transceiver"] == "10GBASE-T"


def test_om4_over_400m_raises():
    with pytest.raises(PhysicalDistanceViolationError):
        recommend_media(401, "om4", 10000)


def test_copper_cannot_carry_40g():
    with pytest.raises(PhysicalDistanceViolationError):
        recommend_media(50, "copper", 40000)


def test_auto_moves_40g_off_copper():
    assert recommend_media(50, "auto", 40000)["medium_key"] == "om4"


def test_22km_uses_er_not_lr_and_matches_spec_wording():
    r = recommend_media(22000, "auto", 10000)
    assert r["transceiver"] == "10GBASE-ER"          # LR only reaches 10 km
    assert "exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber" in r["rationale"]
    assert "22 km" in r["rationale"]


def test_optical_budget_arithmetic_22km_er():
    ob = recommend_media(22000, "auto", 10000)["optical_budget"]
    assert ob["fibre_loss_db"] == 5.5 and ob["connector_loss_db"] == 1.0 and ob["splice_loss_db"] == 1.1
    assert ob["total_link_loss_db"] == 7.6 and ob["margin_db"] == 3.3 and ob["passes"]


def test_er_fails_budget_near_40km_so_zr_selected():
    assert recommend_media(38000, "auto", 10000)["transceiver"] == "10GBASE-ZR"


def test_beyond_single_span_flags_carrier_service():
    r = recommend_media(100000, "auto", 10000)
    assert r["requires_carrier_service"] and "carrier" in r["rationale"]


def test_100g_over_300m_escalates_to_smf():
    r = recommend_media(300, "auto", 100000)
    assert r["medium_key"] == "os2" and r["notes"]


def test_propagation_delay_5us_per_km():
    assert recommend_media(22000, "auto", 10000)["propagation_delay_ms"] == pytest.approx(0.11)


def test_rate_snapping_and_overflow():
    assert snap_rate(1) == 1000 and snap_rate(10001) == 40000
    with pytest.raises(PhysicalDistanceViolationError):
        snap_rate(100001)


def test_zero_distance_rejected():
    with pytest.raises(ValueError):
        recommend_media(0)
