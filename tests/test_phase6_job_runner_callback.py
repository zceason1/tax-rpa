import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.callback_outbox import CallbackTransportResponse
from tax_rpa.jobs.runner import JobRunner


class Phase6JobRunnerCallbackTests(unittest.TestCase):
    def test_callback_failure_keeps_business_state_succeeded_and_creates_outbox(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root, callback_url="https://middle-platform.example/callback")

            def executor(_manifest, _artifacts):
                return {
                    "ok": True,
                    "workflow_status": "ready_to_submit_not_sent",
                    "business_status": "phase5_workflows_completed",
                    "current_step": "comprehensive_income.export_report",
                }

            def transport(_url, _payload, _headers, _timeout_seconds):
                return CallbackTransportResponse(status_code=500, body="bad gateway")

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=executor,
                callback_transport=transport,
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            state = json.loads((job_root / "state.json").read_text(encoding="utf-8"))
            index = json.loads(
                (job_root / "troubleshooting_index.json").read_text(encoding="utf-8")
            )
            callback_record = json.loads(
                (job_root / "callback_outbox.json").read_text(encoding="utf-8")
            )
            artifact_manifest = json.loads(
                (job_root / "artifact_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(summary["state"], "succeeded")
        self.assertEqual(summary["business_status"], "phase5_workflows_completed")
        self.assertEqual(summary["callback_state"], "pending")
        self.assertIsNone(summary["error"])
        self.assertEqual(state["state"], "succeeded")
        self.assertEqual(state["callback_delivery_state"], "pending")
        self.assertEqual(index["callback_outbox_record"], "callback_outbox.json")
        self.assertEqual(callback_record["callback_state"], "pending")
        self.assertEqual(callback_record["payload"]["summary_path"], "summary.json")
        self.assertEqual(
            callback_record["payload"]["artifact_manifest_path"],
            "artifact_manifest.json",
        )
        self.assertEqual(artifact_manifest["callback_status"], "pending")

    def test_job_without_callback_url_marks_callback_not_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=lambda _manifest, _artifacts: {"workflow_status": "fake_completed"},
            ).run(manifest_path)

        self.assertEqual(summary["state"], "succeeded")
        self.assertEqual(summary["callback_state"], "not_configured")


def write_manifest(root: Path, callback_url: str | None = None) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    person_file = input_dir / "person.xlsx"
    salary_file = input_dir / "salary.xlsx"
    person_file.write_bytes(b"person")
    salary_file.write_bytes(b"salary")
    data = {
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
                "path": "input/person.xlsx",
                "sha256": sha256_file(person_file),
            },
            "salary_income": {
                "path": "input/salary.xlsx",
                "sha256": sha256_file(salary_file),
            },
        },
    }
    if callback_url:
        data["callback_url"] = callback_url
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return manifest_path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
