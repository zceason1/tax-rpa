from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.special_deduction.steps.download_update_all_persons import (
    DownloadUpdateAllPersonsStep,
)
from tax_rpa.pages.special_deduction.steps.open_page import OpenSpecialDeductionPageStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class UpdateSpecialDeductionWorkflow:
    """更新专项扣除工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
    ) -> None:
        """初始化更新专项扣除工作流实例，保存依赖、配置和运行上下文。"""
        self.config = config
        self.logger = logger
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))
        self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
        self.step_runner = step_runner

    def run(self) -> WorkflowResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name="update_special_deduction_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="update_special_deduction_workflow",
            status=business_result.status,
            steps=[*lifecycle_result.steps, *business_result.steps],
            evidence=business_result.evidence,
            error=business_result.error,
        )

    def run_on_app(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        steps: list[StepResult] = []
        page = OpenSpecialDeductionPageStep(app.shell()).run()
        update_result = self._run_step(
            "special_deduction.download_update_all_persons",
            lambda: DownloadUpdateAllPersonsStep(page).run(),
            matrix_step="special_deduction_update",
            side_effect_step=True,
        )
        steps.append(update_result)

        return WorkflowResult(
            ok=update_result.ok,
            name="update_special_deduction_workflow",
            status=update_result.status,
            steps=steps,
            evidence={"download_update": update_result.evidence},
            error=update_result.error,
            error_type=update_result.error_type,
            error_code=update_result.error_code,
            side_effect_started=update_result.side_effect_started,
            side_effect_committed=update_result.side_effect_committed,
            retry_allowed=update_result.retry_allowed,
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        """把失败步骤包装成上层失败结果，并保留已执行步骤证据。"""
        return WorkflowResult(
            ok=False,
            name="update_special_deduction_workflow",
            status=result.status,
            steps=steps,
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=result.side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
        )

    def _run_step(
        self,
        step: str,
        operation: Callable[[], StepResult],
        *,
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        """通过步骤执行器运行单个业务步骤，统一保留日志和结果。"""
        if self.step_runner is None:
            return operation()
        return self.step_runner.run_step(
            workflow="update_special_deduction_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )
