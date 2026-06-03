from collections.abc import Callable
import json
from pathlib import Path
import traceback
from typing import Any
from uuid import uuid4

from tax_rpa.jobs.artifact_manifest import ArtifactManifestWriter
from tax_rpa.jobs.artifact_store import ArtifactStore, JobArtifacts
from tax_rpa.jobs.callback_outbox import CallbackOutbox, Transport
from tax_rpa.jobs.lock import UiRunnerLock
from tax_rpa.jobs.machine_config import MachineConfigValidator
from tax_rpa.jobs.manifest import JobManifest, load_job_manifest
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.jobs.preflight import PreflightIssue, PreflightResult, PreflightValidator
from tax_rpa.jobs.redaction import redact_sensitive
from tax_rpa.jobs.runtime_metadata import RuntimeMetadata
from tax_rpa.jobs.state_store import StateStore


JobExecutor = Callable[[JobManifest, JobArtifacts], dict[str, Any]]


class JobRunner:
    """作业运行器，负责预检、执行工作流、落盘状态、回调和终态汇总。"""
    def __init__(
        self,
        *,
        artifacts_root: str | Path = Path("artifacts/jobs"),
        lock_path: str | Path = Path("artifacts/runner.lock.json"),
        executor: JobExecutor | None = None,
        screenshot_grabber: Any | None = None,
        callback_transport: Transport | None = None,
        callback_secret: str | None = None,
        machine_config_path: str | Path | None = None,
        runtime_metadata_collector: Callable[[], RuntimeMetadata | dict[str, Any]]
        | None = None,
    ) -> None:
        """初始化作业执行器实例，保存依赖、配置和运行上下文。"""
        self.artifacts_root = Path(artifacts_root)
        self.lock_path = Path(lock_path)
        self.executor = executor or _fake_executor
        self.screenshot_grabber = screenshot_grabber
        self.callback_transport = callback_transport
        self.callback_secret = callback_secret
        self.machine_config_path = Path(machine_config_path) if machine_config_path else None
        self.runtime_metadata_collector = runtime_metadata_collector

    def run(self, manifest_path: str | Path, base_dir: str | Path | None = None) -> dict[str, Any]:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        manifest_path = Path(manifest_path)
        manifest = load_job_manifest(manifest_path)
        job_base_dir = Path(base_dir) if base_dir is not None else manifest_path.parent
        runtime_metadata = self._collect_runtime_metadata()
        machine_config_summary: dict[str, Any] | None = None
        artifacts = ArtifactStore(self.artifacts_root).for_job(manifest.job_id)
        artifacts.initialize()
        observability = JobObservability(
            artifacts=artifacts,
            context=_context(manifest, workflow="job_runner", step="intake"),
            screenshot_grabber=self.screenshot_grabber,
        )
        state_store = StateStore(artifacts.root)
        state_store.initialize(manifest.job_id)
        artifacts.write_json("manifest.normalized.json", manifest)
        observability.log_job_event("job_started", "started", manifest_path=manifest_path)

        state_store.transition("validating", current_step="preflight")
        preflight_observability = observability.with_context(
            _context(manifest, workflow="job_runner", step="preflight")
        )
        preflight_observability.write_step_journal("step_start", "started")
        file_preflight = PreflightValidator(job_base_dir).validate(manifest)
        machine_config_issues: list[PreflightIssue] = []
        if self.machine_config_path is not None:
            machine_config_result = MachineConfigValidator(self.machine_config_path).validate()
            machine_config_issues = machine_config_result.issues
            if machine_config_result.config is not None:
                machine_config_summary = machine_config_result.config.to_summary_dict()
        preflight = PreflightResult(
            issues=[*file_preflight.issues, *machine_config_issues]
        )
        if not preflight.ok:
            issue = preflight.issues[0]
            preflight_observability.log_preflight(
                "preflight_failed",
                "failed",
                issues=[_issue_to_dict(item) for item in preflight.issues],
            )
            preflight_observability.write_step_journal(
                "step_failed",
                "failed",
                error_type=issue.error_type,
                error_code=issue.error_code,
                message=issue.message,
            )
            state_store.transition(
                "failed",
                current_step="preflight",
                error_type=issue.error_type,
                error_code=issue.error_code,
                message=issue.message,
            )
            failed_path = preflight_observability.write_failed_package(
                error=_error_object(
                    error_type=issue.error_type,
                    error_code=issue.error_code,
                    message=issue.message,
                    workflow="job_runner",
                    step="preflight",
                ),
                traceback_text=None,
                primary_failure_screenshot=None,
            )
            return self._finalize_terminal_job(
                manifest=manifest,
                artifacts=artifacts,
                state_store=state_store,
                observability=preflight_observability,
                state="failed",
                preflight=preflight,
                error_type=issue.error_type,
                error_code=issue.error_code,
                message=issue.message,
                failed_path=failed_path,
                primary_failure_screenshot=None,
                runtime_metadata=runtime_metadata,
                machine_config=machine_config_summary,
            )

        state_store.transition("queued")
        preflight_observability.log_preflight("preflight_passed", "passed")
        preflight_observability.write_step_journal("step_result", "passed")
        executor_result: dict[str, Any] = {}
        executor_observability = observability.with_context(
            _context(manifest, workflow="fake_job", step="executor")
        )
        try:
            with UiRunnerLock(self.lock_path).acquire(manifest.job_id):
                state_store.transition("running", current_workflow="fake_job")
                executor_observability.write_step_journal("step_start", "started")
                executor_observability.log_action(
                    "executor_started",
                    "started",
                    label="fake_job.executor",
                )
                executor_result = self.executor(manifest, artifacts)
                executor_observability.log_action(
                    "executor_completed",
                    "passed",
                    label="fake_job.executor",
                )
                executor_observability.write_step_journal("step_result", "passed")
                if _executor_result_failed(executor_result):
                    failure_observability = observability.with_context(
                        _context(
                            manifest,
                            workflow=executor_result.get("workflow_name") or "fake_job",
                            step=executor_result.get("current_step") or "executor",
                        )
                    )
                    error_type = executor_result.get("error_type") or "UNKNOWN_RESULT"
                    error_code = executor_result.get("error_code") or "workflow_failed"
                    message = executor_result.get("message") or executor_result.get(
                        "workflow_status",
                        "Workflow failed",
                    )
                    failure_observability.log_action(
                        "executor_business_failed",
                        "failed",
                        label="existing_workflows",
                        error_type=error_type,
                        error_code=error_code,
                        message=message,
                    )
                    failure_observability.write_step_journal(
                        "step_failed",
                        "failed",
                        error_type=error_type,
                        error_code=error_code,
                        message=message,
                    )
                    primary_failure_screenshot = (
                        failure_observability.capture_full_screen("workflow_failed")
                    )
                    state_store.transition(
                        "failed",
                        current_workflow=executor_result.get("workflow_name"),
                        current_step=executor_result.get("current_step"),
                        error_type=error_type,
                        error_code=error_code,
                        message=message,
                        screenshot_paths=[primary_failure_screenshot]
                        if primary_failure_screenshot
                        else None,
                    )
                    failed_path = failure_observability.write_failed_package(
                        error=_error_object(
                            error_type=error_type,
                            error_code=error_code,
                            message=message,
                            workflow=executor_result.get("workflow_name") or "fake_job",
                            step=executor_result.get("current_step") or "executor",
                        ),
                        traceback_text=None,
                        primary_failure_screenshot=primary_failure_screenshot,
                    )
                    return self._finalize_terminal_job(
                        manifest=manifest,
                        artifacts=artifacts,
                        state_store=state_store,
                        observability=failure_observability,
                        state="failed",
                        preflight=preflight,
                        executor_result=executor_result,
                        error_type=error_type,
                        error_code=error_code,
                        message=message,
                        failed_path=failed_path,
                        primary_failure_screenshot=primary_failure_screenshot,
                        runtime_metadata=runtime_metadata,
                        machine_config=machine_config_summary,
                    )
                state_store.transition("succeeded", current_workflow="fake_job")
        except Exception as exc:
            traceback_text = traceback.format_exc()
            executor_observability.log_action(
                "executor_failed",
                "failed",
                label="fake_job.executor",
                error_type="SYSTEM_ERROR",
                error_code="job_executor_failed",
                message=str(exc),
            )
            executor_observability.write_step_journal(
                "step_failed",
                "failed",
                error_type="SYSTEM_ERROR",
                error_code="job_executor_failed",
                message=str(exc),
            )
            primary_failure_screenshot = executor_observability.capture_full_screen(
                "job_executor_failed"
            )
            state_store.transition(
                "failed",
                current_workflow="fake_job",
                current_step="executor",
                error_type="SYSTEM_ERROR",
                error_code="job_executor_failed",
                message=str(exc),
                screenshot_paths=[primary_failure_screenshot]
                if primary_failure_screenshot
                else None,
            )
            failed_path = executor_observability.write_failed_package(
                error=_error_object(
                    error_type="SYSTEM_ERROR",
                    error_code="job_executor_failed",
                    message=str(exc),
                    workflow="fake_job",
                    step="executor",
                ),
                traceback_text=traceback_text,
                primary_failure_screenshot=primary_failure_screenshot,
            )
            return self._finalize_terminal_job(
                manifest=manifest,
                artifacts=artifacts,
                state_store=state_store,
                observability=executor_observability,
                state="failed",
                preflight=preflight,
                executor_result=executor_result,
                error_type="SYSTEM_ERROR",
                error_code="job_executor_failed",
                message=str(exc),
                failed_path=failed_path,
                primary_failure_screenshot=primary_failure_screenshot,
                runtime_metadata=runtime_metadata,
                machine_config=machine_config_summary,
            )

        return self._finalize_terminal_job(
            manifest=manifest,
            artifacts=artifacts,
            state_store=state_store,
            observability=observability.with_context(
                _context(manifest, workflow="fake_job", step="executor")
            ),
            state="succeeded",
            preflight=preflight,
            executor_result=executor_result,
            runtime_metadata=runtime_metadata,
            machine_config=machine_config_summary,
        )

    def _collect_runtime_metadata(self) -> dict[str, Any]:
        """执行作业、执行器中的内部辅助逻辑：collect运行时元数据。"""
        if self.runtime_metadata_collector is None:
            metadata: RuntimeMetadata | dict[str, Any] = RuntimeMetadata.collect()
        else:
            metadata = self.runtime_metadata_collector()
        if isinstance(metadata, RuntimeMetadata):
            return metadata.to_dict()
        return dict(metadata)

    def _finalize_terminal_job(
        self,
        *,
        manifest: JobManifest,
        artifacts: JobArtifacts,
        state_store: StateStore,
        observability: JobObservability,
        state: str,
        preflight: PreflightResult,
        executor_result: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
        failed_path: str | None = None,
        primary_failure_screenshot: str | None = None,
        runtime_metadata: dict[str, Any] | None = None,
        machine_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行作业、执行器中的内部辅助逻辑：finalizeterminal作业。"""
        error = (
            _error_object(
                error_type=error_type,
                error_code=error_code or "workflow_failed",
                message=message or "",
                workflow=(executor_result or {}).get("workflow_name") or "job_runner",
                step=(executor_result or {}).get("current_step") or "finalize",
            )
            if error_type
            else None
        )
        business_status = _business_status(
            state=state,
            executor_result=executor_result,
            error_code=error_code,
        )
        callback_result = CallbackOutbox(
            artifacts=artifacts,
            callback_url=manifest.callback_url,
            callback_secret=self.callback_secret,
            transport=self.callback_transport,
        ).deliver(
            _callback_payload(
                manifest=manifest,
                state=state,
                business_status=business_status,
                error=error,
            )
        )
        state_store.update_callback_delivery_state(
            callback_result.callback_state,
            artifact_manifest_path="artifact_manifest.json",
        )
        summary = _summary(
            manifest=manifest,
            artifacts=artifacts,
            state=state,
            preflight=preflight,
            executor_result=executor_result,
            error=error,
            error_type=error_type,
            error_code=error_code,
            message=message,
            primary_failure_screenshot=primary_failure_screenshot,
            business_status=business_status,
            callback_state=callback_result.callback_state,
            callback_outbox_record=callback_result.outbox_record_path,
            runtime_metadata=runtime_metadata,
            machine_config=machine_config,
        )
        summary_path = artifacts.write_json("summary.json", summary)
        troubleshooting_path = observability.write_troubleshooting_index(
            summary_path=summary_path,
            failed_path=failed_path,
            primary_failure_screenshot=primary_failure_screenshot,
            callback_outbox_record=callback_result.outbox_record_path,
        )
        artifact_manifest_path = ArtifactManifestWriter(artifacts).write(
            job_id=manifest.job_id,
            final_status=state,
            callback_status=callback_result.callback_state,
        )
        summary["artifacts"]["manifest"] = artifact_manifest_path
        summary["artifacts"]["troubleshooting_index"] = troubleshooting_path
        artifacts.write_json("summary.json", summary)
        return summary


def _fake_executor(_manifest: JobManifest, _artifacts: JobArtifacts) -> dict[str, Any]:
    """执行作业、执行器中的内部辅助逻辑：fake执行器。"""
    return {"workflow_status": "fake_completed"}


def _summary(
    *,
    manifest: JobManifest,
    artifacts: JobArtifacts,
    state: str,
    preflight: PreflightResult,
    executor_result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    error_type: str | None = None,
    error_code: str | None = None,
    message: str | None = None,
    primary_failure_screenshot: str | None = None,
    business_status: str | None = None,
    callback_state: str = "not_configured",
    callback_outbox_record: str | None = None,
    runtime_metadata: dict[str, Any] | None = None,
    machine_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行作业、执行器中的内部辅助逻辑：摘要。"""
    state_record = _read_json_if_exists(artifacts.root / "state.json") or {}
    return {
        "job_id": manifest.job_id,
        "state": state,
        "business_status": business_status or state,
        "tax_period": manifest.tax_period,
        "run_mode": manifest.run_mode,
        "company_name": manifest.company_name,
        "credit_code": manifest.credit_code,
        "started_at": state_record.get("started_at"),
        "finished_at": state_record.get("finished_at"),
        "current_workflow": state_record.get("current_workflow")
        or (executor_result or {}).get("workflow_name"),
        "current_step": state_record.get("current_step")
        or (executor_result or {}).get("current_step"),
        "manifest_extra": redact_sensitive(manifest.manifest_extra),
        "runtime": runtime_metadata or RuntimeMetadata.collect().to_dict(),
        "machine_config": machine_config,
        "artifact_root": artifacts.root.as_posix(),
        "preflight": {
            "ok": preflight.ok,
            "issues": [_issue_to_dict(issue) for issue in preflight.issues],
        },
        "executor_result": executor_result or {},
        "error": error,
        "error_type": error_type,
        "error_code": error_code,
        "message": message,
        "callback_state": callback_state,
        "callback_outbox_record": callback_outbox_record,
        "primary_failure_screenshot": primary_failure_screenshot,
        "artifacts": {
            "manifest": "artifact_manifest.json",
            "summary": "summary.json",
            "state": "state.json",
            "steps": "logs/steps.jsonl",
            "callbacks": "logs/callbacks.jsonl",
            "troubleshooting_index": "troubleshooting_index.json",
            "failed": "logs/failed.json" if state == "failed" else None,
        },
    }


def _issue_to_dict(issue: PreflightIssue) -> dict[str, Any]:
    """执行作业、执行器中的内部辅助逻辑：问题todict。"""
    return {
        "role": issue.role,
        "path": issue.path,
        "error_type": issue.error_type,
        "error_code": issue.error_code,
        "message": issue.message,
    }


def _executor_result_failed(result: dict[str, Any]) -> bool:
    """执行作业、执行器中的内部辅助逻辑：执行器结果failed。"""
    return result.get("ok") is False


def _business_status(
    *,
    state: str,
    executor_result: dict[str, Any] | None,
    error_code: str | None,
) -> str:
    """执行作业、执行器中的内部辅助逻辑：业务状态。"""
    if executor_result:
        return (
            executor_result.get("business_status")
            or executor_result.get("workflow_status")
            or state
        )
    if error_code:
        return error_code
    return state


def _callback_payload(
    *,
    manifest: JobManifest,
    state: str,
    business_status: str,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    """执行作业、执行器中的内部辅助逻辑：回调载荷。"""
    return {
        "job_id": manifest.job_id,
        "idempotency_key": manifest.idempotency_key,
        "state": state,
        "business_status": business_status,
        "error": error,
        "summary_path": "summary.json",
        "artifact_manifest_path": "artifact_manifest.json",
    }


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    """在文件存在时读取 JSON，不存在时返回空结果。"""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _context(manifest: JobManifest, *, workflow: str, step: str) -> JobLogContext:
    """执行作业、执行器中的内部辅助逻辑：上下文。"""
    return JobLogContext(
        job_id=manifest.job_id,
        idempotency_key=manifest.idempotency_key,
        run_mode=manifest.run_mode,
        workflow=workflow,
        step=step,
        attempt=1,
        correlation_id=f"{manifest.job_id}-{workflow}-{step}-{uuid4().hex}",
    )


def _error_object(
    *,
    error_type: str,
    error_code: str,
    message: str,
    workflow: str,
    step: str,
) -> dict[str, Any]:
    """执行作业、执行器中的内部辅助逻辑：错误object。"""
    return {
        "type": error_type,
        "code": error_code,
        "message": message,
        "workflow": workflow,
        "step": step,
        "retry_allowed": False,
        "side_effect_committed": False,
    }
