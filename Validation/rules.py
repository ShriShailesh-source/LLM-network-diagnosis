"""Validation rules for candidate network configuration commands."""
import ipaddress
import math
import re

from .models import ValidationInput
from .topology import DEVICES, INTERFACE_STATES


def validate_required_fields(data: ValidationInput) -> list[str]:
    errors = []
    for name in ("event_id", "device_id", "target_interface", "detected_fault", "candidate_command"):
        value = getattr(data, name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Missing or invalid {name}")
    score = data.confidence_score
    if (isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(score) or not 0.0 <= score <= 1.0):
        errors.append("confidence_score must be a finite number between 0 and 1")
    return errors


def validate_target(data: ValidationInput) -> list[str]:
    if data.device_id not in DEVICES:
        return [f"Unknown device: {data.device_id}"]
    if data.target_interface not in DEVICES[data.device_id]:
        return [f"Unknown interface {data.target_interface} on {data.device_id}"]
    return []


def parse_command(command: str) -> tuple[str, str] | None:
    """Accept only a deliberately limited, safe Cisco-like command subset."""
    command = " ".join(command.strip().split())
    if command.lower() in {"no shutdown", "shutdown", "no ip address", "no keepalive"}:
        return command.lower(), ""
    match = re.fullmatch(r"(?i)ip address (\S+) (\S+)", command)
    if match:
        try:
            address = ipaddress.IPv4Address(match.group(1))
            mask = ipaddress.IPv4Network(f"0.0.0.0/{match.group(2)}").netmask
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            return None
        return "ip address", f"{address} {mask}"
    match = re.fullmatch(r"(?i)duplex (auto|full|half)", command)
    if match:
        return "duplex", match.group(1).lower()
    match = re.fullmatch(r"(?i)speed (10|100|1000|auto)", command)
    if match:
        return "speed", match.group(1).lower()
    match = re.fullmatch(r"(?i)description ([\w .-]{1,80})", command)
    if match:
        return "description", match.group(1)
    return None


def validate_command_syntax(data: ValidationInput) -> tuple[list[str], tuple[str, str] | None]:
    parsed = parse_command(data.candidate_command) if isinstance(data.candidate_command, str) else None
    if parsed is None:
        return ["Unsupported or syntactically invalid candidate_command"], None
    return [], parsed


def validate_network_state(data: ValidationInput, command: tuple[str, str]) -> list[str]:
    action, _ = command
    state = (
        data.interface_state
        if data.interface_state is not None
        else INTERFACE_STATES.get((data.device_id, data.target_interface))
    )
    config = data.current_config or {}
    errors = []
    if state not in {"up", "down", "admin_down"}:
        return ["Unknown interface state; provide up, down, or admin_down"]
    if action == "no shutdown" and state == "up":
        errors.append("Interface is already up; no shutdown is unnecessary")
    elif action == "no shutdown" and state != "admin_down":
        errors.append("no shutdown is only safe when the interface is administratively down")
    elif action == "shutdown" and state == "admin_down":
        errors.append("Interface is already administratively down")
    elif action == "shutdown" and state == "down":
        errors.append("Shutdown would disable an interface that is already down")
    elif action == "no ip address" and not config.get("ip_address"):
        errors.append("Interface has no configured IP address to remove")
    elif action == "ip address" and config.get("ip_address") == command[1]:
        errors.append("Interface already has the proposed IP address")
    elif action == "ip address" and config.get("expected_ip_address"):
        if config["expected_ip_address"] != command[1]:
            errors.append("Proposed IP address does not match the expected network state")
    elif action == "duplex" and config.get("duplex") == command[1]:
        errors.append("Interface already uses the proposed duplex setting")
    elif action == "speed" and config.get("speed") == command[1]:
        errors.append("Interface already uses the proposed speed setting")
    return errors


FAULT_COMMANDS = {
    "interface_down": {"no shutdown"},
    "administratively_down": {"no shutdown"},
    "ospf_neighbor_down": {"no shutdown"},
    "neighbor_down": {"no shutdown"},
    "missing_ip_address": {"ip address"},
    "incorrect_ip_address": {"ip address"},
    "incorrect_ip": {"ip address"},
    "ip_misconfiguration": {"ip address", "no ip address"},
    "duplex_mismatch": {"duplex"},
    "speed_mismatch": {"speed"},
    "interface_should_be_disabled": {"shutdown"},
}


def normalize_fault_label(fault: str) -> str:
    """Map free-form LLM fault descriptions to the validator's canonical labels."""
    normalized = "_".join(fault.strip().lower().replace("-", " ").split())
    if "administratively_down" in normalized or "administratively_down" == normalized:
        return "administratively_down"
    if re.fullmatch(r"interface(?:_\w+)*_is_down", normalized):
        return "interface_down"
    if normalized.startswith("interface_") and normalized.endswith("_down"):
        return "interface_down"
    return normalized


def validate_fault_fix(data: ValidationInput, command: tuple[str, str]) -> list[str]:
    fault = normalize_fault_label(data.detected_fault)
    allowed = FAULT_COMMANDS.get(fault)
    if not allowed or command[0] not in allowed:
        return [f"Command '{data.candidate_command}' does not address detected fault '{data.detected_fault}'"]
    # A shutdown is only justified for an explicit disable fault.
    if command[0] == "shutdown" and fault != "interface_should_be_disabled":
        return ["Rejecting shutdown because the detected fault does not require disabling the interface"]
    return []


def validate_rules(data: ValidationInput) -> list[str]:
    errors = validate_required_fields(data)
    if errors:
        return errors
    errors.extend(validate_target(data))
    if errors:
        return errors
    syntax_errors, parsed = validate_command_syntax(data)
    errors.extend(syntax_errors)
    if parsed is not None:
        errors.extend(validate_network_state(data, parsed))
        errors.extend(validate_fault_fix(data, parsed))
    return errors
