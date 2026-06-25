from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class DeclarationSubmissionWorkflow(BusinessWorkflow):
    """申报报送工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "declaration_submission_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        app_factory: Any | None = None,
    ) -> None:
        """初始化申报报送工作流实例，保存依赖、配置和运行上下文。"""
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
        readiness = self.context.step(
            "comprehensive_income.declaration_submission_readiness",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            matrix_step="declaration_submission_readiness",
            side_effect_step=False,
        )
        return self.context.result_from_step(
            readiness,
            steps=[readiness],
            evidence={"readiness": readiness.evidence},
        )

    def _run_mode(self) -> str:
        """执行工作流、申报报送工作流中的内部辅助逻辑：run模式。"""
        return self.runtime_options.run_mode
