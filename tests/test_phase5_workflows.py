import unittest
from contextlib import nullcontext
from pathlib import Path

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.declaration_submission_workflow import (
    DeclarationSubmissionWorkflow,
)
from tax_rpa.workflows.export_report_workflow import ExportReportWorkflow
from tax_rpa.workflows.prefill_deduction_workflow import PrefillDeductionWorkflow
from tax_rpa.workflows.tax_calculation_workflow import TaxCalculationWorkflow


class Phase5WorkflowTests(unittest.TestCase):
    def test_each_phase5_workflow_has_fake_driver_success_path(self):
        cases = [
            (PrefillDeductionWorkflow, "success"),
            (TaxCalculationWorkflow, "success"),
            (DeclarationSubmissionWorkflow, "ready_to_submit_not_sent"),
            (ExportReportWorkflow, "not_available_before_submit"),
        ]

        for workflow_class, expected_status in cases:
            with self.subTest(workflow=workflow_class.__name__):
                page = FakePhase5ComprehensivePage()
                result = workflow_class(self._config(), logger=None).run_on_app(
                    FakePhase5App(page)
                )

                self.assertTrue(result.ok)
                self.assertEqual(result.status, expected_status)

    def test_each_phase5_workflow_preserves_business_failure(self):
        cases = [
            (
                PrefillDeductionWorkflow,
                {
                    "prefill_options": StepResult(
                        ok=False,
                        name="prefill.options",
                        status="personal_pension_missing",
                        error="Personal pension option is missing",
                        error_type="BUSINESS_REJECTED",
                        error_code="personal_pension_missing",
                    )
                },
                "BUSINESS_REJECTED",
            ),
            (
                TaxCalculationWorkflow,
                {
                    "tax_result": StepResult(
                        ok=False,
                        name="tax_calculation.result",
                        status="calculation_failed",
                        error="Calculation failed",
                        error_type="BUSINESS_REJECTED",
                        error_code="tax_calculation_failed",
                    )
                },
                "BUSINESS_REJECTED",
            ),
            (
                DeclarationSubmissionWorkflow,
                {
                    "send_button": StepResult(
                        ok=False,
                        name="declaration_submission.send_button",
                        status="send_button_missing",
                        error="Send button missing",
                        error_type="UI_ELEMENT_NOT_FOUND",
                        error_code="send_declaration_button_missing",
                    )
                },
                "UI_ELEMENT_NOT_FOUND",
            ),
            (
                ExportReportWorkflow,
                {
                    "export_result": StepResult(
                        ok=False,
                        name="export_report.result",
                        status="export_failed",
                        error="Export failed",
                        error_type="EXPORT_ERROR",
                        error_code="export_report_failed",
                    )
                },
                "EXPORT_ERROR",
            ),
        ]

        for workflow_class, overrides, expected_error_type in cases:
            with self.subTest(workflow=workflow_class.__name__):
                result = workflow_class(self._config(), logger=None).run_on_app(
                    FakePhase5App(FakePhase5ComprehensivePage(overrides=overrides))
                )

                self.assertFalse(result.ok)
                self.assertEqual(result.error_type, expected_error_type)

    def test_each_phase5_workflow_preserves_unknown_result(self):
        unknown = lambda name: StepResult(
            ok=False,
            name=name,
            status="unknown",
            error="UI result was not recognized",
            error_type="UNKNOWN_RESULT",
            error_code=f"{name.replace('.', '_')}_unknown",
        )
        cases = [
            (PrefillDeductionWorkflow, {"prefill_result": unknown("prefill.result")}),
            (TaxCalculationWorkflow, {"tax_result": unknown("tax_calculation.result")}),
            (
                DeclarationSubmissionWorkflow,
                {"send_button": unknown("declaration_submission.send_button")},
            ),
            (ExportReportWorkflow, {"export_result": unknown("export_report.result")}),
        ]

        for workflow_class, overrides in cases:
            with self.subTest(workflow=workflow_class.__name__):
                result = workflow_class(self._config(), logger=None).run_on_app(
                    FakePhase5App(FakePhase5ComprehensivePage(overrides=overrides))
                )

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "unknown")
                self.assertEqual(result.error_type, "UNKNOWN_RESULT")

    def test_each_phase5_workflow_preserves_blocked_result(self):
        blocked = lambda name: StepResult(
            ok=False,
            name=name,
            status="blocked",
            error="Unexpected dialog",
            error_type="BLOCKED_BY_UNEXPECTED_DIALOG",
            error_code="unexpected_dialog",
            ui_text=["manual review required"],
        )
        cases = [
            (PrefillDeductionWorkflow, {"prefill_dialog": blocked("prefill.dialog")}),
            (
                TaxCalculationWorkflow,
                {"tax_popup": blocked("tax_calculation.popup")},
            ),
            (
                DeclarationSubmissionWorkflow,
                {"declaration_open": blocked("declaration_submission.open")},
            ),
            (ExportReportWorkflow, {"export_menu": blocked("export_report.open_menu")}),
        ]

        for workflow_class, overrides in cases:
            with self.subTest(workflow=workflow_class.__name__):
                result = workflow_class(self._config(), logger=None).run_on_app(
                    FakePhase5App(FakePhase5ComprehensivePage(overrides=overrides))
                )

                self.assertFalse(result.ok)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.error_type, "BLOCKED_BY_UNEXPECTED_DIALOG")
                self.assertEqual(result.error_code, "unexpected_dialog")

    def _config(self) -> PersonImportConfig:
        return PersonImportConfig(person_info_file=Path("person.xlsx"), dry_run=False)


