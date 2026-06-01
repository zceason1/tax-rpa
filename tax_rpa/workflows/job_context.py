from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tax_rpa.jobs.action_policy import ActionPolicy
from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.result_matrix import classify_step_result


@dataclass
class WorkflowJobContext:
    manifest: JobManifest
    artifacts: JobArtifacts
    observability: JobObservability
    action_policy: ActionPolicy
    attempt: int = 1
    _sequence: int = field(default=0, init=False)

    def run_step(
        self,
        *,
        workflow: str,
        step: str,
        operation: Callable[[], StepResult],
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        step_observability = self._step_observability(workflow, step)
        step_observability.write_step_journal("step_start", "started")
        step_observability.log_step("step_start", "started")
        if side_effect_step:
            step_observability.write_step_journal(
                "side_effect_started",
                "started",
                side_effect_expected=True,
            )
        try:
            result = operation()
        except Exception as exc:
            step_observability.write_step_journal(
                "step_exception",
                "failed",
                error=str(exc),
            )
            step_observability.log_step(
                "step_exception",
                "failed",
                error=str(exc),
            )
            raise

        result_matrix = (
            classify_step_result(matrix_step, result) if matrix_step else None
        )
        if side_effect_step and (result.ok or result.side_effect_committed):
            step_observability.write_step_journal(
                "side_effect_committed",
                "committed",
                side_effect_expected=True,
                side_effect_started=True,
                side_effect_committed=True,
            )
        step_data = {
            "result_name": result.name,
            "error": result.error,
            "error_type": result.error_type,
            "error_code": result.error_code,
            "side_effect_started": result.side_effect_started,
            "side_effect_committed": result.side_effect_committed,
            "retry_allowed": result.retry_allowed,
            "result_matrix": result_matrix,
        }
        step_observability.write_step_journal(
            "step_result",
            result.status,
            **step_data,
        )
        step_observability.log_step("step_result", result.status, **step_data)
        return result

    def _step_observability(self, workflow: str, step: str) -> JobObservability:
        self._sequence += 1
        return self.observability.with_context(
            JobLogContext(
                job_id=self.manifest.job_id,
                idempotency_key=self.manifest.idempotency_key,
                run_mode=self.manifest.run_mode,
                workflow=workflow,
                step=step,
                attempt=self.attempt,
                correlation_id=(
                    f"{self.manifest.job_id}-{workflow}-{step}-{self._sequence}"
                ),
            )
        )
