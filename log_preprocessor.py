"""Normalize Cisco-style fixture evidence into structured network events."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from uuid import uuid4


_TIMESTAMP = re.compile(
    r"^\*?(?P<timestamp>(?:[A-Z][a-z]{2}\s+\d{1,2}\s+"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"|\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?))"
)
_DEVICE_ID = re.compile(r"\s(?P<device>[A-Za-z0-9_.-]+)\s+%[A-Z]+-\d+-")
_INTERFACE_DOWN = re.compile(
    r"\bInterface\s+(?P<interface>[\w./:-]+),?\s+"
    r"(?:changed state to|is)\s+down\b",
    re.IGNORECASE,
)
_OSPF_NEIGHBOR_DOWN = re.compile(
    r"\b(?:Nbr|Neighbor)\s+(?P<neighbor>\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"on\s+(?P<interface>[\w./:-]+).*?\bto\s+DOWN\b"
    r"(?:,\s*Neighbor Down:\s*(?P<reason>[^,]+))?",
    re.IGNORECASE,
)
_INTERFACE_BRIEF = re.compile(
    r"^(?P<interface>[\w./:-]+)\s+\S+\s+(?:YES|NO)\s+\S+\s+"
    r"(?P<status>administratively down|down|up)\s+(?:down|up)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedLogEvent:
    """A normalized event extracted from one supported log line."""

    event_id: str
    device_id: str | None
    timestamp: str | None
    target_interface: str
    detected_fault: str
    raw_message: str
    interface_state: str | None = None
    fault_type: str = "interface_down"
    protocol: str | None = None
    neighbor_id: str | None = None
    ip_address: str | None = None


def parse_logs(raw_logs: str, device_id: str | None = None) -> list[ParsedLogEvent]:
    """Extract interface-down and OSPF-neighbor-down events from raw text.

    Provide ``device_id`` when the source logs do not include a hostname.
    Unrecognized lines are ignored. Candidate commands and confidence scores
    are intentionally left to the downstream diagnosis engine.
    """
    events: list[ParsedLogEvent] = []

    for line in raw_logs.splitlines():
        message = line.strip()
        if not message:
            continue

        timestamp_match = _TIMESTAMP.match(message)
        timestamp = timestamp_match.group("timestamp") if timestamp_match else None
        hostname_match = _DEVICE_ID.search(message)
        resolved_device_id = (
            device_id
            or (hostname_match.group("device") if hostname_match else None)
        )

        neighbor_match = _OSPF_NEIGHBOR_DOWN.search(message)
        interface_match = _INTERFACE_DOWN.search(message)
        brief_match = _INTERFACE_BRIEF.match(message)
        interface_state = None

        fault_type = "interface_down"
        protocol = None
        neighbor_id = None
        ip_address = None
        if neighbor_match:
            neighbor = neighbor_match.group("neighbor")
            reason = neighbor_match.group("reason")
            fault = f"OSPF neighbor {neighbor} went down"
            if reason:
                fault += f" (reason: {reason.strip()})"
            interface = neighbor_match.group("interface")
            fault_type = "ospf_neighbor_down"
            protocol = "ospf"
            neighbor_id = neighbor
        elif interface_match:
            interface = interface_match.group("interface")
            fault = f"Interface {interface} is down"
        elif brief_match:
            status = brief_match.group("status").lower()
            if status == "up":
                continue
            interface = brief_match.group("interface")
            fault = f"Interface {interface} is down"
            interface_state = (
                'admin_down'
                if status == 'administratively down'
                else 'down'
            )
            ip_address = message.split()[1] if len(message.split()) > 1 else None
        else:
            continue

        events.append(
            ParsedLogEvent(
                event_id=str(uuid4()),
                device_id=resolved_device_id,
                timestamp=timestamp,
                target_interface=interface,
                detected_fault=fault,
                raw_message=message,
                interface_state=interface_state,
                fault_type=fault_type,
                protocol=protocol,
                neighbor_id=neighbor_id,
                ip_address=ip_address,
            )
        )

    return events


if __name__ == "__main__":
    sample_logs = """\
*Oct 23 17:01:02.123: %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down
Oct 23 17:01:03 router1 %OSPF-5-ADJCHG: Process 1, Nbr 10.0.0.2 on GigabitEthernet0/1 from FULL to DOWN, Neighbor Down: Interface down
"""
    for event in parse_logs(sample_logs, device_id="router1"):
        print(asdict(event))
