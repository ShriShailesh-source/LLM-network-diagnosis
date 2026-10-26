from evaluation import (
    FAULT_TYPES,
    VALIDATION_VARIANTS,
    generate_cases,
    run_diagnosis_benchmark,
    run_evaluation,
    run_validation_benchmark,
)
from Validation.topology import DEFAULT_TOPOLOGY


def test_default_topology_models_three_routers_and_links():
    assert set(DEFAULT_TOPOLOGY.devices) == {"R1", "R2", "R3"}
    assert len(DEFAULT_TOPOLOGY.interfaces) == 6
    assert len(DEFAULT_TOPOLOGY.links) == 3
    assert DEFAULT_TOPOLOGY.interface("R1", "GigabitEthernet0/1").state == "admin_down"


def test_validation_benchmark_has_explicit_balanced_500_case_distribution():
    report = run_validation_benchmark(generate_cases(500))
    assert report["total_cases"] == 500
    assert report["valid_fix_cases"] == 100
    assert report["invalid_fix_cases"] == 400
    assert report["variant_distribution"] == {
        variant: 100 for variant in VALIDATION_VARIANTS
    }
    assert report["valid_fix_acceptance_rate"] == 1.0
    assert report["invalid_fix_rejection_rate"] == 1.0
    assert report["false_acceptance_rate"] == 0.0
    assert report["false_rejection_rate"] == 0.0
    assert report["overall_validation_classification_accuracy"] == 1.0
    assert sum(
        metrics["cases"] for metrics in report["by_fault_type"].values()
    ) == 500


def test_diagnosis_benchmark_compares_mock_predictions_with_ground_truth():
    report = run_diagnosis_benchmark()
    assert report["benchmark_type"] == "deterministic/mock diagnosis benchmark"
    assert report["total_cases"] == 30
    assert report["correct_cases"] == 27
    assert report["diagnosis_accuracy"] == 0.9
    assert set(report["by_fault_type"]) == set(FAULT_TYPES)
    assert sum(
        sum(row.values()) for row in report["confusion_matrix"].values()
    ) == 30


def test_combined_report_keeps_validation_and_diagnosis_metrics_separate():
    first = run_evaluation(generate_cases(30))
    second = run_evaluation(generate_cases(30))
    assert first == second
    assert set(first) == {"validation", "diagnosis", "methodology"}
    assert "diagnosis_accuracy" not in first["validation"]
    assert "overall_validation_classification_accuracy" in first["validation"]
    assert first["methodology"]["diagnosis"].startswith("deterministic/mock")
