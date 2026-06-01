import unittest
from pathlib import Path
from unittest.mock import patch

from tax_rpa.config.person_import import ImportFileConfig, PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult


class CombinedCliTests(unittest.TestCase):
    def test_run_workflow_builds_complete_business_sequence(self):
        from tax_rpa.cli.run_tax_workflow import run_workflow

        captured = {}

        class FakeCombinedWorkflow:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self):
                return WorkflowResult(ok=True, name="combined", status="done")

        with patch("tax_rpa.cli.run_tax_workflow.CombinedTaxWorkflow", FakeCombinedWorkflow):
            summary = run_workflow(
                PersonImportConfig(person_info_file=Path("persons.xlsx")),
                logger=None,
                reset=True,
            )

        self.assertEqual(summary["status"], "done")
        self.assertTrue(captured["reset"])
        self.assertEqual(len(captured["workflow_factories"]), 3)

    def test_run_workflow_failure_keeps_workflow_error_details(self):
        from tax_rpa.cli.run_tax_workflow import WorkflowExecutionError, run_workflow

        class FakeCombinedWorkflow:
            def __init__(self, **_kwargs):
                pass

            def run(self):
                return WorkflowResult(
                    ok=False,
                    name="combined",
                    status="auto_login_failed",
                    evidence={"last_error": "OCR did not find text '申报密码登录'"},
                    error="Auto login failed after 3 attempts",
                    error_type="LOGIN_FAILED",
                    error_code="auto_login_element_not_found",
                )

        with patch("tax_rpa.cli.run_tax_workflow.CombinedTaxWorkflow", FakeCombinedWorkflow):
            with self.assertRaises(WorkflowExecutionError) as cm:
                run_workflow(
                    PersonImportConfig(person_info_file=Path("persons.xlsx")),
                    logger=None,
                )

        self.assertEqual(str(cm.exception), "Auto login failed after 3 attempts")
        self.assertEqual(cm.exception.result.status, "auto_login_failed")
        self.assertEqual(cm.exception.result.error_type, "LOGIN_FAILED")
        self.assertEqual(
            cm.exception.result.error_code,
            "auto_login_element_not_found",
        )

    def test_run_workflow_self_check_executes_complete_business_sequence(self):
        from tax_rpa.cli.run_tax_workflow import run_workflow

        data_dir = Path(__file__).resolve().parents[1] / "data"
        config = PersonImportConfig(
            person_info_file=data_dir / "person_import_probe.xlsx",
            dry_run=True,
            imports={
                "salary_income": ImportFileConfig(
                    file=data_dir / "salary_income_import.xlsx"
                )
            },
        )

        summary = run_workflow(config, logger=None, self_check=True)

        self.assertEqual(summary["status"], "success")
        business_results = summary["workflow"].evidence["business_results"]
        self.assertEqual(
            [result.name for result in business_results],
            [
                "import_person_info_workflow",
                "update_special_deduction_workflow",
                "import_salary_income_workflow",
            ],
        )
        self.assertTrue(all(result.ok for result in business_results))


if __name__ == "__main__":
    unittest.main()
