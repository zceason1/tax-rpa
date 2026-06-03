from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.import_salary_income_data import (
    ImportSalaryIncomeDataStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_salary_income_form import (
    OpenSalaryIncomeFormStep,
)
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class ImportSalaryIncomeWorkflow:
    """导入工资薪金收入工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
    ) -> None:
        """初始化导入工资薪金收入工作流实例，保存依赖、配置和运行上下文。"""
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
                name="import_salary_income_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="import_salary_income_workflow",
            status=business_result.status,
            steps=[*lifecycle_result.steps, *business_result.steps],
            evidence=business_result.evidence,
            error=business_result.error,
        )

    def run_on_app(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        steps: list[StepResult] = []
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        open_form = self._run_step(
            "comprehensive_income.open_salary_income_form",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self._failed(open_form, steps)

        import_file = self._run_step(
            "comprehensive_income.import_salary_income_data",
            lambda: ImportSalaryIncomeDataStep(page).run(
                self.config.import_file("salary_income")
            ),
            matrix_step="salary_income_import",
            side_effect_step=True,
        )
        steps.append(import_file)

        return WorkflowResult(
            ok=import_file.ok,
            name="import_salary_income_workflow",
            status=import_file.status,
            steps=steps,
            evidence={
                "open_form": open_form.evidence,
                "import_file": import_file.evidence,
            },
            error=import_file.error,
            error_type=import_file.error_type,
            error_code=import_file.error_code,
            side_effect_started=import_file.side_effect_started,
            side_effect_committed=import_file.side_effect_committed,
            retry_allowed=import_file.retry_allowed,
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        """把失败步骤包装成上层失败结果，并保留已执行步骤证据。"""
        return WorkflowResult(
            ok=False,
            name="import_salary_income_workflow",
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
            workflow="import_salary_income_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )
