# LLM Network Diagnosis

## Validation module

`Validation` checks an LLM diagnosis before a candidate command is accepted. It
uses the diagnosis fields `event_id`, `device_id`, `target_interface`,
`detected_fault`, `candidate_command`, and `confidence_score`.

The small `Validation/topology.py` inventory defines the simulated devices and
interfaces. Callers can pass the current `interface_state` (`up`, `down`, or
`admin_down`) and `current_config` with the diagnosis payload to validate against
a fresher simulator snapshot. `validate_payload(payload)` adapts the LLM output
dictionary; `validate(ValidationInput(...))` supports direct use. Both return
`{"valid": bool, "errors": [...]}`.

The checks are deliberately simple for the CN project: required fields and
confidence range, device/interface lookup, a limited allowlist/parser for safe
interface commands, state checks to avoid redundant or disruptive changes, and
a fault-to-command mapping. Commands outside the supported subset are rejected
rather than passed through to a device.

Supported faults include `interface_down`, `administratively_down`,
`missing_ip_address`, `incorrect_ip_address`, `ip_misconfiguration`,
`duplex_mismatch`, `speed_mismatch`, and `interface_should_be_disabled`.
