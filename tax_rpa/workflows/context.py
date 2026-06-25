from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.step_runner import StepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


@dataclass(frozen=True)
class WorkflowContext:
    """Shared workflow helper for StepResult execution and WorkflowResult wrapping."""

    workflow: str
    config: PersonImportConfig
    logger: Any
    runtime_options: WorkflowRuntimeOptions
    step_runner: StepRunner | None = None

    def step(
        self,
        step: str,
        operation: Callable[[], StepResult],
        *,
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        """Run a StepResult-producing business step, with optional job instrumentation."""

        def checked_operation() -> StepResult:
            result = operation()
            if not isinstance(result, StepResult):
                raise TypeError("WorkflowContext.step operations must return StepResult")
            return result

        if self.step_runner is None:
            return checked_operation()
        return self.step_runner.run_step(
            workflow=self.workflow,
            step=step,
            operation=checked_operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )

    def result_from_step(
        self,
        result: StepResult,
        *,
        steps: list[StepResult],
        evidence: dict[str, Any],
        side_effect_started: bool | None = None,
        side_effect_committed: bool | None = None,
        retry_allowed: bool | None = None,
    ) -> WorkflowResult:
        """Build a workflow result from one selected final step."""
        return WorkflowResult(
            ok=result.ok,
            name=self.workflow,
            status=result.status,
            steps=steps,
            evidence=evidence,
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=(
                result.side_effect_started
                if side_effect_started is None
                else side_effect_started
            ),
            side_effect_committed=(
                result.side_effect_committed
                if side_effect_committed is None
                else side_effect_committed
            ),
            retry_allowed=result.retry_allowed if retry_allowed is None else retry_allowed,
        )

    def failed_from_step(
        self,
        result: StepResult,
        *,
        steps: list[StepResult],
        evidence: dict[str, Any],
        side_effect_started: bool | None = None,
        side_effect_committed: bool | None = None,
        retry_allowed: bool | None = None,
    ) -> WorkflowResult:
        """Build a failed workflow result from a failed step."""
        return self.result_from_step(
            result,
            steps=steps,
            evidence=evidence,
            side_effect_started=side_effect_started,
            side_effect_committed=side_effect_committed,
            retry_allowed=retry_allowed,
        )
