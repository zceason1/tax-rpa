import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.calibration import (
    CalibrationGate,
    REQUIRED_EXECUTE_NO_SEND_STEPS,
)


def write_step_calibration(
    root: Path,
    *,
    tax_client_version: str,
    step_name: str,
    submit_result_texts: bool = False,
) -> None:
    step_dir = root / tax_client_version / step_name
    step_dir.mkdir(parents=True, exist_ok=True)
    element = {
        "page_name": step_name,
        "tax_client_version": tax_client_version,
        "element_id": f"{step_name}.marker",
        "ui_text": f"{step_name} marker",
        "aliases": [],
        "element_type": "page_marker",
        "region_hint": "content",
        "unknown_behavior": "stop",
        "sample_screenshot": "screenshots/sample.png",
        "sample_ocr_json": "ocr/sample.json",
        "min_score": 0.35,
        "owner_module": f"tax_rpa.pages.{step_name}.elements.page_markers",
    }
    elements = [element]
    if submit_result_texts:
        elements.append(
            {
                **element,
                "element_id": "declaration_submission.result_text",
                "element_type": "result_text",
                "success_texts": ["submitted"],
                "failure_texts": ["failed"],
            }
        )
    (step_dir / "element_calibration.json").write_text(
        json.dumps(elements),
        encoding="utf-8",
    )


class CalibrationGateTests(unittest.TestCase):
    def test_fake_driver_runs_do_not_require_real_client_calibration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = CalibrationGate(Path(temp_dir)).evaluate(
                run_mode="execute_no_send",
                tax_client_version="unknown",
                real_client=False,
            )

        self.assertTrue(result.allowed)
        self.assertEqual(result.status, "skipped_for_fake_driver")

    def test_real_execute_no_send_is_blocked_until_every_required_step_has_calibration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_step_calibration(
                root,
                tax_client_version="tax-client-2026.05",
                step_name=REQUIRED_EXECUTE_NO_SEND_STEPS[0],
            )

            result = CalibrationGate(root).evaluate(
                run_mode="execute_no_send",
                tax_client_version="tax-client-2026.05",
                real_client=True,
            )

        self.assertFalse(result.allowed)
        self.assertIn(REQUIRED_EXECUTE_NO_SEND_STEPS[1], result.missing_steps)
        self.assertEqual(result.error_type, "SUBMIT_NOT_AUTHORIZED")
        self.assertEqual(result.error_code, "calibration_missing")

    def test_real_submit_requires_declaration_submission_success_and_failure_texts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for step_name in REQUIRED_EXECUTE_NO_SEND_STEPS:
                write_step_calibration(
                    root,
                    tax_client_version="tax-client-2026.05",
                    step_name=step_name,
                )

            blocked = CalibrationGate(root).evaluate(
                run_mode="submit",
                tax_client_version="tax-client-2026.05",
                real_client=True,
            )
            write_step_calibration(
                root,
                tax_client_version="tax-client-2026.05",
                step_name="declaration_submission",
                submit_result_texts=True,
            )
            allowed = CalibrationGate(root).evaluate(
                run_mode="submit",
                tax_client_version="tax-client-2026.05",
                real_client=True,
            )

        self.assertFalse(blocked.allowed)
        self.assertIn("declaration_submission.result_text", blocked.missing_elements)
        self.assertTrue(allowed.allowed)


if __name__ == "__main__":
    unittest.main()
