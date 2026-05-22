from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.special_deduction.steps.download_update_all_persons import (
    DownloadUpdateAllPersonsStep,
)
from tax_rpa.pages.special_deduction.steps.open_page import OpenSpecialDeductionPageStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class UpdateSpecialDeductionWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
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
        steps: list[StepResult] = []
        page = OpenSpecialDeductionPageStep(app.shell()).run()
        update_result = DownloadUpdateAllPersonsStep(page).run()
        steps.append(update_result)

        return WorkflowResult(
            ok=update_result.ok,
            name="update_special_deduction_workflow",
            status=update_result.status,
            steps=steps,
            evidence={"download_update": update_result.evidence},
            error=update_result.error,
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        return WorkflowResult(
            ok=False,
            name="update_special_deduction_workflow",
            status=result.status,
            steps=steps,
            error=result.error,
        )
