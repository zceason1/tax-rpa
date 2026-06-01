from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.config.person_import import ImportFileConfig, PersonImportConfig
from tax_rpa.jobs.action_policy import ActionAuditLogger, ActionPolicy
from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.declaration_submission_workflow import (
    DeclarationSubmissionWorkflow,
)
from tax_rpa.workflows.export_report_workflow import ExportReportWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.job_context import WorkflowJobContext
from tax_rpa.workflows.prefill_deduction_workflow import PrefillDeductionWorkflow
from tax_rpa.workflows.tax_calculation_workflow import TaxCalculationWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


class ExistingWorkflowExecutor:
    def __init__(
        self,
        *,
        base_dir: str | Path,
        logger: Any | None = None,
        app_factory: Any | None = None,
        reset: bool = False,
        include_phase5: bool = False,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.logger = logger or NullLogger()
        self.app_factory = app_factory
        self.reset = reset
        self.include_phase5 = include_phase5

    def __call__(self, manifest: JobManifest, artifacts: JobArtifacts) -> dict[str, Any]:
        action_policy = ActionPolicy(
            run_mode=manifest.run_mode,
            job_id=manifest.job_id,
            audit_logger=ActionAuditLogger(artifacts.logs_dir / "actions.jsonl"),
        )
        observability = JobObservability(
            artifacts=artifacts,
            context=JobLogContext(
                job_id=manifest.job_id,
                idempotency_key=manifest.idempotency_key,
                run_mode=manifest.run_mode,
                workflow="combined_tax_workflow",
                step="start",
                attempt=1,
                correlation_id=f"{manifest.job_id}-combined_tax_workflow-start",
            ),
        )
        job_context = WorkflowJobContext(
            manifest=manifest,
            artifacts=artifacts,
            observability=observability,
            action_policy=action_policy,
        )
        workflow = CombinedTaxWorkflow(
            config=self._config(manifest),
            logger=self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
            workflow_factories=self._workflow_factories(),
            job_context=job_context,
        )
        result = workflow.run()
        return _workflow_result_to_executor_result(
            result,
            include_phase5=self.include_phase5,
        )

    def _workflow_factories(self) -> list[Any]:
        factories: list[Any] = [
            lambda config, logger, job_context=None: ImportPersonInfoWorkflow(
                config,
                logger,
                job_context=job_context,
            ),
            lambda config, logger, job_context=None: UpdateSpecialDeductionWorkflow(
                config,
                logger,
                job_context=job_context,
            ),
            lambda config, logger, job_context=None: ImportSalaryIncomeWorkflow(
                config,
                logger,
                job_context=job_context,
            ),
        ]
        if self.include_phase5:
            factories.extend(
                [
                    lambda config, logger, job_context=None: PrefillDeductionWorkflow(
                        config,
                        logger,
                        job_context=job_context,
                    ),
                    lambda config, logger, job_context=None: TaxCalculationWorkflow(
                        config,
                        logger,
                        job_context=job_context,
                    ),
                    lambda config, logger, job_context=None: DeclarationSubmissionWorkflow(
                        config,
                        logger,
                        job_context=job_context,
                    ),
                    lambda config, logger, job_context=None: ExportReportWorkflow(
                        config,
                        logger,
                        job_context=job_context,
                    ),
                ]
            )
        return factories

    def _config(self, manifest: JobManifest) -> PersonImportConfig:
        person_file = self._resolve_manifest_file(manifest, "person_info")
        salary_file = self._resolve_manifest_file(manifest, "salary_income")
        return PersonImportConfig(
            person_info_file=person_file,
            dry_run=manifest.run_mode == "inspect_only",
            imports={
                "person_info": ImportFileConfig(file=person_file),
                "salary_income": ImportFileConfig(file=salary_file),
            },
        )

    def _resolve_manifest_file(self, manifest: JobManifest, role: str) -> Path:
        manifest_file = manifest.files[role]
        path = manifest_file.path
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()


class NullLogger:
    def log(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def step(self, *_args: Any, **_kwargs: Any):
        return nullcontext()

    def screenshot(self, *_args: Any, **_kwargs: Any) -> str:
        return ""

    def write_json(self, _name: str, _data: Any) -> str:
        return ""


def _workflow_result_to_executor_result(
    result: WorkflowResult,
    *,
    include_phase5: bool = False,
) -> dict[str, Any]:
    current_step = _current_step(result)
    return {
        "ok": result.ok,
        "workflow_name": result.name,
        "workflow_status": result.status,
        "business_status": _business_status(result, include_phase5=include_phase5),
        "current_step": current_step,
        "error_type": result.error_type,
        "error_code": result.error_code,
        "message": result.error,
        "side_effect_started": result.side_effect_started,
        "side_effect_committed": result.side_effect_committed,
        "retry_allowed": result.retry_allowed,
        "workflow_result": result,
    }


def _current_step(result: WorkflowResult) -> str | None:
    business_results = result.evidence.get("business_results", [])
    if business_results:
        last_business = business_results[-1]
        if last_business.steps:
            return last_business.steps[-1].name
        return last_business.name
    if result.steps:
        return result.steps[-1].name
    return None


def _business_status(result: WorkflowResult, *, include_phase5: bool) -> str:
    if result.ok:
        return "phase5_workflows_completed" if include_phase5 else "existing_workflows_completed"
    return "phase5_workflow_failed" if include_phase5 else "existing_workflow_failed"
