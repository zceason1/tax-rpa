from typing import Any

from tax_rpa.runtime.result import StepResult


class PrefillDeductionStep:
    def __init__(
        self,
        page: Any,
        *,
        allow_skip_personal_pension: bool = False,
    ) -> None:
        self.page = page
        self.allow_skip_personal_pension = allow_skip_personal_pension

    def run(self) -> StepResult:
        with self.page.step("click_prefill_deduction"):
            click_result = self.page.click_prefill_deduction()
        if not click_result.ok:
            return self._failed(click_result)

        with self.page.step("read_prefill_confirmation_dialog"):
            dialog_result = self.page.read_prefill_confirmation_dialog()
        if not dialog_result.ok:
            return self._failed(dialog_result, click_result=click_result)

        with self.page.step("confirm_prefill_options"):
            options_result = self.page.confirm_prefill_options(
                allow_skip_personal_pension=self.allow_skip_personal_pension,
            )
        if not options_result.ok:
            return self._failed(
                options_result,
                click_result=click_result,
                dialog_result=dialog_result,
            )

        with self.page.step("read_prefill_result"):
            result = self.page.read_prefill_result()
        if not result.ok:
            return self._failed(
                result,
                click_result=click_result,
                dialog_result=dialog_result,
                options_result=options_result,
            )

        return StepResult(
            ok=True,
            name="comprehensive_income.prefill_deduction",
            status=result.status,
            evidence={
                "click": click_result,
                "dialog": dialog_result,
                "options": options_result,
                "result": result,
                **result.evidence,
            },
            side_effect_started=True,
            side_effect_committed=True,
            evidence_paths=result.evidence_paths,
            ui_text=[*dialog_result.ui_text, *result.ui_text],
        )

    def _failed(self, result: StepResult, **evidence: StepResult) -> StepResult:
        return StepResult(
            ok=False,
            name="comprehensive_income.prefill_deduction",
            status=result.status,
            evidence={**evidence, "result": result},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=True,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
            evidence_paths=result.evidence_paths,
            ui_text=result.ui_text,
        )
