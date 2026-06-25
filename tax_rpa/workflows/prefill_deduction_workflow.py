from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_salary_income_form import (
    OpenSalaryIncomeFormStep,
)
from tax_rpa.pages.comprehensive_income.steps.prefill_deduction import (
    PrefillDeductionStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class PrefillDeductionWorkflow(BusinessWorkflow):
    """预填扣除工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "prefill_deduction_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        app_factory: Any | None = None,
    ) -> None:
        """初始化预填扣除工作流实例，保存依赖、配置和运行上下文。"""
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )

    def execute(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        steps = []
        open_form = self.context.step(
            "comprehensive_income.open_salary_income_form_for_prefill",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self.context.failed_from_step(
                open_form,
                steps=steps,
                evidence={"open_form": open_form.evidence},
            )

        prefill = self.context.step(
            "comprehensive_income.prefill_deduction",
            lambda: PrefillDeductionStep(
                page,
                allow_skip_personal_pension=self._allow_skip_personal_pension(),
            ).run(),
            matrix_step="prefill_deduction",
            side_effect_step=True,
        )
        steps.append(prefill)
        return self.context.result_from_step(
            prefill,
            steps=steps,
            evidence={
                "open_form": open_form.evidence,
                "prefill": prefill.evidence,
            },
        )

    def _allow_skip_personal_pension(self) -> bool:
        """执行工作流、预填扣除工作流中的内部辅助逻辑：allowskippersonalpension。"""
        return self.runtime_options.allow_skip_personal_pension
