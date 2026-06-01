from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.tax_calculation import TaxCalculationStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class TaxCalculationWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        job_context: Any | None = None,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.job_context = job_context
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))

    def run(self) -> WorkflowResult:
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name="tax_calculation_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="tax_calculation_workflow",
            status=business_result.status,
            steps=[*lifecycle_result.steps, *business_result.steps],
            evidence=business_result.evidence,
            error=business_result.error,
            error_type=business_result.error_type,
            error_code=business_result.error_code,
            side_effect_started=business_result.side_effect_started,
            side_effect_committed=business_result.side_effect_committed,
            retry_allowed=business_result.retry_allowed,
        )

    def run_on_app(self, app: Any) -> WorkflowResult:
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        calculation = self._run_step(
            "comprehensive_income.calculate_tax",
            lambda: TaxCalculationStep(page).run(),
            matrix_step="tax_calculation",
            side_effect_step=True,
        )
        return WorkflowResult(
            ok=calculation.ok,
            name="tax_calculation_workflow",
            status=calculation.status,
            steps=[calculation],
            evidence={"calculation": calculation.evidence},
            error=calculation.error,
            error_type=calculation.error_type,
            error_code=calculation.error_code,
            side_effect_started=calculation.side_effect_started,
            side_effect_committed=calculation.side_effect_committed,
            retry_allowed=calculation.retry_allowed,
        )

    def _run_step(
        self,
        step: str,
        operation: Callable[[], StepResult],
        *,
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        if self.job_context is None:
            return operation()
        return self.job_context.run_step(
            workflow="tax_calculation_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )
