"""Reproducible offline validation and deterministic/mock diagnosis benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import ParsedLogEvent
from Validation.topology import DEFAULT_TOPOLOGY
from Validation.validator import validate_payload


FAULT_TYPES = ("interface_down", "ospf_neighbor_down", "incorrect_ip")
VALIDATION_VARIANTS = (
    "valid",
    "wrong-command",
    "malformed",
    "wrong-target",
    "wrong-device",
)
INTERFACES = tuple(
    (item.device, item.name)
    for item in DEFAULT_TOPOLOGY.interfaces
    if item.name != "GigabitEthernet0/1" or item.device == "R1"
)


@dataclass(frozen=True)
class EvaluationCase:
    """One synthetic validation classification case with known fix validity."""

    case_id: str
    variant: str
    fault_type: str
    device: str
    interface: str
    expected_valid: bool
    candidate_command: str
    interface_state: str
    current_config: dict[str, str]


@dataclass(frozen=True)
class DiagnosisCase:
    """One evidence event and its independently defined ground-truth fault."""

    case_id: str
    ground_truth_fault: str
    event: ParsedLogEvent


def generate_cases(count: int = 500) -> list[EvaluationCase]:
    """Generate deterministic validation cases without network access.

    The five variants are assigned round-robin, producing exactly 100 of each
    for the default 500-case benchmark.
    """
    if count < 1:
        raise ValueError("count must be positive")
    cases: list[EvaluationCase] = []
    for index in range(count):
        fault_type = FAULT_TYPES[index % len(FAULT_TYPES)]
        device, interface = INTERFACES[index % len(INTERFACES)]
        variant = VALIDATION_VARIANTS[index % len(VALIDATION_VARIANTS)]
        expected_ip = "10.0.99.1 255.255.255.0"
        current_ip = "10.0.12.1 255.255.255.0"
        state = "admin_down" if fault_type in {"interface_down", "ospf_neighbor_down"} else "up"
        command = (
            "no shutdown"
            if fault_type in {"interface_down", "ospf_neighbor_down"}
            else f"ip address {expected_ip}"
        )
        case_device, case_interface = device, interface
        if variant == "wrong-command":
            command = "shutdown"
        elif variant == "malformed":
            command = "reload"
        elif variant == "wrong-target":
            case_interface = "GigabitEthernet9/9"
        elif variant == "wrong-device":
            case_device = "R99"
        config = (
            {"ip_address": current_ip, "expected_ip_address": expected_ip}
            if fault_type == "incorrect_ip"
            else {}
        )
        cases.append(
            EvaluationCase(
                case_id=f"CASE-{index + 1:04d}",
                variant=variant,
                fault_type=fault_type,
                device=case_device,
                interface=case_interface,
                expected_valid=variant == "valid",
                candidate_command=command,
                interface_state=state,
                current_config=config,
            )
        )
    return cases


def _diagnosis_cases() -> list[DiagnosisCase]:
    """Build deterministic evidence for the three diagnosis fault classes."""
    evidence = (
        (
            "interface_down",
            "R1",
            "GigabitEthernet0/1",
            "GigabitEthernet0/1 192.168.1.1 YES manual administratively down down",
        ),
        (
            "ospf_neighbor_down",
            "R2",
            "GigabitEthernet0/1",
            "R2 %OSPF-5-ADJCHG: Process 1, Nbr 10.0.23.2 on "
            "GigabitEthernet0/1 from FULL to DOWN, Neighbor Down: Dead timer expired",
        ),
        (
            "incorrect_ip",
            "R1",
            "GigabitEthernet0/0",
            "GigabitEthernet0/0 10.0.99.1 YES manual up up",
        ),
    )
    cases: list[DiagnosisCase] = []
    for index in range(30):
        fault, device, interface, raw_message = evidence[index % len(evidence)]
        event = ParsedLogEvent(
            event_id=f"DIAG-{index + 1:03d}",
            device_id=device,
            timestamp=None,
            target_interface=interface,
            detected_fault=fault,
            raw_message=raw_message,
            interface_state="admin_down" if fault == "interface_down" else "up",
            fault_type=fault,
            protocol="ospf" if fault == "ospf_neighbor_down" else None,
            neighbor_id="10.0.23.2" if fault == "ospf_neighbor_down" else None,
        )
        cases.append(DiagnosisCase(event.event_id, fault, event))
    return cases


class _DeterministicDiagnosisClient:
    """Mock diagnosis client with a declared, repeatable 90% prediction rate.

    This exercises ``diagnose_event`` without making an external LLM call. One
    case out of every ten is intentionally mapped to the next fault class so
    the reported score is an actual comparison, not a copied test flag.
    """

    def __init__(self, predictions: dict[str, str]) -> None:
        self.predictions = predictions
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        event_id = str(kwargs["contents"]).split("event_id: ", 1)[1].splitlines()[0]
        predicted_fault = self.predictions[event_id]
        event_fields = str(kwargs["contents"]).splitlines()
        fields = {
            line.split(": ", 1)[0]: line.split(": ", 1)[1]
            for line in event_fields
            if ": " in line
        }
        result = DiagnosisResult(
            event_id=event_id,
            device_id=fields["device_id"],
            target_interface=fields["target_interface"],
            detected_fault=predicted_fault,
            candidate_command="no shutdown",
            confidence_score=0.9,
        )
        return SimpleNamespace(parsed=result, text=result.model_dump_json())


def run_validation_benchmark(cases: list[EvaluationCase]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        diagnosis = DiagnosisResult(
            event_id=case.case_id,
            device_id=case.device,
            target_interface=case.interface,
            detected_fault=case.fault_type,
            candidate_command=case.candidate_command,
            confidence_score=0.95,
        )
        validation = validate_payload(
            diagnosis,
            interface_state=case.interface_state,
            current_config=case.current_config,
        )
        accepted = bool(validation["valid"])
        rows.append(
            {
                **asdict(case),
                "validation_result": "ACCEPTED" if accepted else "REJECTED",
                "rejection_reason": "; ".join(validation["errors"]),
            }
        )

    valid_cases = [row for row in rows if row["expected_valid"]]
    invalid_cases = [row for row in rows if not row["expected_valid"]]
    accepted_valid = sum(row["validation_result"] == "ACCEPTED" for row in valid_cases)
    rejected_invalid = sum(row["validation_result"] == "REJECTED" for row in invalid_cases)
    false_acceptances = sum(row["validation_result"] == "ACCEPTED" for row in invalid_cases)
    false_rejections = sum(row["validation_result"] == "REJECTED" for row in valid_cases)
    by_fault: dict[str, dict[str, int]] = {}
    for fault in FAULT_TYPES:
        selected = [row for row in rows if row["fault_type"] == fault]
        by_fault[fault] = {
            "cases": len(selected),
            "valid_fixes": sum(row["expected_valid"] for row in selected),
            "invalid_fixes": sum(not row["expected_valid"] for row in selected),
            "accepted": sum(row["validation_result"] == "ACCEPTED" for row in selected),
            "rejected": sum(row["validation_result"] == "REJECTED" for row in selected),
        }
    return {
        "total_cases": len(rows),
        "valid_fix_cases": len(valid_cases),
        "invalid_fix_cases": len(invalid_cases),
        "accepted_cases": sum(row["validation_result"] == "ACCEPTED" for row in rows),
        "rejected_cases": sum(row["validation_result"] == "REJECTED" for row in rows),
        "valid_fix_acceptance_rate": accepted_valid / len(valid_cases) if valid_cases else 0.0,
        "invalid_fix_rejection_rate": rejected_invalid / len(invalid_cases) if invalid_cases else 0.0,
        "false_acceptance_rate": false_acceptances / len(invalid_cases) if invalid_cases else 0.0,
        "false_rejection_rate": false_rejections / len(valid_cases) if valid_cases else 0.0,
        "overall_validation_classification_accuracy": (
            (accepted_valid + rejected_invalid) / len(rows) if rows else 0.0
        ),
        "variant_distribution": {
            variant: sum(row["variant"] == variant for row in rows)
            for variant in VALIDATION_VARIANTS
        },
        "by_fault_type": by_fault,
        "cases": rows,
    }


def run_diagnosis_benchmark(cases: list[DiagnosisCase] | None = None) -> dict[str, Any]:
    """Run the diagnosis interface against deterministic mock predictions."""
    cases = _diagnosis_cases() if cases is None else cases
    predictions: dict[str, str] = {}
    for index, case in enumerate(cases):
        if index % 10 == 0:
            predictions[case.case_id] = FAULT_TYPES[
                (FAULT_TYPES.index(case.ground_truth_fault) + 1) % len(FAULT_TYPES)
            ]
        else:
            predictions[case.case_id] = case.ground_truth_fault
    client = _DeterministicDiagnosisClient(predictions)
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = diagnose_event(case.event, client=client)
        predicted = result.detected_fault
        rows.append(
            {
                "case_id": case.case_id,
                "ground_truth_fault": case.ground_truth_fault,
                "predicted_fault": predicted,
                "correct": predicted == case.ground_truth_fault,
            }
        )
    by_fault = {
        fault: {
            "cases": sum(row["ground_truth_fault"] == fault for row in rows),
            "correct": sum(
                row["ground_truth_fault"] == fault and row["correct"] for row in rows
            ),
            "accuracy": (
                sum(row["ground_truth_fault"] == fault and row["correct"] for row in rows)
                / sum(row["ground_truth_fault"] == fault for row in rows)
            ),
        }
        for fault in FAULT_TYPES
    }
    confusion_matrix = {
        truth: {
            predicted: sum(
                row["ground_truth_fault"] == truth
                and row["predicted_fault"] == predicted
                for row in rows
            )
            for predicted in FAULT_TYPES
        }
        for truth in FAULT_TYPES
    }
    return {
        "benchmark_type": "deterministic/mock diagnosis benchmark",
        "total_cases": len(rows),
        "correct_cases": sum(row["correct"] for row in rows),
        "diagnosis_accuracy": sum(row["correct"] for row in rows) / len(rows) if rows else 0.0,
        "by_fault_type": by_fault,
        "confusion_matrix": confusion_matrix,
        "cases": rows,
    }


def run_evaluation(cases: list[EvaluationCase] | None = None) -> dict[str, Any]:
    """Run both separate offline benchmarks and return a combined report."""
    validation = run_validation_benchmark(generate_cases() if cases is None else cases)
    diagnosis = run_diagnosis_benchmark()
    return {
        "validation": validation,
        "diagnosis": diagnosis,
        "methodology": {
            "validation": "deterministic offline/synthetic validation classification",
            "diagnosis": "deterministic/mock diagnosis client; no external LLM calls",
        },
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_results(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_csv(report["validation"]["cases"], output_dir / "evaluation.csv")
    (output_dir / "diagnosis.json").write_text(
        json.dumps(report["diagnosis"], indent=2), encoding="utf-8"
    )
    _write_csv(report["diagnosis"]["cases"], output_dir / "diagnosis.csv")
    summary = {
        "methodology": report["methodology"],
        "validation": {key: value for key, value in report["validation"].items() if key != "cases"},
        "diagnosis": {key: value for key, value in report["diagnosis"].items() if key != "cases"},
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _percent(value: float) -> str:
    return f"{value:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation_results"))
    args = parser.parse_args()
    report = {
        "validation": run_validation_benchmark(generate_cases(args.count)),
        "diagnosis": run_diagnosis_benchmark(),
        "methodology": {
            "validation": "deterministic offline/synthetic validation classification",
            "diagnosis": "deterministic/mock diagnosis client; no external LLM calls",
        },
    }
    write_results(report, args.output_dir)
    validation = report["validation"]
    diagnosis = report["diagnosis"]
    print("VALIDATION BENCHMARK")
    print(f"Total cases: {validation['total_cases']}")
    print(f"Valid fixes: {validation['valid_fix_cases']}")
    print(f"Invalid fixes: {validation['invalid_fix_cases']}")
    print(f"Valid-fix acceptance: {_percent(validation['valid_fix_acceptance_rate'])}")
    print(f"Invalid-fix rejection: {_percent(validation['invalid_fix_rejection_rate'])}")
    print(f"False acceptance: {_percent(validation['false_acceptance_rate'])}")
    print(f"False rejection: {_percent(validation['false_rejection_rate'])}")
    print(
        "Validation accuracy: "
        f"{_percent(validation['overall_validation_classification_accuracy'])}"
    )
    print(f"Variant distribution: {validation['variant_distribution']}")
    print("\nDIAGNOSIS BENCHMARK")
    print("Deterministic/mock diagnosis client; no external LLM calls")
    print(f"Total diagnosis cases: {diagnosis['total_cases']}")
    print(f"Diagnosis accuracy: {_percent(diagnosis['diagnosis_accuracy'])}")
    for fault, metrics in diagnosis["by_fault_type"].items():
        print(f"{fault}: {_percent(metrics['accuracy'])} ({metrics['cases']} cases)")
    print(f"\nresults: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
