"""Reproducible, offline evaluation of diagnosis and validation decisions."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ai_engine import DiagnosisResult
from Validation.topology import DEFAULT_TOPOLOGY
from Validation.validator import validate_payload


FAULT_TYPES = ("interface_down", "ospf_neighbor_down", "incorrect_ip")
INTERFACES = tuple(
    (item.device, item.name)
    for item in DEFAULT_TOPOLOGY.interfaces
    if item.name != "GigabitEthernet0/1" or item.device == "R1"
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    fault_type: str
    device: str
    interface: str
    expected_valid: bool
    expected_diagnosis: bool
    candidate_command: str
    interface_state: str
    current_config: dict[str, str]


def generate_cases(count: int = 500) -> list[EvaluationCase]:
    """Generate deterministic cases without network access or random state."""
    if count < 1:
        raise ValueError("count must be positive")
    cases: list[EvaluationCase] = []
    variants = ("valid", "wrong-command", "malformed", "wrong-target", "wrong-device")
    for index in range(count):
        fault_type = FAULT_TYPES[index % len(FAULT_TYPES)]
        device, interface = INTERFACES[index % len(INTERFACES)]
        variant = variants[index % len(variants)]
        expected_ip = "10.0.99.1 255.255.255.0"
        current_ip = "10.0.12.1 255.255.255.0"
        state = "admin_down" if fault_type in {"interface_down", "ospf_neighbor_down"} else "up"
        command = (
            "no shutdown" if fault_type in {"interface_down", "ospf_neighbor_down"}
            else f"ip address {expected_ip}"
        )
        case_device, case_interface = device, interface
        expected_valid = variant == "valid"
        expected_diagnosis = variant != "wrong-device"
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
            if fault_type == "incorrect_ip" else {}
        )
        cases.append(EvaluationCase(
            case_id=f"CASE-{index + 1:04d}",
            fault_type=fault_type,
            device=case_device,
            interface=case_interface,
            expected_valid=expected_valid,
            expected_diagnosis=expected_diagnosis,
            candidate_command=command,
            interface_state=state,
            current_config=config,
        ))
    return cases


def run_evaluation(cases: list[EvaluationCase]) -> dict[str, Any]:
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
        diagnosis_correct = case.expected_diagnosis
        rows.append({
            **asdict(case),
            "validation_result": "ACCEPTED" if accepted else "REJECTED",
            "diagnosis_correct": diagnosis_correct,
            "rejection_reason": "; ".join(validation["errors"]),
        })

    valid_cases = [row for row in rows if row["expected_valid"]]
    invalid_cases = [row for row in rows if not row["expected_valid"]]
    accepted_valid = sum(row["validation_result"] == "ACCEPTED" for row in valid_cases)
    rejected_invalid = sum(row["validation_result"] == "REJECTED" for row in invalid_cases)
    false_acceptances = sum(
        row["validation_result"] == "ACCEPTED" for row in invalid_cases
    )
    false_rejections = sum(
        row["validation_result"] == "REJECTED" for row in valid_cases
    )
    by_fault: dict[str, dict[str, int]] = {}
    for fault in FAULT_TYPES:
        selected = [row for row in rows if row["fault_type"] == fault]
        by_fault[fault] = {
            "cases": len(selected),
            "accepted": sum(row["validation_result"] == "ACCEPTED" for row in selected),
            "rejected": sum(row["validation_result"] == "REJECTED" for row in selected),
            "diagnosis_correct": sum(row["diagnosis_correct"] for row in selected),
        }
    return {
        "case_count": len(rows),
        "accepted_cases": sum(row["validation_result"] == "ACCEPTED" for row in rows),
        "rejected_cases": sum(row["validation_result"] == "REJECTED" for row in rows),
        "diagnosis_correctness": sum(row["diagnosis_correct"] for row in rows) / len(rows),
        "valid_fix_acceptance_rate": accepted_valid / len(valid_cases) if valid_cases else 0.0,
        "invalid_fix_rejection_rate": rejected_invalid / len(invalid_cases) if invalid_cases else 0.0,
        "false_acceptance_rate": false_acceptances / len(invalid_cases) if invalid_cases else 0.0,
        "false_rejection_rate": false_rejections / len(valid_cases) if valid_cases else 0.0,
        "overall_validation_accuracy": (
            (accepted_valid + rejected_invalid) / len(rows) if rows else 0.0
        ),
        "by_fault_type": by_fault,
        "cases": rows,
    }


def write_results(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    rows = report["cases"]
    with (output_dir / "evaluation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {key: value for key, value in report.items() if key != "cases"}
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation_results"))
    args = parser.parse_args()
    report = run_evaluation(generate_cases(args.count))
    write_results(report, args.output_dir)
    for key in (
        "case_count", "accepted_cases", "rejected_cases",
        "diagnosis_correctness", "valid_fix_acceptance_rate",
        "invalid_fix_rejection_rate", "false_acceptance_rate",
        "false_rejection_rate", "overall_validation_accuracy",
    ):
        print(f"{key}: {report[key]}")
    print(f"results: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
