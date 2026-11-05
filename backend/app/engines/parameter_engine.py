from app.models.schemas import NetworkRequest


def validate_parameters(data: NetworkRequest) -> list[str]:
    """Return non-fatal engineering warnings after schema validation."""
    warnings: list[str] = []
    if data.distance_m > 100 and data.bandwidth_mbps > 10000:
        warnings.append(
            "High-bandwidth backbone: verify the selected transceiver's supported rate and optical budget."
        )
    if data.resiliency == "high" and data.site_count < 2:
        warnings.append(
            "High resiliency was requested, but only one site was supplied; add a redundant path/device."
        )
    if data.endpoints > sum(item.hosts for item in data.subnet_requests):
        warnings.append(
            "The sum of requested subnet hosts is lower than the total endpoint count. Confirm the subnet requests."
        )
    return warnings
