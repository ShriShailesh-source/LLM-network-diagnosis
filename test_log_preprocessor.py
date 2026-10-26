import unittest
from uuid import UUID

from log_preprocessor import parse_logs


class ParseLogsTests(unittest.TestCase):
    def test_parses_interface_and_ospf_neighbor_down(self) -> None:
        raw_logs = """\
*Oct 23 17:01:02.123: %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down
Oct 23 17:01:03 router1 %OSPF-5-ADJCHG: Process 1, Nbr 10.0.0.2 on GigabitEthernet0/1 from FULL to DOWN, Neighbor Down: Interface down
"""

        events = parse_logs(raw_logs)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].device_id, None)
        self.assertEqual(events[0].timestamp, "Oct 23 17:01:02.123")
        self.assertEqual(events[0].target_interface, "GigabitEthernet0/1")
        self.assertEqual(events[0].detected_fault, "Interface GigabitEthernet0/1 is down")
        self.assertEqual(events[1].device_id, "router1")
        self.assertEqual(events[1].target_interface, "GigabitEthernet0/1")
        self.assertEqual(
            events[1].detected_fault,
            "OSPF neighbor 10.0.0.2 went down (reason: Interface down)",
        )
        UUID(events[0].event_id)
        UUID(events[1].event_id)

    def test_uses_supplied_device_id_and_skips_unrecognized_lines(self) -> None:
        events = parse_logs(
            "informational message\n"
            "%LINK-3-UPDOWN: Interface Ethernet1/2 is down",
            device_id="switch-a",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].device_id, "switch-a")
        self.assertEqual(events[0].target_interface, "Ethernet1/2")

    def test_empty_input_returns_no_events(self) -> None:
        self.assertEqual(parse_logs(" \n"), [])

    def test_ospf_event_exposes_structured_protocol_fields(self) -> None:
        event = parse_logs(
            "R2 %OSPF-5-ADJCHG: Process 1, Nbr 10.0.23.2 on "
            "GigabitEthernet0/1 from FULL to DOWN, Neighbor Down: Dead timer expired"
        )[0]
        self.assertEqual(event.fault_type, "ospf_neighbor_down")
        self.assertEqual(event.protocol, "ospf")
        self.assertEqual(event.neighbor_id, "10.0.23.2")


if __name__ == "__main__":
    unittest.main()
