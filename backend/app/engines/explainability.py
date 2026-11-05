def build_architecture_report(media: dict, routing: dict, vlsm: dict, warnings: list[str]) -> list[dict]:
    decisions = [
        {"area": "Physical media", "decision": media["medium"], "reason": media["rationale"]},
        {"area": "Transceiver", "decision": media["transceiver"],
         "reason": "Selected as the matching transceiver family in the assignment scenario; verify exact reach and optical budget."},
        {"area": "Routing", "decision": routing["protocol"], "reason": routing["rationale"]},
        {"area": "Subnetting", "decision": "VLSM", "reason": vlsm["rationale"]},
    ]
    for warning in warnings:
        decisions.append({"area": "Validation warning", "decision": "Review required", "reason": warning})
    return decisions
