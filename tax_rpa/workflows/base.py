from collections.abc import Callable
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.step_runner import StepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.app_factory import create_tax_client_app
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.context import WorkflowContext


class BusinessWorkflow:
    """Base support for standalone lifecycle and shared workflow context."""

    name = ""

    def _init_workflow(
        self,
        *,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: StepRunner | None = None,
        reset: bool = False,
    ) -> None:
        self.config = config
        self.logger = logger
        self.app_factory = app_factory or create_tax_client_app
        self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
        self.step_runner = step_runner
        self.reset = reset
        self.context = WorkflowContext(
            workflow=self.name,
            config=self.config,
            logger=self.logger,
            runtime_options=self.runtime_options,
            step_runner=self.step_runner,
        )

    def run(self) -> WorkflowResult:
        """Run lifecycle for standalone usage, then execute the business workflow."""
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
                name=self.name,
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                evidence=lifecycle_result.evidence,
                error=lifecycle_result.error,
                error_type=lifecycle_result.error_type,
                error_code=lifecycle_result.error_code,
                side_effect_started=lifecycle_result.side_effect_started,
                side_effect_committed=lifecycle_result.side_effect_committed,
                retry_allowed=lifecycle_result.retry_allowed,
            )

        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name=self.name,
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
        """Run business logic on an already logged-in app."""
        return self.execute(app)

    def execute(self, app: Any) -> WorkflowResult:
        """Concrete workflows implement business order here."""
        raise NotImplementedError
