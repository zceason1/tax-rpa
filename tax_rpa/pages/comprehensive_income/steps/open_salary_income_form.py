from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage


class OpenSalaryIncomeFormStep:
    """open工资薪金收入form步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, page: "ComprehensiveIncomePage") -> None:
        """初始化open工资薪金收入form步骤实例，保存依赖、配置和运行上下文。"""
        self.page = page

    def run(self) -> StepResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
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
