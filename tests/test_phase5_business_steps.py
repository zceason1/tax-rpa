import unittest
from contextlib import nullcontext

from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.export_declaration_report import (
    ExportDeclarationReportStep,
)
from tax_rpa.pages.comprehensive_income.steps.prefill_deduction import (
    PrefillDeductionStep,
)
from tax_rpa.pages.comprehensive_income.steps.tax_calculation import (
    TaxCalculationStep,
)
from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.result_matrix import classify_step_result


class Phase5BusinessStepTests(unittest.TestCase):
    def test_result_matrix_classifies_phase5_success_failure_unknown_and_blocked(self):
        success = classify_step_result(
            "prefill_deduction",
            StepResult(ok=True, name="prefill", status="success"),
        )
        failure = classify_step_result(
            "export_report",
            StepResult(ok=False, name="export", status="failed"),
        )
        unknown = classify_step_result(
            "tax_calculation",
            StepResult(ok=False, name="calculate", status="unknown"),
        )
        blocked = classify_step_result(
            "tax_calculation",
            StepResult(
                ok=False,
                name="calculate",
                status="blocked",
                error_type="BLOCKED_BY_UNEXPECTED_DIALOG",
                error_code="unexpected_dialog",
            ),
        )

        self.assertEqual(success["outcome"], "success")
        self.assertEqual(failure["outcome"], "failure")
        self.assertEqual(failure["error_type"], "EXPORT_ERROR")
        self.assertEqual(failure["error_code"], "export_report_failed")
        self.assertEqual(unknown["outcome"], "unknown")
        self.assertEqual(unknown["error_type"], "UNKNOWN_RESULT")
        self.assertEqual(unknown["error_code"], "tax_calculation_result_unknown")
        self.assertEqual(blocked["outcome"], "blocked")
        self.assertEqual(blocked["error_type"], "BLOCKED_BY_UNEXPECTED_DIALOG")

    def test_prefill_selects_required_options_and_waits_for_explicit_result(self):
        page = FakePhase5Page()

        result = PrefillDeductionStep(page).run()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertEqual(
            page.events,
            [
                "click_prefill_deduction",
                "read_prefill_confirmation_dialog",
                "confirm_prefill_options:False",
                "read_prefill_result",
            ],
        )

    def test_prefill_can_skip_personal_pension_only_when_allowed(self):
        blocked_page = FakePhase5Page(personal_pension_available=False)

        blocked = PrefillDeductionStep(blocked_page).run()

        self.assertFalse(blocked.ok)
        self.assertEqual(blocked.status, "personal_pension_missing")
        self.assertEqual(blocked.error_type, "BUSINESS_REJECTED")

        allowed_page = FakePhase5Page(personal_pension_available=False)
        allowed = PrefillDeductionStep(
            allowed_page,
            allow_skip_personal_pension=True,
        ).run()

        self.assertTrue(allowed.ok)
        self.assertEqual(allowed.status, "success")
        self.assertIn("confirm_prefill_options:True", allowed_page.events)

    def test_tax_calculation_blocks_unexpected_popup_without_confirming(self):
        page = FakePhase5Page(
            tax_popup=StepResult(
                ok=False,
                name="tax_calculation.popup",
                status="blocked",
                error="Unexpected popup",
                error_type="BLOCKED_BY_UNEXPECTED_DIALOG",
                error_code="unexpected_dialog",
                ui_text=["manual review required"],
            )
        )

        result = TaxCalculationStep(page).run()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.error_type, "BLOCKED_BY_UNEXPECTED_DIALOG")
        self.assertNotIn("confirm_tax_calculation_popup", page.events)

    def test_declaration_readiness_locates_send_button_without_clicking(self):
        page = FakePhase5Page()

        result = DeclarationSubmissionReadinessStep(
            page,
            run_mode="execute_no_send",
        ).run()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ready_to_submit_not_sent")
        self.assertFalse(result.side_effect_started)
        self.assertEqual(
            page.events,
            ["open_declaration_submission_page", "locate_send_declaration_button"],
        )

    def test_export_execute_no_send_accepts_not_available_before_submit(self):
        page = FakePhase5Page(
            export_result=StepResult(
                ok=True,
                name="export_report.result",
                status="not_available_before_submit",
                evidence={"export_status": "not_available_before_submit"},
            )
        )

        result = ExportDeclarationReportStep(
            page,
            run_mode="execute_no_send",
        ).run()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "not_available_before_submit")
        self.assertEqual(result.evidence["export_status"], "not_available_before_submit")


class FakePhase5Page:
    def __init__(
        self,
        *,
        personal_pension_available: bool = True,
        tax_popup: StepResult | None = None,
        export_result: StepResult | None = None,
    ) -> None:
        self.personal_pension_available = personal_pension_available
        self.tax_popup = tax_popup or StepResult(
            ok=True,
            name="tax_calculation.popup",
            status="no_popup",
        )
        self.export_result = export_result or StepResult(
            ok=True,
            name="export_report.result",
            status="pre_submit_export",
            evidence={"export_status": "pre_submit_export"},
        )
        self.events: list[str] = []

    def step(self, _name, **_data):
        return nullcontext()

    def click_prefill_deduction(self):
        self.events.append("click_prefill_deduction")
        return StepResult(ok=True, name="prefill.click", status="clicked")

    def read_prefill_confirmation_dialog(self):
        self.events.append("read_prefill_confirmation_dialog")
        return StepResult(
            ok=True,
            name="prefill.confirmation_dialog",
            status="ready",
        )

    def confirm_prefill_options(self, *, allow_skip_personal_pension: bool):
        self.events.append(f"confirm_prefill_options:{allow_skip_personal_pension}")
        if self.personal_pension_available or allow_skip_personal_pension:
            return StepResult(ok=True, name="prefill.options", status="confirmed")
        return StepResult(
            ok=False,
            name="prefill.options",
            status="personal_pension_missing",
            error="Personal pension option is missing",
            error_type="BUSINESS_REJECTED",
            error_code="personal_pension_missing",
        )

    def read_prefill_result(self):
        self.events.append("read_prefill_result")
        return StepResult(ok=True, name="prefill.result", status="success")

    def click_tax_calculation_tab(self):
        self.events.append("click_tax_calculation_tab")
        return StepResult(ok=True, name="tax_calculation.open", status="clicked")

    def read_tax_calculation_popup(self):
        self.events.append("read_tax_calculation_popup")
        return self.tax_popup

    def confirm_tax_calculation_popup(self):
        self.events.append("confirm_tax_calculation_popup")
        return StepResult(ok=True, name="tax_calculation.popup_confirm", status="confirmed")

    def read_tax_calculation_result(self):
        self.events.append("read_tax_calculation_result")
        return StepResult(ok=True, name="tax_calculation.result", status="success")

    def open_declaration_submission_page(self):
        self.events.append("open_declaration_submission_page")
        return StepResult(ok=True, name="declaration_submission.open", status="ready")

    def locate_send_declaration_button(self):
        self.events.append("locate_send_declaration_button")
        return StepResult(
            ok=True,
            name="declaration_submission.send_button",
            status="ready_to_submit_not_sent",
        )

    def open_export_report_menu(self):
        self.events.append("open_export_report_menu")
        return StepResult(ok=True, name="export_report.open_menu", status="opened")

    def choose_standard_report_option(self):
        self.events.append("choose_standard_report_option")
        return StepResult(ok=True, name="export_report.standard", status="selected")

    def read_export_result(self, *, run_mode: str):
        self.events.append(f"read_export_result:{run_mode}")
        return self.export_result


if __name__ == "__main__":
    unittest.main()
