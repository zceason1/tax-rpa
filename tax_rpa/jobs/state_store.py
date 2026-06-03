import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


ALLOWED_TRANSITIONS = {
    "received": {"validating", "cancelled"},
    "validating": {"queued", "failed", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "blocked", "running_recovered"},
    "running_recovered": {"running", "failed", "blocked"},
    "succeeded": set(),
    "failed": set(),
    "blocked": {"cancelled"},
    "cancelled": set(),
}
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


class StateTransitionError(ValueError):
    """状态流转错误异常，表示作业、状态存储中的特定错误场景。"""
    pass


@dataclass(frozen=True)
class JobStateRecord:
    """作业状态记录，封装作业、状态存储相关状态和行为。"""
    job_id: str
    state: str
    started_at: str
    updated_at: str
    current_workflow: str | None = None
    current_step: str | None = None
    finished_at: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    screenshot_paths: list[str] = field(default_factory=list)
    artifact_manifest_path: str | None = None
    callback_delivery_state: str = "not_configured"


class StateStore:
    """作业状态存储，负责初始化、读取和合法状态流转。"""
    def __init__(self, job_root: str | Path) -> None:
        """初始化状态存储实例，保存依赖、配置和运行上下文。"""
        self.job_root = Path(job_root)
        self.state_path = self.job_root / "state.json"
        self.logs_dir = self.job_root / "logs"
        self.transition_log_path = self.logs_dir / "state_transitions.jsonl"

    def initialize(self, job_id: str) -> JobStateRecord:
        """初始化作业相关目录或状态文件。"""
        now = _now()
        record = JobStateRecord(
            job_id=job_id,
            state="received",
            started_at=now,
            updated_at=now,
        )
        self._write_state(record)
        self._append_transition(
            job_id=job_id,
            from_state=None,
            record=record,
        )
        return record

    def load(self) -> JobStateRecord:
        """读取配置、状态或记录，并转换成当前模块使用的对象。"""
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return JobStateRecord(**data)

    def transition(
        self,
        to_state: str,
        *,
        current_workflow: str | None = None,
        current_step: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        message: str | None = None,
        screenshot_paths: list[str] | None = None,
        artifact_manifest_path: str | None = None,
        callback_delivery_state: str | None = None,
    ) -> JobStateRecord:
        """执行作业状态流转，并写入状态文件和流转日志。"""
        current = self.load()
        _assert_allowed_transition(current.state, to_state)
        now = _now()
        record = JobStateRecord(
            job_id=current.job_id,
            state=to_state,
            started_at=current.started_at,
            updated_at=now,
            current_workflow=current_workflow,
            current_step=current_step,
            finished_at=now if to_state in TERMINAL_STATES else None,
            error_type=error_type,
            error_code=error_code,
            message=message,
            screenshot_paths=screenshot_paths or [],
            artifact_manifest_path=artifact_manifest_path,
            callback_delivery_state=callback_delivery_state
            or current.callback_delivery_state,
        )
        self._write_state(record)
        self._append_transition(
            job_id=current.job_id,
            from_state=current.state,
            record=record,
        )
        return record

    def update_callback_delivery_state(
        self,
        callback_delivery_state: str,
        *,
        artifact_manifest_path: str | None = None,
    ) -> JobStateRecord:
        """更新作业回调投递状态。"""
        current = self.load()
        now = _now()
        record = dataclasses.replace(
            current,
            updated_at=now,
            callback_delivery_state=callback_delivery_state,
            artifact_manifest_path=artifact_manifest_path
            or current.artifact_manifest_path,
        )
        self._write_state(record)
        return record

    def _write_state(self, record: JobStateRecord) -> None:
        """把当前作业状态写入状态文件。"""
        self.job_root.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_name(f"{self.state_path.name}.tmp")
        temp_path.write_text(
            json.dumps(_to_jsonable(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.state_path)

    def _append_transition(
        self,
        *,
        job_id: str,
        from_state: str | None,
        record: JobStateRecord,
    ) -> None:
        """追加一条状态流转记录，便于追踪作业生命周期。"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "time": record.updated_at,
            "job_id": job_id,
            "from_state": from_state,
            "to_state": record.state,
            "current_workflow": record.current_workflow,
            "current_step": record.current_step,
            "error_type": record.error_type,
            "error_code": record.error_code,
            "message": record.message,
            "artifact_manifest_path": record.artifact_manifest_path,
            "callback_delivery_state": record.callback_delivery_state,
        }
        with self.transition_log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_to_jsonable(event), ensure_ascii=False) + "\n")


def _assert_allowed_transition(from_state: str, to_state: str) -> None:
    """执行作业、状态存储中的内部辅助逻辑：assert允许结果流转。"""
    if to_state not in ALLOWED_TRANSITIONS:
        raise StateTransitionError(f"Unknown target state: {to_state}")
    if to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
        raise StateTransitionError(f"Invalid state transition: {from_state} -> {to_state}")


def _now() -> str:
    """生成当前 UTC 时间字符串，供状态和日志落盘使用。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _to_jsonable(value: Any) -> Any:
    """把路径、数据类和嵌套对象转换为可 JSON 序列化结构。"""
    if dataclasses.is_dataclass(value):
        return _to_jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value
