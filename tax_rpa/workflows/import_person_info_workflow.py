from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.steps.open_page import OpenPersonInfoPageStep
from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class ImportPersonInfoWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        job_context: Any | None = None,
        reset: bool = False,
    ) -> None:
        self.config = config
        self.logger = logger
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))
        self.job_context = job_context
        self.reset = reset

    def run(self) -> WorkflowResult:
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name="import_person_info_workflow",
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                error=lifecycle_result.error,
            )
        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name="import_person_info_workflow",
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
        page = OpenPersonInfoPageStep(app.shell()).run()
        import_file = self._run_step(
            "person_info.import_person_file",
            lambda: ImportPersonFileStep(page).run(self.config.person_info_file),
            side_effect_step=True,
        )
        steps.append(import_file)
        if not import_file.ok:
            return WorkflowResult(
                ok=False,
                name="import_person_info_workflow",
                status=import_file.status,
                steps=steps,
                evidence={"import_file": import_file.evidence},
                error=import_file.error,
                error_type=import_file.error_type,
                error_code=import_file.error_code,
                side_effect_started=import_file.side_effect_started,
                side_effect_committed=import_file.side_effect_committed,
                retry_allowed=import_file.retry_allowed,
            )

        validation_result = self._run_step(
            "person_info.wait_import_result",
            lambda: WaitImportResultStep(page).run(),
            matrix_step="personnel_import",
        )
        steps.append(validation_result)

        if validation_result.status == "ready_to_submit":
            submit_result = self._run_step(
                "person_info.submit_import_data",
                lambda: SubmitImportDataStep(page).run(),
                side_effect_step=True,
            )
            steps.append(submit_result)
            if not submit_result.ok:
                return WorkflowResult(
                    ok=False,
                    name="import_person_info_workflow",
                    status=submit_result.status,
                    steps=steps,
                    evidence={
                        "import_file": import_file.evidence,
                        "validation_result": validation_result.evidence,
                        "submit_result": submit_result.evidence,
                    },
                    error=submit_result.error,
                    error_type=submit_result.error_type,
                    error_code=submit_result.error_code,
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            import_result = self._run_step(
                "person_info.wait_submit_result",
                lambda: WaitImportResultStep(page).run(),
                matrix_step="personnel_import",
            )
            if import_result.status == "ready_to_submit":
                import_result = StepResult(
                    ok=False,
                    name=import_result.name,
                    status="unknown",
                    evidence={
                        **import_result.evidence,
                        "post_submit_status": "ready_to_submit",
                    },
                    error="Personnel import remained at submit-data confirmation after submit",
                    error_type="UNKNOWN_RESULT",
                    error_code="person_import_result_unknown",
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            steps.append(import_result)
        else:
            import_result = validation_result

        side_effect_started = (
            import_file.ok
            or import_file.side_effect_started
            or validation_result.side_effect_started
            or import_result.side_effect_started
        )
        side_effect_committed = (
            import_file.ok
            or import_file.side_effect_committed
            or validation_result.side_effect_committed
            or import_result.side_effect_committed
        )

        evidence = {
            "import_file": import_file.evidence,
            "validation_result": validation_result.evidence,
            "import_result": import_result.evidence,
        }
        if validation_result.status == "ready_to_submit":
            evidence["submit_result"] = steps[-2].evidence

        return WorkflowResult(
            ok=import_result.ok,
            name="import_person_info_workflow",
            status=import_result.status,
            steps=steps,
            evidence=evidence,
            error=import_result.error,
            error_type=import_result.error_type,
            error_code=import_result.error_code,
            side_effect_started=side_effect_started,
            side_effect_committed=side_effect_committed,
            retry_allowed=False if side_effect_started else import_result.retry_allowed,
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
            workflow="import_person_info_workflow",
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )
