from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.special_deduction.steps.download_update_all_persons import (
    DownloadUpdateAllPersonsStep,
)
from tax_rpa.pages.special_deduction.steps.open_page import OpenSpecialDeductionPageStep
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class UpdateSpecialDeductionWorkflow(BusinessWorkflow):
    """更新专项扣除工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "update_special_deduction_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Any | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
    ) -> None:
        """初始化更新专项扣除工作流实例，保存依赖、配置和运行上下文。"""
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )

    def execute(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        page = OpenSpecialDeductionPageStep(app.shell()).run()
        update_result = self.context.step(
            "special_deduction.download_update_all_persons",
            lambda: DownloadUpdateAllPersonsStep(page).run(),
            matrix_step="special_deduction_update",
            side_effect_step=True,
        )

        return self.context.result_from_step(
            update_result,
            steps=[update_result],
            evidence={"download_update": update_result.evidence},
        )
