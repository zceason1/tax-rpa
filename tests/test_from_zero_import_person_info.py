import unittest
from pathlib import Path

from tax_rpa.cli.from_zero_import_person_info import build_launch_decision, is_process_not_found


class FromZeroImportPersonInfoTests(unittest.TestCase):
    def test_build_launch_decision_skips_launch_when_process_already_running(self):
        decision = build_launch_decision([1234], Path("C:/client/EPPortalITS.exe"))

        self.assertEqual(decision["action"], "reuse_running_process")
        self.assertEqual(decision["pids"], [1234])

    def test_build_launch_decision_launches_when_path_configured(self):
        decision = build_launch_decision([], Path("C:/client/EPPortalITS.exe"))

        self.assertEqual(decision["action"], "launch")
        self.assertEqual(decision["app_path"], "C:\\client\\EPPortalITS.exe")

    def test_build_launch_decision_requires_app_path_when_no_process_running(self):
        decision = build_launch_decision([], None)

        self.assertEqual(decision["action"], "missing_app_path")

    def test_is_process_not_found_matches_existing_helper_error(self):
        self.assertTrue(is_process_not_found(RuntimeError("未找到进程 EPPortalITS.exe")))
        self.assertFalse(is_process_not_found(RuntimeError("other failure")))


if __name__ == "__main__":
    unittest.main()
