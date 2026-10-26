"""Deterministic risk classification for candidate configuration commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskAssessment:
    """Risk and blast-radius attributes for one candidate command."""

    risk_level: str
    blast_radius: str
    reversible: bool
    reason: str


def classify_risk(command: str) -> RiskAssessment:
    """Classify a command without trusting any model-provided risk label."""
    normalized = " ".join(command.strip().lower().split())
    if normalized in {"reload", "write erase", "erase startup-config", "erase nvram:"}:
        return RiskAssessment("CRITICAL", "DEVICE", False, "Destructive or reload operation")
    if normalized.startswith(("access-list ", "ip access-group ", "route-map ")):
        return RiskAssessment("HIGH", "MULTIPLE_FLOWS", True, "May affect multiple traffic flows")
    if normalized.startswith(("router ", "ip route ", "ipv6 route ")):
        return RiskAssessment("HIGH", "NETWORK_PATH", True, "Routing change may affect network reachability")
    if normalized.startswith(("ip address ", "no ip address")):
        return RiskAssessment("MEDIUM", "SINGLE_INTERFACE", True, "Changes interface addressing")
    if normalized in {"no shutdown", "shutdown"}:
        return RiskAssessment("LOW", "SINGLE_INTERFACE", True, "Reversible single-interface state change")
    return RiskAssessment("UNKNOWN", "UNKNOWN", False, "Command is outside the classified policy")
