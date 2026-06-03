from collections.abc import Callable
from dataclasses import dataclass, field

from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.runtime.result_matrix import classify_step_result
from tax_rpa.runtime.result import StepResult


@dataclass
class JobStepRunner:
    """作业步骤执行器，负责在作业上下文中执行步骤并记录观测数据。"""
    manifest: JobManifest
    artifacts: JobArtifacts
    observability: JobObservability
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
        """执行作业、工作流步骤执行器中的run步骤逻辑，供业务流程或相邻模块调用。"""
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
        """执行作业、工作流步骤执行器中的内部辅助逻辑：步骤可观测性。"""
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
