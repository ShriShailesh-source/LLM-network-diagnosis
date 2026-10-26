"""Expected-state prediction and post-fix verification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedState:
    """Predicted state transition for a supported corrective command."""

    current_state: str
    candidate_command: str
    expected_state: str | None
    supported: bool
    reason: str


def predict_expected_state(current_state: str, candidate_command: str) -> ExpectedState:
    """Predict a state transition without executing a network command."""
    state = current_state.strip().lower()
    command = " ".join(candidate_command.strip().lower().split())
    if command == "no shutdown" and state == "admin_down":
        return ExpectedState(
            state, command, "up/up", True,
            "Administrative shutdown is expected to clear to operational up/up",
        )
    if command == "shutdown" and state in {"up", "down"}:
        return ExpectedState(
            state, command, "admin_down/down", True,
            "Shutdown is expected to produce administratively down/down",
        )
    return ExpectedState(
        state, command, None, False,
        "No deterministic expected-state mapping exists for this transition",
    )


def verify_expected_state(expected: ExpectedState, observed_state: str) -> bool:
    """Return whether an observed post-fix state matches the prediction."""
    return (
        expected.supported
        and expected.expected_state is not None
        and observed_state.strip().lower() == expected.expected_state
    )
