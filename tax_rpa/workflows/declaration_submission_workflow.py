from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class DeclarationSubmissionWorkflow:
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
                name="declaration_submission_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="declaration_submission_workflow",
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
        readiness = self._run_step(
            "comprehensive_income.declaration_submission_readiness",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            matrix_step="declaration_submission_readiness",
            side_effect_step=False,
        )
        return WorkflowResult(
            ok=readiness.ok,
            name="declaration_submission_workflow",
            status=readiness.status,
            steps=[readiness],
            evidence={"readiness": readiness.evidence},
            error=readiness.error,
            error_type=readiness.error_type,
            error_code=readiness.error_code,
            side_effect_started=readiness.side_effect_started,
            side_effect_committed=readiness.side_effect_committed,
            retry_allowed=readiness.retry_allowed,
        )

    def _run_mode(self) -> str:
        manifest = getattr(self.job_context, "manifest", None)
        if manifest is not None:
            return manifest.run_mode
        return "inspect_only" if self.config.dry_run else "execute_no_send"

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
            workflow="declaration_submission_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )
