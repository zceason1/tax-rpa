import unittest
from pathlib import Path
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.cli.from_zero_import_person_info import (
    build_launch_decision,
    is_process_not_found,
    parse_args,
    run_from_zero,
    run_self_check,
)
from tax_rpa.runtime.result import WorkflowResult


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

    def test_run_self_check_executes_workflow_without_real_client(self):
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=True)

        summary = run_self_check(config, logger=None)

        self.assertEqual(summary["status"], "success")
        self.assertEqual(
            [step.status for step in summary["workflow"].steps],
            ["self_check_start", "self_check_login", "dry_run", "success"],
        )

    def test_from_zero_cli_accepts_reset_flag(self):
        with patch("sys.argv", ["from-zero", "--reset"]):
            args = parse_args()

        self.assertTrue(args.reset)

    def test_run_from_zero_passes_reset_to_lifecycle_workflow(self):
        captured = {}

        class FakeWorkflow:
            def __init__(self, config, logger, reset=False):
                captured["config"] = config
                captured["logger"] = logger
                captured["reset"] = reset

            def run(self):
                return WorkflowResult(ok=True, name="import_person_info_workflow", status="success")

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        with patch(
            "tax_rpa.cli.from_zero_import_person_info.ImportPersonInfoWorkflow",
            FakeWorkflow,
        ):
            summary = run_from_zero(config, logger=None, reset=True)

        self.assertEqual(summary["status"], "success")
        self.assertTrue(captured["reset"])


if __name__ == "__main__":
    unittest.main()
