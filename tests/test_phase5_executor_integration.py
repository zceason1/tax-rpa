import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.testing.self_check_app import (
    SelfCheckApp,
    SelfCheckComprehensiveIncomePage,
    SelfCheckShell,
)
from tax_rpa.jobs.existing_workflow_executor import ExistingWorkflowExecutor
from tax_rpa.jobs.runner import JobRunner
from tax_rpa.runtime.result import StepResult


class Phase5ExecutorIntegrationTests(unittest.TestCase):
    def test_phase5_execute_no_send_self_check_reaches_export_attempt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=ExistingWorkflowExecutor(
                    base_dir=root,
                    app_factory=lambda config, logger: SelfCheckApp(config, logger),
                    include_phase5=True,
                ),
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            step_events = [
                json.loads(line)
                for line in (job_root / "logs" / "steps.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(summary["state"], "succeeded")
        self.assertEqual(summary["executor_result"]["workflow_status"], "not_available_before_submit")
        self.assertEqual(
            summary["executor_result"]["business_status"],
            "phase5_workflows_completed",
        )
        self.assertEqual(step_events[-1]["result_matrix"]["matrix_step"], "export_report")
        self.assertEqual(step_events[-1]["result_matrix"]["outcome"], "success")
        self.assertEqual(step_events[-1]["status"], "not_available_before_submit")

    def test_phase5_blocked_tax_calculation_stops_before_declaration_and_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=ExistingWorkflowExecutor(
                    base_dir=root,
                    app_factory=lambda config, logger: BlockedTaxCalculationApp(config, logger),
                    include_phase5=True,
                ),
                screenshot_grabber=lambda path: path.write_bytes(b"fake-png"),
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            step_events = [
                json.loads(line)
                for line in (job_root / "logs" / "steps.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(summary["state"], "failed")
        self.assertEqual(summary["error_type"], "BLOCKED_BY_UNEXPECTED_DIALOG")
        self.assertEqual(summary["error_code"], "unexpected_dialog")
        self.assertEqual(step_events[-1]["result_matrix"]["matrix_step"], "tax_calculation")
        self.assertEqual(step_events[-1]["result_matrix"]["outcome"], "blocked")
        self.assertNotIn(
            "declaration_submission_readiness",
            [event["result_matrix"]["matrix_step"] for event in step_events if event.get("result_matrix")],
        )
        self.assertNotIn(
            "export_report",
            [event["result_matrix"]["matrix_step"] for event in step_events if event.get("result_matrix")],
        )


class BlockedTaxCalculationApp(SelfCheckApp):
    def shell(self):
        return BlockedTaxCalculationShell()


class BlockedTaxCalculationShell(SelfCheckShell):
    def open_comprehensive_income_page(self):
        return BlockedTaxCalculationPage()


class BlockedTaxCalculationPage(SelfCheckComprehensiveIncomePage):
    def read_tax_calculation_popup(self):
        return StepResult(
            ok=False,
            name="self_check.tax_calculation_popup",
            status="blocked",
            error="Unexpected tax calculation popup",
            error_type="BLOCKED_BY_UNEXPECTED_DIALOG",
            error_code="unexpected_dialog",
            ui_text=["manual review required"],
        )


def write_manifest(root: Path) -> Path:
    person_file = root / "person.xlsx"
    salary_file = root / "salary.xlsx"
    person_file.write_bytes(b"person")
    salary_file.write_bytes(b"salary")
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "job_id": "202605-001",
                "idempotency_key": "company-tax-period-flow-v1",
                "company_name": "ExampleCo",
                "credit_code": "91440300ABCDEF1234",
                "tax_period": "2026-05",
                "person_action": "import_file",
                "run_mode": "execute_no_send",
                "submit_enabled": False,
                "files": {
                    "person_info": {
                        "path": "person.xlsx",
                        "sha256": sha256_file(person_file),
                    },
                    "salary_income": {
                        "path": "salary.xlsx",
                        "sha256": sha256_file(salary_file),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
