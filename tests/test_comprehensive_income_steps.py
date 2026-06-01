import unittest
from contextlib import nullcontext
from pathlib import Path

from tax_rpa.pages.comprehensive_income.steps.import_salary_income_data import (
    ImportSalaryIncomeDataStep,
)
from tax_rpa.runtime.result import StepResult


class FakeComprehensiveIncomePage:
    def __init__(self, dry_run: bool, file_dialog_opened: bool) -> None:
        self.dry_run = dry_run
        self.file_dialog_opened = file_dialog_opened
        self.events: list[str] = []

    def step(self, _name, **_data):
        return nullcontext()

    def click_import_button(self):
        self.events.append("click_import")
        return StepResult(ok=True, name="click_import", status="clicked")

    def choose_import_data_option(self):
        self.events.append("choose_import_data")
        return StepResult(ok=True, name="choose_import_data", status="clicked")

    def choose_salary_income_file(self, path, _import_option_result):
        self.events.append(f"choose_file:{path.name}")
        if not self.file_dialog_opened:
            return None
        return StepResult(ok=True, name="choose_file", status="dry_run")


class ComprehensiveIncomeStepTests(unittest.TestCase):
    def test_import_salary_income_data_allows_missing_file_dialog_in_debug_mode(self):
        page = FakeComprehensiveIncomePage(dry_run=True, file_dialog_opened=False)

        result = ImportSalaryIncomeDataStep(page).run(Path("salary.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "debug_verified")
        self.assertEqual(
            page.events,
            ["click_import", "choose_import_data", "choose_file:salary.xlsx"],
        )

    def test_import_salary_income_data_requires_file_dialog_when_submit_mode(self):
        page = FakeComprehensiveIncomePage(dry_run=False, file_dialog_opened=False)

        result = ImportSalaryIncomeDataStep(page).run(Path("salary.xlsx"))

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "file_dialog_missing")

    def test_import_salary_income_data_waits_for_import_result_after_file_submit(self):
        class Page(FakeComprehensiveIncomePage):
            def __init__(self):
                super().__init__(dry_run=False, file_dialog_opened=True)
                self.events = []

            def read_salary_income_import_result(self):
                self.events.append("read_result")
                return StepResult(
                    ok=True,
                    name="salary_income.wait_import_result",
                    status="success",
                )

        page = Page()

        result = ImportSalaryIncomeDataStep(page).run(Path("salary.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")
        self.assertEqual(
            page.events,
            ["click_import", "choose_import_data", "choose_file:salary.xlsx", "read_result"],
        )
        self.assertIn("import_result", result.evidence)

    def test_import_salary_income_data_stops_when_import_result_unknown(self):
        class Page(FakeComprehensiveIncomePage):
            def __init__(self):
                super().__init__(dry_run=False, file_dialog_opened=True)

            def read_salary_income_import_result(self):
                return StepResult(
                    ok=False,
                    name="salary_income.wait_import_result",
                    status="unknown",
                    error="Salary income import result was not recognized",
                    error_type="UNKNOWN_RESULT",
                    error_code="salary_income_import_result_unknown",
                )

        result = ImportSalaryIncomeDataStep(Page()).run(Path("salary.xlsx"))

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")

    def test_import_salary_income_data_stops_when_file_submit_fails(self):
        class Page(FakeComprehensiveIncomePage):
            def __init__(self):
                super().__init__(dry_run=False, file_dialog_opened=True)
                self.read_result_called = False

            def choose_salary_income_file(self, path, _import_option_result):
                self.events.append(f"choose_file:{path.name}")
                return StepResult(
                    ok=False,
                    name="choose_file",
                    status="submit_failed",
                    error="File submit failed",
                    error_type="FILE_SUBMIT_FAILED",
                    error_code="file_submit_failed",
                )

            def read_salary_income_import_result(self):
                self.read_result_called = True
                return StepResult(ok=True, name="salary_income.wait_import_result", status="success")

        page = Page()

        result = ImportSalaryIncomeDataStep(page).run(Path("salary.xlsx"))

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "submit_failed")
        self.assertEqual(result.error_type, "FILE_SUBMIT_FAILED")
        self.assertFalse(page.read_result_called)


if __name__ == "__main__":
    unittest.main()
