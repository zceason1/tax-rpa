import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.runner import JobRunner


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(root: Path, include_salary: bool = True) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    person_file = input_dir / "person.xlsx"
    salary_file = input_dir / "salary.xlsx"
    person_file.write_bytes(b"person")
    if include_salary:
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
                        "path": "input/person.xlsx",
                        "sha256": sha256_file(person_file),
                    },
                    "salary_income": {
                        "path": "input/salary.xlsx",
                        "sha256": sha256_file(salary_file) if salary_file.exists() else "b" * 64,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


class JobRunnerTests(unittest.TestCase):
    def test_fake_job_validates_locks_writes_state_and_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            calls = []

            def executor(manifest, artifacts):
                calls.append((manifest.job_id, artifacts.root.name))
                return {"workflow_status": "fake_completed"}

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=executor,
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            transitions = (job_root / "logs" / "state_transitions.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(summary["state"], "succeeded")
            self.assertEqual(calls, [("202605-001", "202605-001")])
            self.assertTrue((job_root / "state.json").exists())
            self.assertTrue((job_root / "summary.json").exists())
            self.assertTrue((root / "runner.lock.json").exists())
            self.assertEqual(
                [json.loads(line)["to_state"] for line in transitions],
                ["received", "validating", "queued", "running", "succeeded"],
            )

    def test_preflight_failure_fails_job_without_calling_executor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root, include_salary=False)

            def executor(_manifest, _artifacts):
                raise AssertionError("executor must not run after preflight failure")

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=executor,
            ).run(manifest_path)

            transitions = (
                root
                / "artifacts"
                / "202605-001"
                / "logs"
                / "state_transitions.jsonl"
            ).read_text(encoding="utf-8").splitlines()

            self.assertEqual(summary["state"], "failed")
            self.assertEqual(summary["error_type"], "MATERIAL_INVALID")
            self.assertEqual(summary["error_code"], "input_file_missing")
            self.assertEqual(
                [json.loads(line)["to_state"] for line in transitions],
                ["received", "validating", "failed"],
            )

    def test_executor_failure_writes_troubleshooting_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)
            screenshots = []

            def executor(_manifest, _artifacts):
                raise RuntimeError("forced failure")

            def screenshot_grabber(path: Path) -> None:
                screenshots.append(path)
                path.write_bytes(b"fake-png")

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=executor,
                screenshot_grabber=screenshot_grabber,
            ).run(manifest_path)

            job_root = root / "artifacts" / "202605-001"
            index = json.loads(
                (job_root / "troubleshooting_index.json").read_text(encoding="utf-8")
            )
            failed = json.loads(
                (job_root / "logs" / "failed.json").read_text(encoding="utf-8")
            )

            self.assertEqual(summary["state"], "failed")
            self.assertEqual(summary["error_code"], "job_executor_failed")
            self.assertEqual(
                summary["primary_failure_screenshot"],
                "screenshots/job_executor_failed.png",
            )
            self.assertEqual(
                summary["artifacts"]["troubleshooting_index"],
                "troubleshooting_index.json",
            )
            self.assertEqual(screenshots[0].name, "job_executor_failed.png")
            self.assertTrue((job_root / index["primary_failure_screenshot"]).exists())
            self.assertEqual(index["summary"], "summary.json")
            self.assertEqual(index["state"], "state.json")
            self.assertEqual(
                index["primary_failure_screenshot"],
                "screenshots/job_executor_failed.png",
            )
            self.assertEqual(index["latest_action_event"]["event"], "executor_failed")
            self.assertEqual(
                index["current_step_journal_entry"]["event"],
                "step_failed",
            )
            self.assertEqual(failed["error"]["code"], "job_executor_failed")
            self.assertIn("RuntimeError", failed["traceback"])
            self.assertEqual(failed["state_snapshot"]["state"], "failed")
            self.assertEqual(
                failed["latest_action_event"]["event"],
                "executor_failed",
            )


if __name__ == "__main__":
    unittest.main()
