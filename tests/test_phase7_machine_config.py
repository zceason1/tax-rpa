import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.machine_config import MachineConfigValidator, load_machine_config
from tax_rpa.jobs.runner import JobRunner


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_valid_machine_config(path: Path, app_path: Path | None = None) -> None:
    app_path = app_path or path.parent / "client.lnk"
    app_path.write_text("shortcut", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "app": {
                    "app_path": app_path.as_posix(),
                    "process_name": "EPPortalITS.exe",
                    "launch_timeout_seconds": 60,
                    "login_timeout_seconds": 300,
                    "window_timeout_seconds": 90,
                },
                "screen": {
                    "required_width": 1920,
                    "required_height": 1080,
                    "required_dpi": 96,
                },
                "ocr": {
                    "engine": "rapidocr",
                    "default_score_threshold": 0.35,
                },
                "artifacts": {
                    "root": "artifacts/jobs",
                    "min_free_gb": 10,
                    "retention_success_days": 30,
                    "retention_failed_days": 90,
                },
                "callback": {
                    "timeout_seconds": 10,
                    "retry_window_hours": 24,
                    "secret_credential_name": "tax-rpa-callback-secret",
                },
                "submit": {
                    "production_switch_path": "config/production_submit_enabled.json",
                },
            }
        ),
        encoding="utf-8",
    )


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
                "job_id": "202605-phase7",
                "idempotency_key": "company-tax-period-phase7",
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


class MachineConfigTests(unittest.TestCase):
    def test_load_machine_config_validates_required_shape_and_redacts_summary_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "machine_config.json"
            write_valid_machine_config(config_path)

            config = load_machine_config(config_path)

        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.ocr_engine, "rapidocr")
        summary_copy = config.to_summary_dict()
        self.assertEqual(
            summary_copy["callback"]["secret_credential_name"],
            "[REDACTED]",
        )

    def test_machine_config_validator_reports_missing_config_as_system_environment_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = MachineConfigValidator(Path(temp_dir) / "missing.json").validate()

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].error_type, "SYSTEM_ENVIRONMENT_ERROR")
        self.assertEqual(result.issues[0].error_code, "machine_config_missing")

    def test_job_runner_fails_preflight_when_required_machine_config_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = write_manifest(root)

            def executor(_manifest, _artifacts):
                raise AssertionError("executor must not run without machine config")

            summary = JobRunner(
                artifacts_root=root / "artifacts",
                lock_path=root / "runner.lock.json",
                executor=executor,
                machine_config_path=root / "missing_machine_config.json",
            ).run(manifest_path)

        self.assertEqual(summary["state"], "failed")
        self.assertEqual(summary["error_type"], "SYSTEM_ENVIRONMENT_ERROR")
        self.assertEqual(summary["error_code"], "machine_config_missing")


if __name__ == "__main__":
    unittest.main()
