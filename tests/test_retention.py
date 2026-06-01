import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tax_rpa.jobs.retention import RetentionCleaner, RetentionPolicy


class RetentionTests(unittest.TestCase):
    def test_cleanup_deletes_expired_terminal_jobs_and_preserves_pending_callbacks(self):
        now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_job(root, "old-success", "succeeded", now - timedelta(days=31))
            create_job(root, "recent-success", "succeeded", now - timedelta(days=2))
            create_job(root, "old-failed", "failed", now - timedelta(days=91))
            create_job(
                root,
                "pending-success",
                "succeeded",
                now - timedelta(days=31),
                callback_state="pending",
            )
            create_job(
                root,
                "dead-letter-failed",
                "failed",
                now - timedelta(days=91),
                callback_state="dead_letter",
            )

            report = RetentionCleaner(
                root,
                policy=RetentionPolicy(success_days=30, failed_days=90),
                now=lambda: now,
            ).cleanup()

            remaining = {path.name for path in root.iterdir() if path.is_dir()}

        self.assertEqual(
            set(report.deleted_jobs),
            {"old-success", "old-failed"},
        )
        self.assertEqual(
            remaining,
            {"recent-success", "pending-success", "dead-letter-failed"},
        )
        self.assertIn("pending-success", report.preserved_jobs)
        self.assertIn("dead-letter-failed", report.preserved_jobs)

    def test_cleanup_deletes_expired_legacy_runlogger_artifacts(self):
        now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_legacy_run(
                root,
                "person_import_20260401_120000",
                "succeeded",
                now - timedelta(days=31),
            )
            create_legacy_run(
                root,
                "person_import_20260520_120000",
                "succeeded",
                now - timedelta(days=4),
            )
            create_legacy_run(
                root,
                "person_import_20260201_120000",
                "failed",
                now - timedelta(days=91),
            )
            create_legacy_run(
                root,
                "person_import_20260101_120000",
                "incomplete",
                now - timedelta(days=120),
            )
            create_legacy_run(
                root,
                "manual_probe_20260101_120000",
                "failed",
                now - timedelta(days=120),
            )

            report = RetentionCleaner(
                root,
                policy=RetentionPolicy(success_days=30, failed_days=90),
                now=lambda: now,
            ).cleanup()

            remaining = {path.name for path in root.iterdir() if path.is_dir()}

        self.assertEqual(
            set(report.deleted_jobs),
            {"person_import_20260401_120000", "person_import_20260201_120000"},
        )
        self.assertEqual(
            remaining,
            {
                "person_import_20260520_120000",
                "person_import_20260101_120000",
                "manual_probe_20260101_120000",
            },
        )
        self.assertIn("person_import_20260520_120000", report.preserved_jobs)
        self.assertIn("person_import_20260101_120000", report.skipped_jobs)
        self.assertIn("manual_probe_20260101_120000", report.skipped_jobs)

    def test_cleanup_artifacts_cleans_jobs_root_and_legacy_root(self):
        from tax_rpa.cli.cleanup_artifacts import cleanup_artifacts

        now = datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            jobs_root = root / "jobs"
            jobs_root.mkdir()
            create_job(jobs_root, "old-job-success", "succeeded", now - timedelta(days=31))
            create_legacy_run(
                root,
                "person_import_20260201_120000",
                "failed",
                now - timedelta(days=91),
            )

            report = cleanup_artifacts(
                root,
                policy=RetentionPolicy(success_days=30, failed_days=90),
                now=lambda: now,
            )

            remaining_jobs = {path.name for path in jobs_root.iterdir() if path.is_dir()}
            remaining_legacy = {
                path.name
                for path in root.iterdir()
                if path.is_dir() and path.name.startswith("person_import_")
            }

        self.assertEqual(remaining_jobs, set())
        self.assertEqual(remaining_legacy, set())
        self.assertEqual(
            set(report.deleted_jobs),
            {"old-job-success", "person_import_20260201_120000"},
        )


def create_job(
    root: Path,
    job_id: str,
    state: str,
    finished_at: datetime,
    *,
    callback_state: str = "not_configured",
) -> None:
    job_root = root / job_id
    job_root.mkdir()
    (job_root / "state.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "state": state,
                "started_at": finished_at.isoformat(),
                "updated_at": finished_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "callback_delivery_state": callback_state,
            }
        ),
        encoding="utf-8",
    )
    (job_root / "summary.json").write_text("{}", encoding="utf-8")


def create_legacy_run(
    root: Path,
    name: str,
    state: str,
    finished_at: datetime,
) -> None:
    run_root = root / name
    run_root.mkdir()
    (run_root / "steps.jsonl").write_text("{}", encoding="utf-8")
    marker_path = None
    if state == "succeeded":
        marker_path = run_root / "tax_workflow_summary.json"
        marker_path.write_text(json.dumps({"status": "success"}), encoding="utf-8")
    elif state == "failed":
        marker_path = run_root / "failed.json"
        marker_path.write_text(json.dumps({"status": "failed"}), encoding="utf-8")

    timestamp = finished_at.timestamp()
    for path in run_root.iterdir():
        os.utime(path, (timestamp, timestamp))
    os.utime(run_root, (timestamp, timestamp))
    if marker_path is not None:
        os.utime(marker_path, (timestamp, timestamp))


if __name__ == "__main__":
    unittest.main()
