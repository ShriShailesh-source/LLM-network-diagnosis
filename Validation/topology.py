"""Small simulated topology and interface state for validation."""

# This intentionally small inventory is the project's simulated network.
# A simulator can supply its own state through ValidationInput.interface_state.
DEVICES = {
    "R1": {"GigabitEthernet0/1", "GigabitEthernet0/2"},
    "R2": {"GigabitEthernet0/1", "GigabitEthernet0/2"},
    "SW1": {"GigabitEthernet0/1", "GigabitEthernet0/2"},
}

# State labels: up, down, or admin_down. State is only used when caller does
# not provide a fresher interface_state snapshot.
INTERFACE_STATES = {
    ("R1", "GigabitEthernet0/1"): "admin_down",
    ("R1", "GigabitEthernet0/2"): "up",
    ("R2", "GigabitEthernet0/1"): "admin_down",
    ("R2", "GigabitEthernet0/2"): "up",
    ("SW1", "GigabitEthernet0/1"): "admin_down",
    ("SW1", "GigabitEthernet0/2"): "up",
}
