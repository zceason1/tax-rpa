from collections.abc import Callable
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.recovery_policy import is_recoverable_environment_failure


BusinessWorkflowFactory = Callable[[PersonImportConfig, Any], Any]


class CombinedTaxWorkflow:
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        workflow_factories: list[BusinessWorkflowFactory],
        reset: bool = False,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        name: str = "combined_tax_workflow",
    ) -> None:
        self.config = config
        self.logger = logger
        self.workflow_factories = workflow_factories
        self.reset = reset
        self.app_factory = app_factory
        self.name = name

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
                name=self.name,
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                evidence={"lifecycle": lifecycle_result.evidence},
                error=lifecycle_result.error,
            )

        business_results: list[WorkflowResult] = []
        for factory in self.workflow_factories:
            workflow = factory(self.config, self.logger)
            result = workflow.run_on_app(lifecycle.app)
            if not result.ok and is_recoverable_environment_failure(result):
                recovered = self._reset_and_wait_for_login()
                if recovered.ok:
                    workflow = factory(self.config, self.logger)
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
        if not result.ok:
            return result
        return WorkflowResult(
            ok=True,
            name=result.name,
            status=result.status,
            steps=result.steps,
            evidence={**result.evidence, "app": lifecycle.app},
        )
