import dataclasses
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tax_rpa.jobs.artifact_store import JobArtifacts


SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "authorization",
    "cookie",
)


@dataclass(frozen=True)
class JobLogContext:
    """作业log上下文，封装作业、可观测性相关状态和行为。"""
    job_id: str
    idempotency_key: str
    run_mode: str
    workflow: str
    step: str
    attempt: int
    correlation_id: str

    def with_step(
        self,
        *,
        workflow: str | None = None,
        step: str | None = None,
        attempt: int | None = None,
        correlation_id: str | None = None,
    ) -> "JobLogContext":
        """基于现有作业上下文派生步骤级上下文。"""
        return dataclasses.replace(
            self,
            workflow=workflow or self.workflow,
            step=step or self.step,
            attempt=attempt or self.attempt,
            correlation_id=correlation_id or self.correlation_id,
        )


class JobObservability:
    """作业可观测性工具，负责结构化日志、截图和故障包。"""
    def __init__(
        self,
        *,
        artifacts: JobArtifacts,
        context: JobLogContext,
        screenshot_grabber: Any | None = None,
    ) -> None:
        """初始化作业可观测性实例，保存依赖、配置和运行上下文。"""
        self.artifacts = artifacts
        self.context = context
        self.screenshot_grabber = screenshot_grabber

    def with_context(self, context: JobLogContext) -> "JobObservability":
        """基于现有观测器派生带新作业上下文的观测器。"""
        return JobObservability(
            artifacts=self.artifacts,
            context=context,
            screenshot_grabber=self.screenshot_grabber,
        )

    def log_job_event(self, event: str, status: str, **data: Any) -> None:
        """记录作业级事件。"""
        self._write_jsonl("job_events", event, status, data)

    def log_step(self, event: str, status: str, **data: Any) -> None:
        """记录步骤级事件。"""
        self._write_jsonl("steps", event, status, data)

    def write_step_journal(self, event: str, status: str, **data: Any) -> None:
        """写入步骤流水日志，记录步骤开始、完成或失败。"""
        self._write_jsonl("step_journal", event, status, data)

    def log_action(self, event: str, status: str, **data: Any) -> None:
        """记录 UI 动作事件。"""
        self._write_jsonl("actions", event, status, data)

    def log_ocr(self, event: str, status: str, **data: Any) -> None:
        """记录 OCR 识别事件。"""
        self._write_jsonl("ocr", event, status, data)

    def log_dialog(self, event: str, status: str, **data: Any) -> None:
        """记录弹窗处理事件。"""
        self._write_jsonl("dialogs", event, status, data)

    def log_window(self, event: str, status: str, **data: Any) -> None:
        """记录窗口发现和切换事件。"""
        self._write_jsonl("windows", event, status, data)

    def log_preflight(self, event: str, status: str, **data: Any) -> None:
        """记录预检事件。"""
        self._write_jsonl("preflight", event, status, data)

    def write_ocr_json(self, correlation_id: str, data: dict[str, Any]) -> str:
        """写入 OCR 识别详情 JSON。"""
        filename = f"{_safe_filename(correlation_id)}.json"
        return self.artifacts.write_json(Path("ocr") / filename, data)

    def capture_full_screen(self, name: str) -> str | None:
        """截取全屏截图并写入作业截图目录。"""
        self.artifacts.screenshots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{_safe_filename(name)}.png"
        target = self.artifacts.screenshots_dir / filename
        relative_path = target.relative_to(self.artifacts.root).as_posix()
        try:
            if self.screenshot_grabber is not None:
                self.screenshot_grabber(target)
            else:
                _grab_full_screen(target)
        except Exception as exc:
            self.log_job_event(
                "screenshot_capture_failed",
                "failed",
                screenshot_type="full_screen",
                target_path=relative_path,
                error=str(exc),
            )
            return None

        self.log_job_event(
            "screenshot_captured",
            "captured",
            screenshot_type="full_screen",
            screenshot_path=relative_path,
        )
        return relative_path

    def write_failed_package(
        self,
        *,
        error: dict[str, Any],
        traceback_text: str | None,
        primary_failure_screenshot: str | None,
    ) -> str:
        """生成故障排查包，汇总截图、日志和最近事件。"""
        failed = {
            **self._context_fields(),
            "error": error,
            "traceback": traceback_text,
            "primary_failure_screenshot": primary_failure_screenshot,
            "state_snapshot": self._read_json_if_exists("state.json"),
            "current_step_journal_entry": self._latest_event("step_journal"),
            "latest_action_event": self._latest_event("actions"),
            "latest_ocr_event": self._latest_event("ocr"),
            "latest_dialog_event": self._latest_event("dialogs"),
            "latest_window_snapshot": self._latest_event("windows"),
        }
        return self.artifacts.write_json("logs/failed.json", _redact(failed))

    def write_troubleshooting_index(
        self,
        *,
        summary_path: str,
        state_path: str = "state.json",
        failed_path: str | None = None,
        primary_failure_screenshot: str | None = None,
        last_main_window_screenshot: str | None = None,
        last_ocr_json: str | None = None,
        exported_files: list[str] | None = None,
        callback_outbox_record: str | None = None,
    ) -> str:
        """写入故障排查索引，帮助快速定位失败现场。"""
        latest_action = self._latest_event("actions")
        latest_ocr = self._latest_event("ocr")
        latest_dialog = self._latest_event("dialogs")
        latest_window = self._latest_event("windows")
        current_step = self._latest_event("step_journal")
        last_full_screen = self._latest_full_screen_screenshot()
        if last_full_screen is None:
            last_full_screen = primary_failure_screenshot

        index = {
            **self._context_fields(),
            "summary": summary_path,
            "state": state_path,
            "failed": failed_path,
            "primary_failure_screenshot": primary_failure_screenshot,
            "last_full_screen_screenshot": last_full_screen,
            "last_main_window_screenshot": last_main_window_screenshot,
            "last_ocr_json": last_ocr_json or _read_key(latest_ocr, "ocr_json_path"),
            "last_popup_text": _read_key(latest_dialog, "text"),
            "latest_action_event": latest_action,
            "latest_ocr_event": latest_ocr,
            "latest_dialog_event": latest_dialog,
            "latest_window_event": latest_window,
            "current_step_journal_entry": current_step,
            "exported_files": exported_files
            if exported_files is not None
            else self._relative_files(self.artifacts.exported_dir),
            "callback_outbox_record": callback_outbox_record,
        }
        return self.artifacts.write_json("troubleshooting_index.json", _redact(index))

    def _write_jsonl(
        self,
        log_name: str,
        event: str,
        status: str,
        data: dict[str, Any],
    ) -> None:
        """向 JSONL 日志文件追加一条结构化事件。"""
        self.artifacts.logs_dir.mkdir(parents=True, exist_ok=True)
        item = {
            "time": _now(),
            **self._context_fields(),
            "event": event,
            "status": status,
            **data,
        }
        path = self.artifacts.logs_dir / f"{log_name}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(_redact(item), ensure_ascii=False) + "\n")

    def _context_fields(self) -> dict[str, Any]:
        """生成当前观测上下文的公共字段。"""
        return {
            "job_id": self.context.job_id,
            "idempotency_key": self.context.idempotency_key,
            "run_mode": self.context.run_mode,
            "workflow": self.context.workflow,
            "step": self.context.step,
            "attempt": self.context.attempt,
            "correlation_id": self.context.correlation_id,
        }

    def _latest_full_screen_screenshot(self) -> str | None:
        """查找最近一次全屏截图路径。"""
        for event in reversed(self._events("job_events")):
            if (
                event.get("event") == "screenshot_captured"
                and event.get("screenshot_type") == "full_screen"
            ):
                return event.get("screenshot_path")
        return None

    def _latest_event(self, log_name: str) -> dict[str, Any] | None:
        """读取指定日志中的最近一条事件。"""
        events = self._events(log_name)
        return events[-1] if events else None

    def _events(self, log_name: str) -> list[dict[str, Any]]:
        """读取指定 JSONL 日志中的全部事件。"""
        path = self.artifacts.logs_dir / f"{log_name}.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(json.loads(line))
        return events

    def _read_json_if_exists(self, relative_path: str) -> dict[str, Any] | None:
        """在文件存在时读取 JSON，不存在时返回空结果。"""
        path = self.artifacts.root / relative_path
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _relative_files(self, directory: Path) -> list[str]:
        """列出目录下相对作业根目录的文件路径。"""
        if not directory.exists():
            return []
        return [
            path.relative_to(self.artifacts.root).as_posix()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ]


def _now() -> str:
    """生成当前 UTC 时间字符串，供状态和日志落盘使用。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _grab_full_screen(path: Path) -> None:
    """执行作业、可观测性中的内部辅助逻辑：grabfull屏幕。"""
    from PIL import ImageGrab

    ImageGrab.grab().save(path)


def _safe_filename(value: str) -> str:
    """安全处理filename，异常时返回可控默认值。"""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "screenshot"


def _read_key(event: dict[str, Any] | None, key: str) -> Any | None:
    """读取key，并处理缺失或异常情况。"""
    if event is None:
        return None
    return event.get(key)


def _redact(value: Any, key: str | None = None) -> Any:
    """执行作业、可观测性中的内部辅助逻辑：redact。"""
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if dataclasses.is_dataclass(value):
        return _redact(dataclasses.asdict(value), key=key)
    if isinstance(value, dict):
        return {str(item_key): _redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_redact(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _is_sensitive_key(key: str) -> bool:
    """判断字段名是否属于敏感信息。"""
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
