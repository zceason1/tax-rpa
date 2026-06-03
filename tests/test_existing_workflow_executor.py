import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.testing.self_check_app import SelfCheckApp
from tax_rpa.jobs.existing_workflow_executor import ExistingWorkflowExecutor
from tax_rpa.jobs.runner import JobRunner
from tax_rpa.runtime.result import StepResult


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


class ExistingWorkflowExecutorTests(unittest.TestCase):
    def test_job_runner_execute_no_send_self_check_reaches_salary_import_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=ExistingWorkflowExecutor(
                    base_dir=root,
                    app_factory=lambda config, logger: SelfCheckApp(config, logger),
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
        self.assertEqual(summary["executor_result"]["workflow_status"], "success")
        self.assertEqual(
            summary["executor_result"]["business_status"],
            "existing_workflows_completed",
        )
        self.assertEqual(step_events[-1]["result_matrix"]["matrix_step"], "salary_income_import")
        self.assertEqual(step_events[-1]["result_matrix"]["outcome"], "success")

    def test_job_runner_marks_unknown_import_result_as_failed_business_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=ExistingWorkflowExecutor(
                    base_dir=root,
                    app_factory=lambda config, logger: UnknownPersonImportApp(config, logger),
                ),
                screenshot_grabber=lambda path: path.write_bytes(b"fake-png"),
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            failed = json.loads(
                (job_root / "logs" / "failed.json").read_text(encoding="utf-8")
            )

        self.assertEqual(summary["state"], "failed")
        self.assertEqual(summary["error_type"], "UNKNOWN_RESULT")
        self.assertEqual(summary["error_code"], "person_import_result_unknown")
        self.assertEqual(
            summary["executor_result"]["workflow_status"],
            "unknown",
        )
        self.assertEqual(failed["error"]["type"], "UNKNOWN_RESULT")


class UnknownPersonImportApp(SelfCheckApp):
    def shell(self):
        return UnknownPersonImportShell()


class UnknownPersonImportShell:
    def open_person_info_page(self):
        return UnknownPersonImportPage()


class UnknownPersonImportPage:
    def step(self, _name, **_data):
        from contextlib import nullcontext

        return nullcontext()

    def close_message_dialog_if_present(self):
        return StepResult(ok=True, name="message_dialog", status="none")

    def click_import_button(self):
        return StepResult(ok=True, name="click_import_button", status="clicked")

    def choose_import_file_option(self):
        return StepResult(
            ok=True,
            name="choose_import_file_option",
            status="selected",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_person_file(self, path, _dropdown_result):
        return StepResult(
            ok=True,
            name="choose_person_file",
            status="submitted",
            evidence={"file_path": str(path)},
        )

    def read_import_result(self):
        return StepResult(
            ok=False,
            name="wait_import_result",
            status="unknown",
            error="Personnel import result was not recognized",
            error_type="UNKNOWN_RESULT",
            error_code="person_import_result_unknown",
            side_effect_started=True,
            side_effect_committed=True,
        )


if __name__ == "__main__":
    unittest.main()
