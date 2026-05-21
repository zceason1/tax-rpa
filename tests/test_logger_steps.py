import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from tax_rpa.drivers.logger import RunLogger


class RunLoggerStepTests(unittest.TestCase):
    def test_step_logs_start_and_passed_with_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                logger = RunLogger()

                with redirect_stdout(StringIO()):
                    with logger.step("sample step", page="person_info"):
                        logger.log("inside", "ok")

                entries = [
                    json.loads(line)
                    for line in logger.log_path.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                os.chdir(original_cwd)

        self.assertEqual(entries[0]["step"], "sample step")
        self.assertEqual(entries[0]["status"], "start")
        self.assertEqual(entries[0]["page"], "person_info")
        self.assertEqual(entries[1]["step"], "inside")
        self.assertEqual(entries[1]["status"], "ok")
        self.assertEqual(entries[2]["step"], "sample step")
        self.assertEqual(entries[2]["status"], "passed")
        self.assertIn("duration_ms", entries[2])

    def test_step_logs_failed_and_reraises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                logger = RunLogger()

                with redirect_stdout(StringIO()):
                    with self.assertRaises(ValueError):
                        with logger.step("failing step"):
                            raise ValueError("bad input")

                entries = [
                    json.loads(line)
                    for line in logger.log_path.read_text(encoding="utf-8").splitlines()
                ]
            finally:
                os.chdir(original_cwd)

        self.assertEqual(entries[0]["step"], "failing step")
        self.assertEqual(entries[0]["status"], "start")
        self.assertEqual(entries[1]["step"], "failing step")
        self.assertEqual(entries[1]["status"], "failed")
        self.assertEqual(entries[1]["error"], "bad input")
        self.assertIn("traceback", entries[1])
        self.assertIn("duration_ms", entries[1])


if __name__ == "__main__":
    unittest.main()
