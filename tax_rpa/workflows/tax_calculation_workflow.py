from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.tax_calculation import TaxCalculationStep
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class TaxCalculationWorkflow(BusinessWorkflow):
    """税务税款计算工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "tax_calculation_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        app_factory: Any | None = None,
    ) -> None:
        """初始化税务税款计算工作流实例，保存依赖、配置和运行上下文。"""
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
        calculation = self.context.step(
            "comprehensive_income.calculate_tax",
            lambda: TaxCalculationStep(page).run(),
            matrix_step="tax_calculation",
            side_effect_step=True,
        )
        return self.context.result_from_step(
            calculation,
            steps=[calculation],
            evidence={"calculation": calculation.evidence},
        )
