from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
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
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class PrefillDeductionWorkflow:
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
                name="prefill_deduction_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="prefill_deduction_workflow",
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
        steps: list[StepResult] = []
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        open_form = self._run_step(
            "comprehensive_income.open_salary_income_form_for_prefill",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self._failed(open_form, steps)

        prefill = self._run_step(
            "comprehensive_income.prefill_deduction",
            lambda: PrefillDeductionStep(
                page,
                allow_skip_personal_pension=self._allow_skip_personal_pension(),
            ).run(),
            matrix_step="prefill_deduction",
            side_effect_step=True,
        )
        steps.append(prefill)
        return self._from_final_step(prefill, steps, {"open_form": open_form.evidence})

    def _allow_skip_personal_pension(self) -> bool:
        manifest = getattr(self.job_context, "manifest", None)
        return bool(getattr(manifest, "allow_skip_personal_pension", False))

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
            workflow="prefill_deduction_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )

    def _from_final_step(
        self,
        result: StepResult,
        steps: list[StepResult],
        evidence: dict[str, Any],
    ) -> WorkflowResult:
        return WorkflowResult(
            ok=result.ok,
            name="prefill_deduction_workflow",
            status=result.status,
            steps=steps,
            evidence={**evidence, "prefill": result.evidence},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=result.side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        return WorkflowResult(
            ok=False,
            name="prefill_deduction_workflow",
            status=result.status,
            steps=steps,
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=result.side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
        )
