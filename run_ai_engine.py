"""Run a sample diagnosis offline, or call Gemini with --live."""

from __future__ import annotations

import argparse
import sys
from types import SimpleNamespace

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import parse_logs


class _MockClient:
    """Small offline stand-in for the Gemini content-generation client."""

    def __init__(self, result: DiagnosisResult) -> None:
        self.models = SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                parsed=result,
                text=result.model_dump_json(),
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send the sample event to Gemini (requires GEMINI_API_KEY).",
    )
    args = parser.parse_args()

    sample_logs = (
        "*Oct 23 17:01:02.123: %LINK-3-UPDOWN: Interface "
        "GigabitEthernet0/1, changed state to down\n"
    )
    events = parse_logs(sample_logs, device_id="router1")
    if not events:
        raise RuntimeError("The sample log did not produce a parsed event")
    event = events[0]

    if args.live:
        print(
            "Sending sample event to Gemini (60-second timeout)...",
            file=sys.stderr,
            flush=True,
        )
        diagnosis = diagnose_event(event)
    else:
        mock_result = DiagnosisResult(
            event_id=event.event_id,
            device_id=event.device_id or "",
            target_interface=event.target_interface,
            detected_fault=event.detected_fault,
            candidate_command="",
            confidence_score=0.0,
        )
        diagnosis = diagnose_event(event, client=_MockClient(mock_result))

    print(diagnosis.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
