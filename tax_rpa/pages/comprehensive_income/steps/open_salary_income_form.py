from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage


class OpenSalaryIncomeFormStep:
    def __init__(self, page: "ComprehensiveIncomePage") -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("点击正常工资薪金所得行"):
            row_result = self.page.click_salary_income_row()

        with self.page.step("点击填写"):
            fill_result = self.page.click_salary_income_fill()

        ok = row_result.ok and fill_result.ok
        return StepResult(
            ok=ok,
            name="comprehensive_income.open_salary_income_form",
            status=fill_result.status if ok else "failed",
            evidence={
                "salary_income_row": row_result,
                "fill": fill_result,
            },
            error=row_result.error or fill_result.error,
        )
