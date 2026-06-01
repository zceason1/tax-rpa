import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.runtime_metadata import RuntimeMetadata
from tax_rpa.jobs.runner import JobRunner


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(root: Path) -> Path:
    input_dir = root / "input"
    input_dir.mkdir()
    person_file = input_dir / "person.xlsx"
    salary_file = input_dir / "salary.xlsx"
    person_file.write_bytes(b"person")
    salary_file.write_bytes(b"salary")
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "job_id": "202605-runtime",
                "idempotency_key": "company-tax-period-runtime",
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
        ),
        encoding="utf-8",
    )
    return manifest_path


class RuntimeMetadataTests(unittest.TestCase):
    def test_runtime_metadata_defaults_unknown_for_unreadable_version_values(self):
        metadata = RuntimeMetadata.collect(
            script_version_reader=lambda: None,
            git_commit_reader=lambda: "",
            tax_client_version_reader=lambda: (_ for _ in ()).throw(RuntimeError("no window")),
            ocr_engine_version_reader=lambda: None,
            screen_reader=lambda: {},
            windows_user_reader=lambda: "runner",
        )

        self.assertEqual(metadata.script_version, "unknown")
        self.assertEqual(metadata.git_commit, "unknown")
        self.assertEqual(metadata.tax_client_version, "unknown")
        self.assertEqual(metadata.ocr_engine_version, "unknown")
        self.assertEqual(metadata.windows_user, "runner")
        self.assertEqual(metadata.resolution, {"width": None, "height": None})
        self.assertIsNone(metadata.dpi)

    def test_job_runner_summary_records_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                runtime_metadata_collector=lambda: RuntimeMetadata(
                    script_version="phase7-test",
                    git_commit="abc123",
                    tax_client_version="tax-client-2026.05",
                    ocr_engine_version="rapidocr-1.0",
                    windows_user="runner",
                    resolution={"width": 1920, "height": 1080},
                    dpi=96,
                ),
            ).run(manifest_path)

        self.assertEqual(summary["runtime"]["script_version"], "phase7-test")
        self.assertEqual(summary["runtime"]["git_commit"], "abc123")
        self.assertEqual(summary["runtime"]["tax_client_version"], "tax-client-2026.05")
        self.assertEqual(summary["runtime"]["ocr_engine_version"], "rapidocr-1.0")
        self.assertEqual(summary["runtime"]["windows_user"], "runner")
        self.assertEqual(summary["runtime"]["resolution"], {"width": 1920, "height": 1080})
        self.assertEqual(summary["runtime"]["dpi"], 96)


if __name__ == "__main__":
    unittest.main()