class FakePhase5App:
    def __init__(self, page: "FakePhase5ComprehensivePage") -> None:
        self.page = page

    def shell(self):
        return FakePhase5Shell(self.page)


class FakePhase5Shell:
    def __init__(self, page: "FakePhase5ComprehensivePage") -> None:
        self.page = page

    def open_comprehensive_income_page(self):
        return self.page


class FakePhase5ComprehensivePage:
    def __init__(self, *, overrides: dict[str, StepResult] | None = None) -> None:
        self.overrides = overrides or {}
        self.events: list[str] = []

    def step(self, _name, **_data):
        return nullcontext()

    def click_salary_income_row(self):
        self.events.append("click_salary_income_row")
        return StepResult(ok=True, name="salary_income.row", status="clicked")

    def click_salary_income_fill(self):
        self.events.append("click_salary_income_fill")
        return StepResult(ok=True, name="salary_income.fill", status="clicked")

    def click_prefill_deduction(self):
        self.events.append("click_prefill_deduction")
        return StepResult(ok=True, name="prefill.click", status="clicked")

    def read_prefill_confirmation_dialog(self):
        self.events.append("read_prefill_confirmation_dialog")
        return self.overrides.get(
            "prefill_dialog",
            StepResult(ok=True, name="prefill.dialog", status="ready"),
        )

    def confirm_prefill_options(self, *, allow_skip_personal_pension: bool):
        self.events.append(f"confirm_prefill_options:{allow_skip_personal_pension}")
        return self.overrides.get(
            "prefill_options",
            StepResult(ok=True, name="prefill.options", status="confirmed"),
        )

    def read_prefill_result(self):
        self.events.append("read_prefill_result")
        return self.overrides.get(
            "prefill_result",
            StepResult(ok=True, name="prefill.result", status="success"),
        )

    def click_tax_calculation_tab(self):
        self.events.append("click_tax_calculation_tab")
        return StepResult(ok=True, name="tax_calculation.open", status="clicked")

    def read_tax_calculation_popup(self):
        self.events.append("read_tax_calculation_popup")
        return self.overrides.get(
            "tax_popup",
            StepResult(ok=True, name="tax_calculation.popup", status="no_popup"),
        )

    def confirm_tax_calculation_popup(self):
        self.events.append("confirm_tax_calculation_popup")
        return StepResult(ok=True, name="tax_calculation.popup_confirm", status="confirmed")

    def read_tax_calculation_result(self):
        self.events.append("read_tax_calculation_result")
        return self.overrides.get(
            "tax_result",
            StepResult(ok=True, name="tax_calculation.result", status="success"),
        )

    def open_declaration_submission_page(self):
        self.events.append("open_declaration_submission_page")
        return self.overrides.get(
            "declaration_open",
            StepResult(ok=True, name="declaration_submission.open", status="ready"),
        )

    def locate_send_declaration_button(self):
        self.events.append("locate_send_declaration_button")
        return self.overrides.get(
            "send_button",
            StepResult(
                ok=True,
                name="declaration_submission.send_button",
                status="ready_to_submit_not_sent",
            ),
        )

    def open_export_report_menu(self):
        self.events.append("open_export_report_menu")
        return self.overrides.get(
            "export_menu",
            StepResult(ok=True, name="export_report.open_menu", status="opened"),
        )

    def choose_standard_report_option(self):
        self.events.append("choose_standard_report_option")
        return self.overrides.get(
            "export_standard",
            StepResult(ok=True, name="export_report.standard", status="selected"),
        )

    def read_export_result(self, *, run_mode: str):
        self.events.append(f"read_export_result:{run_mode}")
        return self.overrides.get(
            "export_result",
            StepResult(
                ok=True,
                name="export_report.result",
                status="not_available_before_submit",
                evidence={"export_status": "not_available_before_submit"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
