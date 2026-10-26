"""Deterministic three-router OSPF Area 0-style simulated topology."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Interface:
    device: str
    name: str
    ip_address: str | None
    state: str
    ospf_area: int = 0


@dataclass(frozen=True)
class Link:
    left: tuple[str, str]
    right: tuple[str, str]
    protocol: str = "ospf"


@dataclass(frozen=True)
class SimulatedTopology:
    interfaces: tuple[Interface, ...]
    links: tuple[Link, ...]
    ospf_neighbors: dict[str, tuple[str, ...]]

    def interface(self, device: str, name: str) -> Interface | None:
        return next(
            (item for item in self.interfaces
             if item.device == device and item.name == name),
            None,
        )

    @property
    def devices(self) -> dict[str, set[str]]:
        return {
            device: {item.name for item in self.interfaces if item.device == device}
            for device in {item.device for item in self.interfaces}
        }


def build_default_topology() -> SimulatedTopology:
    """Build the repeatable lab topology used by validation and evaluation.

    This is a state model, not a live OSPF implementation.
    """
    interfaces = (
        Interface("R1", "GigabitEthernet0/0", "10.0.12.1/30", "up"),
        Interface("R1", "GigabitEthernet0/1", "10.0.13.1/30", "admin_down"),
        Interface("R2", "GigabitEthernet0/0", "10.0.12.2/30", "up"),
        Interface("R2", "GigabitEthernet0/1", "10.0.23.1/30", "up"),
        Interface("R3", "GigabitEthernet0/0", "10.0.23.2/30", "up"),
        Interface("R3", "GigabitEthernet0/1", "10.0.13.2/30", "up"),
    )
    links = (
        Link(("R1", "GigabitEthernet0/0"), ("R2", "GigabitEthernet0/0")),
        Link(("R2", "GigabitEthernet0/1"), ("R3", "GigabitEthernet0/0")),
        Link(("R3", "GigabitEthernet0/1"), ("R1", "GigabitEthernet0/1")),
    )
    return SimulatedTopology(
        interfaces=interfaces,
        links=links,
        ospf_neighbors={"R1": ("R2", "R3"), "R2": ("R1", "R3"), "R3": ("R1", "R2")},
    )


DEFAULT_TOPOLOGY = build_default_topology()

# This intentionally small inventory is the project's simulated network.
# A simulator can supply its own state through ValidationInput.interface_state.
DEVICES = DEFAULT_TOPOLOGY.devices

# State labels: up, down, or admin_down. State is only used when caller does
# not provide a fresher interface_state snapshot.
INTERFACE_STATES = {
    (item.device, item.name): item.state for item in DEFAULT_TOPOLOGY.interfaces
}
