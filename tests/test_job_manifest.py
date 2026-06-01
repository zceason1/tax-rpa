import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.manifest import (
    JobManifest,
    ManifestValidationError,
    load_job_manifest,
)


def valid_manifest(**overrides):
    data = {
        "job_id": "202605-001",
        "idempotency_key": "company-tax-period-flow-v1",
        "company_name": "ExampleCo",
        "credit_code": "91440300ABCDEF1234",
        "tax_period": "202605",
        "person_action": "import_file",
        "run_mode": "execute_no_send",
        "submit_enabled": False,
        "files": {
            "person_info": {
                "path": "input/202605_ExampleCo_91440300ABCDEF1234_PERSON_INFO_v1.xlsx",
                "sha256": "a" * 64,
            },
            "salary_income": {
                "path": "input/202605_ExampleCo_91440300ABCDEF1234_SALARY_INCOME_v1.xlsx",
                "sha256": "b" * 64,
            },
        },
        "operator_note": "preserve me",
    }
    data.update(overrides)
    return data


class JobManifestTests(unittest.TestCase):
    def test_load_manifest_normalizes_tax_period_and_preserves_extra_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(valid_manifest(), ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = load_job_manifest(manifest_path)

        self.assertIsInstance(manifest, JobManifest)
        self.assertEqual(manifest.tax_period, "2026-05")
        self.assertEqual(manifest.run_mode, "execute_no_send")
        self.assertFalse(manifest.submit_enabled)
        self.assertEqual(manifest.manifest_extra, {"operator_note": "preserve me"})
        self.assertEqual(
            manifest.files["person_info"].path,
            Path("input/202605_ExampleCo_91440300ABCDEF1234_PERSON_INFO_v1.xlsx"),
        )

    def test_missing_required_field_fails_as_material_invalid(self):
        data = valid_manifest()
        del data["job_id"]

        with self.assertRaises(ManifestValidationError) as cm:
            JobManifest.from_dict(data)

        self.assertEqual(cm.exception.error_type, "MATERIAL_INVALID")
        self.assertEqual(cm.exception.error_code, "manifest_missing_required_field")

    def test_add_person_is_reserved_but_unsupported_in_phase_1(self):
        data = valid_manifest(person_action="add_person", person_type="domestic")

        with self.assertRaises(ManifestValidationError) as cm:
            JobManifest.from_dict(data)

        self.assertEqual(cm.exception.error_type, "UNSUPPORTED_ACTION")
        self.assertEqual(cm.exception.error_code, "person_action_add_person_unsupported")

    def test_invalid_run_mode_fails_as_material_invalid(self):
        data = valid_manifest(run_mode="debug")

        with self.assertRaises(ManifestValidationError) as cm:
            JobManifest.from_dict(data)

        self.assertEqual(cm.exception.error_type, "MATERIAL_INVALID")
        self.assertEqual(cm.exception.error_code, "manifest_invalid_run_mode")

    def test_required_import_files_must_include_person_and_salary(self):
        data = valid_manifest(files={"person_info": valid_manifest()["files"]["person_info"]})

        with self.assertRaises(ManifestValidationError) as cm:
            JobManifest.from_dict(data)

        self.assertEqual(cm.exception.error_type, "MATERIAL_INVALID")
        self.assertEqual(cm.exception.error_code, "manifest_missing_file_role")


if __name__ == "__main__":
    unittest.main()
