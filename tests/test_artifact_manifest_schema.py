import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.artifact_manifest import ArtifactManifestWriter
from tax_rpa.jobs.artifact_store import ArtifactStore


class ArtifactManifestSchemaTests(unittest.TestCase):
    def test_artifact_manifest_lists_relative_paths_checksums_and_callback_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            (artifacts.input_dir / "person.xlsx").write_bytes(b"person")
            (artifacts.logs_dir / "steps.jsonl").write_text("{}", encoding="utf-8")
            (artifacts.screenshots_dir / "screen.png").write_bytes(b"png")
            artifacts.write_json("summary.json", {"job_id": "202605-001"})
            artifacts.write_json("state.json", {"state": "succeeded"})

            relative_path = ArtifactManifestWriter(artifacts).write(
                job_id="202605-001",
                final_status="succeeded",
                callback_status="pending",
            )
            manifest = json.loads(
                (artifacts.root / relative_path).read_text(encoding="utf-8")
            )

        self.assertEqual(relative_path, "artifact_manifest.json")
        self.assertEqual(manifest["job_id"], "202605-001")
        self.assertEqual(manifest["final_status"], "succeeded")
        self.assertEqual(manifest["callback_status"], "pending")
        paths = [item["path"] for item in manifest["artifacts"]]
        self.assertIn("input/person.xlsx", paths)
        self.assertIn("logs/steps.jsonl", paths)
        self.assertIn("screenshots/screen.png", paths)
        self.assertIn("summary.json", paths)
        self.assertIn("state.json", paths)
        self.assertTrue(all(not Path(path).is_absolute() for path in paths))
        self.assertTrue(all(item["sha256"] for item in manifest["artifacts"]))
        self.assertTrue(all(item["created_at"] for item in manifest["artifacts"]))


if __name__ == "__main__":
    unittest.main()
