from dataclasses import replace
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from ai_engine import GEMINI_RESPONSE_SCHEMA, DiagnosisResult, diagnose_event
from log_preprocessor import parse_logs


class DiagnoseEventTests(unittest.TestCase):
    def setUp(self) -> None:
        events = parse_logs(
            "%LINK-3-UPDOWN: Interface GigabitEthernet0/1 is down",
            device_id="router1",
        )
        self.event = events[0]

    def test_returns_pydantic_contract_using_injected_client(self) -> None:
        expected = DiagnosisResult(
            event_id=self.event.event_id,
            device_id="router1",
            target_interface="GigabitEthernet0/1",
            detected_fault="Interface is down; administrative state is unknown",
            candidate_command="",
            confidence_score=0.0,
        )
        generate_content = Mock(
            return_value=SimpleNamespace(parsed=expected, text=expected.model_dump_json())
        )
        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        )

        result = diagnose_event(self.event, client=client)

        self.assertEqual(result, expected)
        self.assertEqual(
            set(result.model_dump()),
            {
                "event_id",
                "device_id",
                "target_interface",
                "detected_fault",
                "candidate_command",
                "confidence_score",
            },
        )
        config = generate_content.call_args.kwargs["config"]
        self.assertEqual(config.response_schema, GEMINI_RESPONSE_SCHEMA)
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertNotIn("additionalProperties", str(config.response_schema))

    def test_gemini_schema_declares_exact_contract_fields(self) -> None:
        self.assertEqual(GEMINI_RESPONSE_SCHEMA["type"], "object")
        self.assertEqual(
            set(GEMINI_RESPONSE_SCHEMA["properties"]),
            {
                "event_id",
                "device_id",
                "target_interface",
                "detected_fault",
                "candidate_command",
                "confidence_score",
            },
        )
        self.assertEqual(
            set(GEMINI_RESPONSE_SCHEMA["required"]),
            set(GEMINI_RESPONSE_SCHEMA["properties"]),
        )
        self.assertNotIn("additionalProperties", GEMINI_RESPONSE_SCHEMA)

    def test_pydantic_contract_rejects_extra_fields_and_invalid_confidence(self) -> None:
        valid = {
            "event_id": self.event.event_id,
            "device_id": "router1",
            "target_interface": "GigabitEthernet0/1",
            "detected_fault": "Interface is down",
            "candidate_command": "",
            "confidence_score": 0.0,
        }

        with self.assertRaises(ValidationError):
            DiagnosisResult.model_validate({**valid, "unexpected": "value"})
        with self.assertRaises(ValidationError):
            DiagnosisResult.model_validate({**valid, "confidence_score": 1.1})

    def test_rejects_event_without_device_id(self) -> None:
        event_without_device = replace(self.event, device_id=None)
        with self.assertRaisesRegex(ValueError, "device_id is required"):
            diagnose_event(event_without_device, client=Mock())

    def test_rejects_model_changing_identity(self) -> None:
        incorrect = DiagnosisResult(
            event_id="different-event",
            device_id="router1",
            target_interface="GigabitEthernet0/1",
            detected_fault="Interface is down",
            candidate_command="",
            confidence_score=0.0,
        )
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kwargs: SimpleNamespace(
                    parsed=incorrect,
                    text=incorrect.model_dump_json(),
                )
            )
        )

        with self.assertRaisesRegex(ValueError, "changed the event"):
            diagnose_event(self.event, client=client)

    def test_validates_json_text_when_sdk_has_no_parsed_object(self) -> None:
        expected = DiagnosisResult(
            event_id=self.event.event_id,
            device_id="router1",
            target_interface="GigabitEthernet0/1",
            detected_fault=self.event.detected_fault,
            candidate_command="",
            confidence_score=0.0,
        )
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_kwargs: SimpleNamespace(
                    parsed=None,
                    text=expected.model_dump_json(),
                )
            )
        )

        self.assertEqual(diagnose_event(self.event, client=client), expected)


if __name__ == "__main__":
    unittest.main()
