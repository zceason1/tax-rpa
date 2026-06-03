from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.config.person_import import ImportFileConfig, PersonImportConfig
from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
from tax_rpa.runtime.action_policy import ActionAuditLogger, ActionPolicy
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.declaration_submission_workflow import (
    DeclarationSubmissionWorkflow,
)
from tax_rpa.workflows.export_report_workflow import ExportReportWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.prefill_deduction_workflow import PrefillDeductionWorkflow
from tax_rpa.workflows.tax_calculation_workflow import TaxCalculationWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


class ExistingWorkflowExecutor:
    """既有工作流执行器，负责把作业清单转换为当前 UI 工作流执行。"""
    def __init__(
        self,
        *,
        base_dir: str | Path,
        logger: Any | None = None,
        app_factory: Any | None = None,
        reset: bool = False,
        include_phase5: bool = False,
    ) -> None:
        """初始化既有工作流执行器实例，保存依赖、配置和运行上下文。"""
        self.base_dir = Path(base_dir)
        self.logger = logger or NullLogger()
        self.app_factory = app_factory
        self.reset = reset
        self.include_phase5 = include_phase5

    def __call__(self, manifest: JobManifest, artifacts: JobArtifacts) -> dict[str, Any]:
        """让实例可以像函数一样执行，作为作业执行器或适配器入口。"""
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
        step_runner = JobStepRunner(
            manifest=manifest,
            artifacts=artifacts,
            observability=observability,
        )
        runtime_options = WorkflowRuntimeOptions(
            run_mode=manifest.run_mode,
            allow_skip_personal_pension=manifest.allow_skip_personal_pension,
        )
        workflow = CombinedTaxWorkflow(
            config=self._config(manifest),
            logger=self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
            workflow_factories=self._workflow_factories(),
            step_runner=step_runner,
            runtime_options=runtime_options,
            action_policy=action_policy,
        )
        result = workflow.run()
        return _workflow_result_to_executor_result(
            result,
            include_phase5=self.include_phase5,
        )

    def _workflow_factories(self) -> list[Any]:
        """执行作业、既有工作流执行器中的内部辅助逻辑：工作流factories。"""
        factories: list[Any] = [
            lambda config, logger, step_runner=None, runtime_options=None: ImportPersonInfoWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
            lambda config, logger, step_runner=None, runtime_options=None: UpdateSpecialDeductionWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
            lambda config, logger, step_runner=None, runtime_options=None: ImportSalaryIncomeWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
        ]
        if self.include_phase5:
            factories.extend(
                [
                    lambda config, logger, step_runner=None, runtime_options=None: PrefillDeductionWorkflow(
                        config,
                        logger,
                        step_runner=step_runner,
                        runtime_options=runtime_options,
                    ),
                    lambda config, logger, step_runner=None, runtime_options=None: TaxCalculationWorkflow(
                        config,
                        logger,
                        step_runner=step_runner,
                        runtime_options=runtime_options,
                    ),
                    lambda config, logger, step_runner=None, runtime_options=None: DeclarationSubmissionWorkflow(
                        config,
                        logger,
                        step_runner=step_runner,
                        runtime_options=runtime_options,
                    ),
                    lambda config, logger, step_runner=None, runtime_options=None: ExportReportWorkflow(
                        config,
                        logger,
                        step_runner=step_runner,
                        runtime_options=runtime_options,
                    ),
                ]
            )
        return factories

    def _config(self, manifest: JobManifest) -> PersonImportConfig:
        """执行作业、既有工作流执行器中的内部辅助逻辑：配置。"""
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
        """解析清单文件，并转换为后续流程需要的规范形式。"""
        manifest_file = manifest.files[role]
        path = manifest_file.path
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()


class NullLogger:
    """null日志，封装作业、既有工作流执行器相关状态和行为。"""
    def log(self, *_args: Any, **_kwargs: Any) -> None:
        """写入日志事件，记录当前动作或状态。"""
        return None

    def step(self, *_args: Any, **_kwargs: Any):
        """创建页面局部步骤上下文，用于记录日志和截图。"""
        return nullcontext()

    def screenshot(self, *_args: Any, **_kwargs: Any) -> str:
        """执行作业、既有工作流执行器中的截图逻辑，供业务流程或相邻模块调用。"""
        return ""

    def write_json(self, _name: str, _data: Any) -> str:
        """把数据写入作业产物目录下的 JSON 文件。"""
        return ""


def _workflow_result_to_executor_result(
    result: WorkflowResult,
    *,
    include_phase5: bool = False,
) -> dict[str, Any]:
    """执行作业、既有工作流执行器中的内部辅助逻辑：工作流结果to执行器结果。"""
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
    """执行作业、既有工作流执行器中的内部辅助逻辑：当前步骤。"""
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
    """执行作业、既有工作流执行器中的内部辅助逻辑：业务状态。"""
    if result.ok:
        return "phase5_workflows_completed" if include_phase5 else "existing_workflows_completed"
    return "phase5_workflow_failed" if include_phase5 else "existing_workflow_failed"
