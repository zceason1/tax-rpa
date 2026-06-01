import hashlib
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.preflight import PreflightValidator


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_for(root: Path, person_name: str = "person.xlsx", salary_name: str = "salary.xlsx") -> JobManifest:
    person_path = root / "input" / person_name
    salary_path = root / "input" / salary_name
    return JobManifest.from_dict(
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
                    "path": person_path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(person_path.read_bytes()) if person_path.exists() else "a" * 64,
                },
                "salary_income": {
                    "path": salary_path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(salary_path.read_bytes()) if salary_path.exists() else "b" * 64,
                },
            },
        }
    )


class PreflightValidatorTests(unittest.TestCase):
    def test_valid_manifest_files_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "person.xlsx").write_bytes(b"person")
            (input_dir / "salary.xlsx").write_bytes(b"salary")

            result = PreflightValidator(root).validate(manifest_for(root))

        self.assertTrue(result.ok)
        self.assertEqual(result.issues, [])

    def test_missing_file_fails_as_material_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "person.xlsx").write_bytes(b"person")
            manifest = manifest_for(root)

            result = PreflightValidator(root).validate(manifest)

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].error_type, "MATERIAL_INVALID")
        self.assertEqual(result.issues[0].error_code, "input_file_missing")

    def test_temp_suffix_fails_as_transfer_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "person.xlsx.tmp").write_bytes(b"person")
            (input_dir / "salary.xlsx").write_bytes(b"salary")
            manifest = manifest_for(root, person_name="person.xlsx.tmp")

            result = PreflightValidator(root).validate(manifest)

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].error_type, "FILE_TRANSFER_INCOMPLETE")
        self.assertEqual(result.issues[0].error_code, "file_transfer_incomplete")

    def test_checksum_mismatch_fails_as_material_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "person.xlsx").write_bytes(b"person")
            (input_dir / "salary.xlsx").write_bytes(b"salary")
            manifest = manifest_for(root)
            bad_manifest = JobManifest.from_dict(
                {
                    **manifest_for(root).__dict__,
                    "files": {
                        "person_info": {
                            "path": "input/person.xlsx",
                            "sha256": "0" * 64,
                        },
                        "salary_income": {
                            "path": "input/salary.xlsx",
                            "sha256": sha256_bytes((input_dir / "salary.xlsx").read_bytes()),
                        },
                    },
                }
            )

            result = PreflightValidator(root).validate(bad_manifest)

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].error_type, "MATERIAL_INVALID")
        self.assertEqual(result.issues[0].error_code, "input_file_checksum_mismatch")

    def test_changing_size_fails_as_transfer_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "person.xlsx").write_bytes(b"person")
            (input_dir / "salary.xlsx").write_bytes(b"salary")
            sizes = [1, 2]

            def unstable_size(_path: Path) -> int:
                return sizes.pop(0) if sizes else 2

            result = PreflightValidator(root, size_reader=unstable_size).validate(manifest_for(root))

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].error_type, "FILE_TRANSFER_INCOMPLETE")
        self.assertEqual(result.issues[0].error_code, "file_transfer_incomplete")


if __name__ == "__main__":
    unittest.main()
