from collections.abc import Callable
import inspect
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.recovery_policy import can_retry_after_failure


BusinessWorkflowFactory = Callable[..., Any]


class CombinedTaxWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        workflow_factories: list[BusinessWorkflowFactory],
        reset: bool = False,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        name: str = "combined_tax_workflow",
        job_context: Any | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.workflow_factories = workflow_factories
        self.reset = reset
        self.app_factory = app_factory
        self.name = name
        self.job_context = job_context

    def run(self) -> WorkflowResult:
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        self._attach_job_context(lifecycle.app)
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name=self.name,
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                evidence={"lifecycle": lifecycle_result.evidence},
                error=lifecycle_result.error,
                error_type=lifecycle_result.error_type,
                error_code=lifecycle_result.error_code,
                side_effect_started=lifecycle_result.side_effect_started,
                side_effect_committed=lifecycle_result.side_effect_committed,
                retry_allowed=lifecycle_result.retry_allowed,
            )

        business_results: list[WorkflowResult] = []
        for factory in self.workflow_factories:
            workflow = self._build_business_workflow(factory)
            result = workflow.run_on_app(lifecycle.app)
            if not result.ok and can_retry_after_failure(result):
                recovered = self._reset_and_wait_for_login()
                if recovered.ok:
                    self._attach_job_context(recovered.evidence["app"])
                    workflow = self._build_business_workflow(factory)
                    result = workflow.run_on_app(recovered.evidence["app"])
            business_results.append(result)
            if not result.ok:
                return WorkflowResult(
                    ok=False,
                    name=self.name,
                    status=result.status,
                    steps=lifecycle_result.steps,
                    evidence={
                        "lifecycle": lifecycle_result.evidence,
                        "business_results": business_results,
                    },
                    error=result.error,
                    error_type=result.error_type,
                    error_code=result.error_code,
                    side_effect_started=result.side_effect_started,
                    side_effect_committed=result.side_effect_committed,
                    retry_allowed=result.retry_allowed,
                )

        status = business_results[-1].status if business_results else lifecycle_result.status
        return WorkflowResult(
            ok=True,
            name=self.name,
            status=status,
            steps=lifecycle_result.steps,
            evidence={
                "lifecycle": lifecycle_result.evidence,
                "business_results": business_results,
            },
        )

    def _reset_and_wait_for_login(self) -> WorkflowResult:
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=True,
            app_factory=self.app_factory,
        )
        result = lifecycle.run()
        self._attach_job_context(lifecycle.app)
        if not result.ok:
            return result
        return WorkflowResult(
            ok=True,
            name=result.name,
            status=result.status,
            steps=result.steps,
            evidence={**result.evidence, "app": lifecycle.app},
        )

    def _build_business_workflow(self, factory: BusinessWorkflowFactory) -> Any:
        if self.job_context is None:
            return factory(self.config, self.logger)
        if _accepts_job_context(factory):
            return factory(self.config, self.logger, self.job_context)
        return factory(self.config, self.logger)

    def _attach_job_context(self, app: Any) -> None:
        if self.job_context is None:
            return
        app_context = getattr(app, "context", None)
        if app_context is None:
            return
        if hasattr(app_context, "action_policy"):
            app_context.action_policy = self.job_context.action_policy


def _accepts_job_context(factory: BusinessWorkflowFactory) -> bool:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return False
    parameters = list(signature.parameters.values())
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return True
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return True
    return len(parameters) >= 3
