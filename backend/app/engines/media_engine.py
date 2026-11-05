class PhysicalDistanceViolationError(ValueError):
    """Raised when copper Ethernet is requested beyond the assignment's 100m limit."""


def recommend_media(distance_m: float, requested_media: str = "auto") -> dict:
    if distance_m < 0:
        raise ValueError("Distance cannot be negative.")

    if requested_media == "copper" and distance_m > 100:
        raise PhysicalDistanceViolationError(
            f"Copper Ethernet requested for {distance_m:g}m; the assignment limit is 100m."
        )

    # Assignment rule: <=100m Cat6a; 101-400m OM4; >400m OS2.
    if distance_m <= 100:
        medium = "Cat6a"
        transceiver = "10GBASE-T (where 10 Gb/s is required)"
        rationale = (
            f"Cat6a is selected because the link distance ({distance_m:g}m) is within "
            "the assignment's 100m copper Ethernet boundary."
        )
    elif distance_m <= 400:
        medium = "OM4 Multimode Fiber"
        transceiver = "10GBASE-SR (850nm)"
        rationale = (
            f"OM4 multimode fiber is selected for the {distance_m:g}m backbone run, "
            "which falls in the assignment's 101–400m band. Verify actual transceiver reach."
        )
    else:
        medium = "OS2 Single-Mode Fiber"
        transceiver = "10GBASE-LR/ER (select to match reach)"
        rationale = (
            f"OS2 single-mode fiber is selected because the {distance_m:g}m run exceeds "
            "the assignment's 400m multimode-fiber band. Verify optical power budget and transceiver reach."
        )

    return {
        "medium": medium,
        "transceiver": transceiver,
        "distance_m": distance_m,
        "rationale": rationale,
        "engineering_note": (
            "Distance bands follow the assignment table. Real deployments must also validate "
            "Ethernet standard, fiber type, connector loss, splice loss, transceiver reach and optical budget."
        ),
    }
