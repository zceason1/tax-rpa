import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.lock import UiRunnerBusyError, UiRunnerLock


class UiRunnerLockTests(unittest.TestCase):
    def test_acquire_writes_runner_lock_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "runner.lock.json"
            lock = UiRunnerLock(lock_path)

            lease = lock.acquire("202605-001")
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
            finally:
                lease.release()

        self.assertEqual(data["job_id"], "202605-001")
        self.assertIn("process_id", data)
        self.assertIn("windows_user", data)
        self.assertIn("acquired_at", data)
        self.assertIn("heartbeat_at", data)

    def test_second_acquire_reports_busy_with_active_job_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "runner.lock.json"
            first = UiRunnerLock(lock_path).acquire("202605-001")
            try:
                with self.assertRaises(UiRunnerBusyError) as cm:
                    UiRunnerLock(lock_path).acquire("202605-002")
            finally:
                first.release()

        self.assertEqual(cm.exception.active_job_id, "202605-001")

    def test_stale_diagnostic_file_does_not_block_after_release(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "runner.lock.json"
            first = UiRunnerLock(lock_path).acquire("202605-001")
            first.release()

            second = UiRunnerLock(lock_path).acquire("202605-002")
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
            finally:
                second.release()

        self.assertEqual(data["job_id"], "202605-002")


if __name__ == "__main__":
    unittest.main()
