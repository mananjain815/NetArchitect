"""L1 media engine: distance + bandwidth physics, transceiver selection and optical budget.

Distance bands follow the CIC-307 table:
    <= 100 m   -> Cat6a   (IEEE 802.3an, 10GBASE-T)
    101-400 m  -> OM4 MMF (10GBASE-SR @ 850 nm)
    > 400 m    -> OS2 SMF (10GBASE-LR / ER / ZR)
Bandwidth then selects the Ethernet standard, and the optical budget is checked for fibre links.
Loss / budget constants are planning values (IEEE 802.3 / TIA-568 / vendor datasheets): verify
against the datasheet of the actual optic before purchase.
"""
import math


class PhysicalDistanceViolationError(ValueError):
    """Raised when the requested medium cannot physically carry the requested distance / rate."""


STANDARD_RATES = (1000, 10000, 40000, 100000)

# (name, medium, reach_m, wavelength_nm, channel_insertion_loss_budget_dB or None)
TRANSCEIVERS = {
    1000: [
        ("1000BASE-T", "cat6a", 100, None, None),
        ("1000BASE-SX", "om4", 550, 850, None),
        ("1000BASE-LX", "os2", 10_000, 1310, 4.5),
        ("1000BASE-EX", "os2", 40_000, 1310, None),
        ("1000BASE-ZX", "os2", 70_000, 1550, None),
    ],
    10000: [
        ("10GBASE-T", "cat6a", 100, None, None),
        ("10GBASE-SR", "om4", 400, 850, 2.9),
        ("10GBASE-LR", "os2", 10_000, 1310, 6.2),
        ("10GBASE-ER", "os2", 40_000, 1550, 10.9),
        ("10GBASE-ZR", "os2", 80_000, 1550, 24.0),
    ],
    40000: [
        ("40GBASE-SR4", "om4", 150, 850, None),
        ("40GBASE-LR4", "os2", 10_000, 1310, 6.7),
        ("40GBASE-ER4", "os2", 40_000, 1310, 15.0),
    ],
    100000: [
        ("100GBASE-SR4", "om4", 100, 850, 1.9),
        ("100GBASE-LR4", "os2", 10_000, 1310, 6.3),
        ("100GBASE-ER4", "os2", 40_000, 1310, 15.0),
    ],
}

# Planning attenuation in dB/km
ATTENUATION_DB_KM = {("om4", 850): 3.5, ("os2", 1310): 0.40, ("os2", 1550): 0.25}
CONNECTOR_LOSS_DB = 0.5      # per mated pair, 2 per link
SPLICE_LOSS_DB = 0.1         # one fusion splice assumed every 2 km of cable
SPLICE_SPACING_KM = 2.0
FIBER_DELAY_MS_PER_KM = 0.005  # ~5 microseconds per km (group index ~1.47)

MEDIUM_LABEL = {"cat6a": "Cat6a", "om4": "OM4 Multimode Fiber", "os2": "OS2 Single-Mode Fiber"}


def fmt_distance(distance_m: float) -> str:
    return f"{distance_m / 1000:g} km" if distance_m >= 1000 else f"{distance_m:g} m"


def snap_rate(bandwidth_mbps: int) -> int:
    """Smallest standard Ethernet rate that can carry the requested bandwidth."""
    if bandwidth_mbps < 1:
        raise ValueError("Bandwidth must be positive.")
    for rate in STANDARD_RATES:
        if bandwidth_mbps <= rate:
            return rate
    raise PhysicalDistanceViolationError(
        f"{bandwidth_mbps} Mb/s exceeds the highest rate supported by this tool (100GbE); "
        "use link aggregation or a 200G/400G design."
    )


