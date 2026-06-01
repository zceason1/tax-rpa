import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.canary import CanaryRunner, CanaryTarget
from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.production_gate import ProductionGate
from tax_rpa.jobs.submit_authorization import SubmitAuthorization


def manifest(**overrides) -> JobManifest:
    data = {
        "job_id": "202605-gate",
        "idempotency_key": "company-tax-period-gate",
        "company_name": "ExampleCo",
        "credit_code": "91440300ABCDEF1234",
        "tax_period": "2026-05",
        "person_action": "import_file",
        "run_mode": "submit",
        "submit_enabled": True,
        "files": {
            "person_info": {"path": "input/person.xlsx", "sha256": "a" * 64},
            "salary_income": {"path": "input/salary.xlsx", "sha256": "b" * 64},
        },
    }
    data.update(overrides)
    return JobManifest.from_dict(data)


def write_switch(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "enabled": True,
                "approved_by": "tax-owner",
                "approved_at": "2026-05-24T16:00:00+08:00",
            }
        ),
        encoding="utf-8",
    )


def write_canary(path: Path, *, run_mode: str, passed: bool, review_status: str = "approved") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_mode": run_mode,
                "passed": passed,
                "tax_client_version": "tax-client-2026.05",
                "review": {
                    "status": review_status,
                    "approved_by": "qa",
                    "approved_at": "2026-05-24T16:05:00+08:00",
                },
                "targets": [],
            }
        ),
        encoding="utf-8",
    )


def write_checklist(
    path: Path,
    *,
    inspect_record: Path,
    execute_record: Path,
    calibration_gate_passed: bool = True,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "self_check_passed": True,
                "tax_client_version": "tax-client-2026.05",
                "inspect_only_canary_record": inspect_record.as_posix(),
                "execute_no_send_canary_record": execute_record.as_posix(),
                "calibration_gate_passed": calibration_gate_passed,
                "review": {
                    "status": "approved",
                    "approved_by": "tax-owner",
                    "approved_at": "2026-05-24T16:10:00+08:00",
                },
            }
        ),
        encoding="utf-8",
    )


class CanaryAndProductionGateTests(unittest.TestCase):
    def test_canary_runner_writes_pass_record_without_clicking_submit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = CanaryRunner(
                artifacts_root=root,
                timestamp="20260524_160000",
                tax_client_version_reader=lambda: "tax-client-2026.05",
                probe=lambda target: {
                    "found": True,
                    "score": 0.91,
                    "ocr_text": target.label,
                },
            )

            result = runner.run(
                run_mode="inspect_only",
                targets=[
                    CanaryTarget(
                        target_id="personnel_import.page_marker",
                        label="personnel page",
                        target_type="page_marker",
                        owner_module="tax_rpa.pages.person_info.elements.page_markers",
                    )
                ],
            )
            record = json.loads((root / result.record_path).read_text(encoding="utf-8"))

        self.assertTrue(result.passed)
        self.assertEqual(result.record_path, "canary/20260524_160000/canary_record.json")
        self.assertTrue(record["targets"][0]["found"])
        self.assertFalse(record["submit_clicked"])

    def test_failed_canary_writes_maintenance_ticket(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = CanaryRunner(
                artifacts_root=root,
                timestamp="20260524_160100",
                probe=lambda _target: {"found": False, "score": 0.12, "ocr_text": ""},
            ).run(
                run_mode="execute_no_send",
                targets=[
                    CanaryTarget(
                        target_id="tax_calculation.continue_button",
                        label="continue tax calculation",
                        target_type="button",
                        owner_module="tax_rpa.pages.comprehensive_income.elements.tax_calculation",
                    )
                ],
            )
            ticket = json.loads((root / result.maintenance_ticket_path).read_text(encoding="utf-8"))

        self.assertFalse(result.passed)
        self.assertEqual(ticket["failed_targets"][0]["target_id"], "tax_calculation.continue_button")
        self.assertEqual(
            ticket["failed_targets"][0]["suggested_element_module"],
            "tax_rpa.pages.comprehensive_income.elements.tax_calculation",
        )

    def test_production_gate_denies_until_canary_artifacts_pass_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inspect_record = root / "canary" / "inspect" / "canary_record.json"
            execute_record = root / "canary" / "execute" / "canary_record.json"
            write_canary(inspect_record, run_mode="inspect_only", passed=True)
            write_canary(execute_record, run_mode="execute_no_send", passed=False)
            checklist_path = root / "submit_enablement_checklist.json"
            write_checklist(
                checklist_path,
                inspect_record=inspect_record,
                execute_record=execute_record,
            )

            result = ProductionGate(
                checklist_path=checklist_path,
                tax_client_version_reader=lambda: "tax-client-2026.05",
            ).evaluate()

        self.assertFalse(result.allowed)
        self.assertIn("execute_no_send_canary_record", result.missing_gates)
        self.assertEqual(result.error_type, "SUBMIT_NOT_AUTHORIZED")

    def test_submit_authorization_includes_production_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            switch_path = root / "production_submit_enabled.json"
            checklist_path = root / "missing_checklist.json"
            write_switch(switch_path)

            result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=True,
                windows_user="runner",
                production_gate=ProductionGate(
                    checklist_path=checklist_path,
                    tax_client_version_reader=lambda: "tax-client-2026.05",
                ),
            ).authorize(
                manifest(),
                step_name="declaration.submit",
                label="send declaration",
            )

        self.assertFalse(result.allowed)
        self.assertIn("production_gate", result.missing_gates)

    def test_submit_authorization_allows_when_production_gate_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            switch_path = root / "production_submit_enabled.json"
            inspect_record = root / "canary" / "inspect" / "canary_record.json"
            execute_record = root / "canary" / "execute" / "canary_record.json"
            checklist_path = root / "submit_enablement_checklist.json"
            write_switch(switch_path)
            write_canary(inspect_record, run_mode="inspect_only", passed=True)
            write_canary(execute_record, run_mode="execute_no_send", passed=True)
            write_checklist(
                checklist_path,
                inspect_record=inspect_record,
                execute_record=execute_record,
            )

            result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=True,
                windows_user="runner",
                production_gate=ProductionGate(
                    checklist_path=checklist_path,
                    tax_client_version_reader=lambda: "tax-client-2026.05",
                ),
            ).authorize(
                manifest(),
                step_name="declaration.submit",
                label="send declaration",
            )

        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.permit)
        self.assertEqual(result.missing_gates, [])


if __name__ == "__main__":
    unittest.main()
