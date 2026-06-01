from typing import Any

from tax_rpa.runtime.result import StepResult


class TaxCalculationStep:
    def __init__(self, page: Any) -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("click_tax_calculation_tab"):
            open_result = self.page.click_tax_calculation_tab()
        if not open_result.ok:
            return self._failed(open_result)

        with self.page.step("read_tax_calculation_popup"):
            popup_result = self.page.read_tax_calculation_popup()
        if not popup_result.ok:
            return self._failed(popup_result, open_result=open_result)

        popup_confirm_result: StepResult | None = None
        if popup_result.status not in {"no_popup", "not_present"}:
            with self.page.step("confirm_tax_calculation_popup"):
                popup_confirm_result = self.page.confirm_tax_calculation_popup()
            if not popup_confirm_result.ok:
                return self._failed(
                    popup_confirm_result,
                    open_result=open_result,
                    popup_result=popup_result,
                )

        with self.page.step("read_tax_calculation_result"):
            result = self.page.read_tax_calculation_result()
        if not result.ok:
            return self._failed(
                result,
                open_result=open_result,
                popup_result=popup_result,
                popup_confirm_result=popup_confirm_result,
            )

        return StepResult(
            ok=True,
            name="comprehensive_income.calculate_tax",
            status=result.status,
            evidence={
                "open": open_result,
                "popup": popup_result,
                "popup_confirm": popup_confirm_result,
                "result": result,
                **result.evidence,
            },
            side_effect_started=True,
            side_effect_committed=True,
            evidence_paths=result.evidence_paths,
            ui_text=[*popup_result.ui_text, *result.ui_text],
        )

    def _failed(self, result: StepResult, **evidence: StepResult | None) -> StepResult:
        return StepResult(
            ok=False,
            name="comprehensive_income.calculate_tax",
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
