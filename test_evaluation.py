from evaluation import generate_cases, run_evaluation
from Validation.topology import DEFAULT_TOPOLOGY


def test_default_topology_models_three_routers_and_links():
    assert set(DEFAULT_TOPOLOGY.devices) == {"R1", "R2", "R3"}
    assert len(DEFAULT_TOPOLOGY.interfaces) == 6
    assert len(DEFAULT_TOPOLOGY.links) == 3
    assert DEFAULT_TOPOLOGY.interface("R1", "GigabitEthernet0/1").state == "admin_down"


def test_evaluation_is_deterministic_and_reports_metrics():
    first = run_evaluation(generate_cases(30))
    second = run_evaluation(generate_cases(30))
    assert first == second
    assert first["case_count"] == 30
    assert first["false_acceptance_rate"] == 0.0
    assert first["false_rejection_rate"] == 0.0
    assert set(first["by_fault_type"]) == {
        "interface_down", "ospf_neighbor_down", "incorrect_ip"
    }
