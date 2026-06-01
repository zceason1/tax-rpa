import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.artifact_store import ArtifactPathError, ArtifactStore


class ArtifactStoreTests(unittest.TestCase):
    def test_create_job_artifact_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")

            artifacts.initialize()

            self.assertTrue((Path(temp_dir) / "202605-001").is_dir())
            self.assertTrue(artifacts.logs_dir.is_dir())
            self.assertTrue(artifacts.screenshots_dir.is_dir())
            self.assertTrue(artifacts.ocr_dir.is_dir())
            self.assertTrue(artifacts.exported_dir.is_dir())
            self.assertTrue(artifacts.input_dir.is_dir())

    def test_write_json_returns_job_relative_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()

            relative_path = artifacts.write_json(
                "summary.json",
                {"job_id": "202605-001", "path": Path("input/file.xlsx")},
            )

            self.assertEqual(relative_path, "summary.json")
            data = json.loads((artifacts.root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["job_id"], "202605-001")
            self.assertEqual(data["path"], "input/file.xlsx")

    def test_write_json_rejects_paths_outside_job_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()

            with self.assertRaises(ArtifactPathError):
                artifacts.write_json("../outside.json", {"bad": True})


if __name__ == "__main__":
    unittest.main()