def optical_budget(medium: str, distance_m: float, wavelength: int, budget_db) -> dict:
    km = distance_m / 1000
    alpha = ATTENUATION_DB_KM[(medium, wavelength)]
    fibre = round(alpha * km, 2)
    connectors = 2 * CONNECTOR_LOSS_DB
    splices = round(math.floor(km / SPLICE_SPACING_KM) * SPLICE_LOSS_DB, 2) if medium == "os2" else 0.0
    total = round(fibre + connectors + splices, 2)
    out = {
        "wavelength_nm": wavelength,
        "attenuation_db_per_km": alpha,
        "fibre_loss_db": fibre,
        "connector_loss_db": connectors,
        "splice_loss_db": splices,
        "total_link_loss_db": total,
        "budget_db": budget_db,
        "margin_db": None if budget_db is None else round(budget_db - total, 2),
        "passes": None if budget_db is None else (budget_db - total) >= 0,
    }
    return out


def _candidates(rate: int, medium: str):
    return [t for t in TRANSCEIVERS[rate] if t[1] == medium]


def _pick_optic(rate: int, medium: str, distance_m: float):
    """Return (transceiver tuple, budget dict|None, rejected list) for the smallest optic that works."""
    rejected = []
    for name, med, reach, wl, budget in _candidates(rate, medium):
        if distance_m > reach:
            rejected.append(f"{name}: reach {fmt_distance(reach)} < {fmt_distance(distance_m)}")
            continue
        ob = optical_budget(med, distance_m, wl, budget) if wl else None
        if ob and ob["passes"] is False:
            rejected.append(
                f"{name}: link loss {ob['total_link_loss_db']} dB > budget {ob['budget_db']} dB"
            )
            continue
        return (name, med, reach, wl, budget), ob, rejected
    return None, None, rejected


