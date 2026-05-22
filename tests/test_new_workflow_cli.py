import unittest
from pathlib import Path
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult


class NewWorkflowCliTests(unittest.TestCase):
    def test_salary_income_cli_defaults_to_debug_dry_run(self):
        from tax_rpa.cli.import_salary_income import with_execution_mode

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=False)

        debug_config = with_execution_mode(config, submit=False)

        self.assertTrue(debug_config.dry_run)

    def test_salary_income_cli_submit_enables_real_file_dialog_submission(self):
        from tax_rpa.cli.import_salary_income import with_execution_mode

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=True)

        submit_config = with_execution_mode(config, submit=True)

        self.assertFalse(submit_config.dry_run)

    def test_special_deduction_cli_defaults_to_debug_dry_run(self):
        from tax_rpa.cli.update_special_deduction import with_execution_mode

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=False)

        debug_config = with_execution_mode(config, submit=False)

        self.assertTrue(debug_config.dry_run)

    def test_special_deduction_cli_submit_enables_real_clicks(self):
        from tax_rpa.cli.update_special_deduction import with_execution_mode

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=True)

        submit_config = with_execution_mode(config, submit=True)

        self.assertFalse(submit_config.dry_run)

    def test_salary_income_cli_passes_reset_to_top_level_workflow(self):
        from tax_rpa.cli.import_salary_income import run_workflow

        captured = {}

        class FakeCombinedWorkflow:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self):
                return WorkflowResult(ok=True, name="combined", status="done")

        with patch("tax_rpa.cli.import_salary_income.CombinedTaxWorkflow", FakeCombinedWorkflow):
            summary = run_workflow(
                PersonImportConfig(person_info_file=Path("persons.xlsx")),
                logger=None,
                self_check=False,
                reset=True,
            )

        self.assertEqual(summary["status"], "done")
        self.assertTrue(captured["reset"])
        self.assertEqual(len(captured["workflow_factories"]), 1)

    def test_special_deduction_cli_passes_reset_to_top_level_workflow(self):
        from tax_rpa.cli.update_special_deduction import run_workflow

        captured = {}

        class FakeCombinedWorkflow:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self):
                return WorkflowResult(ok=True, name="combined", status="done")

        with patch("tax_rpa.cli.update_special_deduction.CombinedTaxWorkflow", FakeCombinedWorkflow):
            summary = run_workflow(
                PersonImportConfig(person_info_file=Path("persons.xlsx")),
                logger=None,
                self_check=False,
                reset=True,
            )

        self.assertEqual(summary["status"], "done")
        self.assertTrue(captured["reset"])
        self.assertEqual(len(captured["workflow_factories"]), 1)


if __name__ == "__main__":
    unittest.main()
