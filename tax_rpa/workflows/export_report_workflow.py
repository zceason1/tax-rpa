from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.export_declaration_report import (
    ExportDeclarationReportStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class ExportReportWorkflow:
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
                name="export_report_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="export_report_workflow",
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
            "comprehensive_income.declaration_submission_readiness_for_export",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            side_effect_step=False,
        )
        steps = [readiness]
        if not readiness.ok:
            return self._failed(readiness, steps)

        export = self._run_step(
            "comprehensive_income.export_report",
            lambda: ExportDeclarationReportStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            matrix_step="export_report",
            side_effect_step=True,
        )
        steps.append(export)
        return WorkflowResult(
            ok=export.ok,
            name="export_report_workflow",
            status=export.status,
            steps=steps,
            evidence={
                "readiness": readiness.evidence,
                "export": export.evidence,
                "export_status": export.evidence.get("export_status"),
            },
            error=export.error,
            error_type=export.error_type,
            error_code=export.error_code,
            side_effect_started=export.side_effect_started,
            side_effect_committed=export.side_effect_committed,
            retry_allowed=export.retry_allowed,
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
            workflow="export_report_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        return WorkflowResult(
            ok=False,
            name="export_report_workflow",
            status=result.status,
            steps=steps,
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=result.side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
        )