def recommend_media(distance_m: float, requested_media: str = "auto", bandwidth_mbps: int = 10000) -> dict:
    """Choose medium + Ethernet standard for ONE link. Raises PhysicalDistanceViolationError."""
    if distance_m <= 0:
        raise ValueError("Distance must be greater than zero.")
    rate = snap_rate(bandwidth_mbps)
    dist = fmt_distance(distance_m)
    notes: list[str] = []

    # ---- 1. boundary errors on explicit requests -------------------------------------------------
    if requested_media == "copper" and distance_m > 100:
        raise PhysicalDistanceViolationError(
            f"Copper (Cat6a / 802.3an) requested for {dist}, but twisted-pair Ethernet is limited to "
            "100 m (90 m permanent link + 10 m patch cords). Beyond that, insertion loss and "
            "crosstalk (NEXT/alien) exceed the receiver's equalisation range and the link fails. "
            "Use OM4 (101-400 m) or OS2 single-mode fibre."
        )
    if requested_media == "copper" and rate > 10000:
        raise PhysicalDistanceViolationError(
            f"Copper cannot carry {rate / 1000:g} Gb/s: Cat6a tops out at 10GBASE-T."
        )
    if requested_media == "om4" and distance_m > 400:
        raise PhysicalDistanceViolationError(
            f"OM4 multimode fibre requested for {dist}; 850 nm modal dispersion and attenuation limit "
            "10GBASE-SR to 400 m on OM4 (IEEE 802.3ae). Use OS2 single-mode fibre."
        )

    # ---- 2. distance band per assignment table ---------------------------------------------------
    if requested_media in ("om4", "os2"):
        band = requested_media
    elif distance_m <= 100:
        band = "cat6a"
    elif distance_m <= 400:
        band = "om4"
    else:
        band = "os2"

    # bandwidth physics: Cat6a cannot exceed 10 Gb/s
    if band == "cat6a" and rate > 10000:
        band = "om4"
        notes.append(
            f"Cat6a supports at most 10 Gb/s (10GBASE-T), so the {rate // 1000}G requirement is moved to fibre."
        )
    medium = band
    pick, ob, rejected = _pick_optic(rate, medium, distance_m)

    # OM4 optic cannot reach (e.g. 40G/100G-SR4 reach 150/100 m) -> escalate to single-mode
    if pick is None and medium == "om4" and requested_media != "om4":
        notes.append(
            f"{rate // 1000}G multimode optics reach less than {dist} on OM4 ({'; '.join(rejected)}); "
            "the link is escalated to OS2 single-mode."
        )
        medium = "os2"
        pick, ob, rejected = _pick_optic(rate, medium, distance_m)

    requires_carrier = False
    if pick is None:
        if medium == "os2":
            requires_carrier = True
            transceiver = "No single-span optic reaches this distance"
            reach_m = None
            wl = None
        else:
            raise PhysicalDistanceViolationError(
                f"No {MEDIUM_LABEL[medium]} transceiver for {rate // 1000}G reaches {dist}. "
                + "; ".join(rejected)
            )
    else:
        transceiver, _, reach_m, wl, _b = pick

    # ---- 3. rationale -----------------------------------------------------------------------------
    rate_txt = f"{rate // 1000}G" if rate >= 1000 else f"{rate}M"
    if medium == "cat6a":
        rationale = (
            f"Selected Cat6a because link distance ({dist}) is within the 100 m twisted-pair limit of "
            f"IEEE 802.3an; {transceiver} runs over Cat6a at up to 100 m at {rate_txt}."
        )
    elif medium == "om4":
        why = "exceeds the 100 m copper limit" if distance_m > 100 else "was explicitly requested"
        rationale = (
            f"Selected OM4 Multimode Fiber because link distance ({dist}) {why} and stays inside the "
            f"400 m OM4 reach of {transceiver} (850 nm VCSEL, IEEE 802.3ae); beyond 400 m modal "
            "dispersion and attenuation at 850 nm close the eye."
        )
    else:
        if distance_m > 400:
            why = f"link distance ({dist}) exceeds the 400 m attenuation/dispersion limit of OM4 Multimode Fiber"
        else:
            why = "single-mode was explicitly requested (or the multimode optic cannot meet the data rate)"
        rationale = f"Selected OS2 Single-Mode Fiber because {why}."
        if pick:
            rationale += f" {transceiver} ({wl} nm) reaches {fmt_distance(reach_m)}."
        else:
            rationale += (
                f" No single-span {rate_txt} optic reaches {dist} (longest is ZR/ER-class at 40-80 km): "
                "provision the path as carrier-provided service, DWDM with amplification, or regenerate."
            )
    if rejected and pick:
        rationale += " Rejected smaller optics: " + "; ".join(rejected) + "."
    if ob:
        m = ob["margin_db"]
        if m is not None:
            rationale += (
                f" Optical budget: {ob['attenuation_db_per_km']} dB/km x {distance_m / 1000:g} km = "
                f"{ob['fibre_loss_db']} dB fibre + {ob['connector_loss_db']} dB connectors"
                + (f" + {ob['splice_loss_db']} dB splices" if ob["splice_loss_db"] else "")
                + f" = {ob['total_link_loss_db']} dB total vs {ob['budget_db']} dB transceiver budget "
                f"-> {m} dB margin."
            )
            if m < 1.0:
                notes.append(f"Optical margin is thin ({m} dB); add attenuation headroom or choose a longer-reach optic.")
        else:
            rationale += (
                f" Estimated link loss {ob['total_link_loss_db']} dB; verify against the vendor datasheet "
                "budget of the exact optic."
            )

    delay = round(distance_m / 1000 * FIBER_DELAY_MS_PER_KM, 4) if medium in ("om4", "os2") else 0.0
    return {
        "medium": MEDIUM_LABEL[medium],
        "medium_key": medium,
        "rate_mbps": rate,
        "transceiver": transceiver,
        "reach_m": reach_m,
        "distance_m": distance_m,
        "rationale": rationale,
        "optical_budget": ob,
        "propagation_delay_ms": delay,
        "requires_carrier_service": requires_carrier,
        "notes": notes,
        "engineering_note": (
            "Planning values only (IEEE 802.3, TIA-568). Validate connector/splice counts and the "
            "datasheet budget of the exact transceiver before ordering."
        ),
    }


def plan_media(distance_m: float, access_distance_m: float, bandwidth_mbps: int,
               access_bandwidth_mbps: int, requested_media: str = "auto") -> dict:
    """Access run and backbone/WAN run are different links with different rules."""
    backbone = recommend_media(distance_m, requested_media, bandwidth_mbps)
    access = recommend_media(access_distance_m, "auto", access_bandwidth_mbps)
    return {"backbone": backbone, "access": access}
