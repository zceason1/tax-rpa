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
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class ImportSalaryIncomeWorkflow:
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
        steps: list[StepResult] = []
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        open_form = OpenSalaryIncomeFormStep(page).run()
        steps.append(open_form)
        if not open_form.ok:
            return self._failed(open_form, steps)

        import_file = ImportSalaryIncomeDataStep(page).run(self.config.import_file("salary_income"))
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
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        return WorkflowResult(
            ok=False,
            name="import_salary_income_workflow",
            status=result.status,
            steps=steps,
            error=result.error,
        )
