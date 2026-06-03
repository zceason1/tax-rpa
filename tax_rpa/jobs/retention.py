import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


PRESERVED_CALLBACK_STATES = {"pending", "dead_letter"}
LEGACY_RUN_PREFIX = "person_import_"


@dataclass(frozen=True)
class RetentionPolicy:
    """保留清理策略，封装作业、保留清理相关状态和行为。"""
    success_days: int = 30
    failed_days: int = 90


@dataclass
class RetentionReport:
    """保留清理报表，封装作业、保留清理相关状态和行为。"""
    deleted_jobs: list[str] = field(default_factory=list)
    preserved_jobs: list[str] = field(default_factory=list)
    skipped_jobs: list[str] = field(default_factory=list)


class RetentionCleaner:
    """产物保留清理器，负责删除过期作业和旧版运行目录。"""
    def __init__(
        self,
        artifacts_root: str | Path,
        *,
        policy: RetentionPolicy | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """初始化保留清理cleaner实例，保存依赖、配置和运行上下文。"""
        self.artifacts_root = Path(artifacts_root)
        self.policy = policy or RetentionPolicy()
        self.now = now or (lambda: datetime.now().astimezone())

    def cleanup(self) -> RetentionReport:
        """执行产物清理并返回清理报告。"""
        report = RetentionReport()
        if not self.artifacts_root.exists():
            return report

        for job_root in sorted(path for path in self.artifacts_root.iterdir() if path.is_dir()):
            state_path = job_root / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
            else:
                state = self._legacy_run_state(job_root)
            if state is None:
                report.skipped_jobs.append(job_root.name)
                continue
            if state.get("callback_delivery_state") in PRESERVED_CALLBACK_STATES:
                report.preserved_jobs.append(job_root.name)
                continue
            if not self._expired(state):
                report.preserved_jobs.append(job_root.name)
                continue
            shutil.rmtree(job_root)
            report.deleted_jobs.append(job_root.name)
        return report

    def _expired(self, state: dict) -> bool:
        """判断作业或运行目录是否已经超过保留期限。"""
        finished_at = state.get("finished_at") or state.get("updated_at")
        if not finished_at:
            return False
        finished = datetime.fromisoformat(finished_at)
        age = self.now() - finished
        if state.get("state") == "succeeded":
            return age > timedelta(days=self.policy.success_days)
        if state.get("state") == "failed":
            return age > timedelta(days=self.policy.failed_days)
        return False

    def _legacy_run_state(self, run_root: Path) -> dict | None:
        """读取旧版运行目录状态，供清理策略兼容使用。"""
        if not run_root.name.startswith(LEGACY_RUN_PREFIX):
            return None

        success_path = run_root / "tax_workflow_summary.json"
        failed_path = run_root / "failed.json"
        if success_path.exists():
            return {
                "state": "succeeded",
                "finished_at": _mtime_iso(success_path),
                "callback_delivery_state": "not_configured",
            }
        if failed_path.exists():
            return {
                "state": "failed",
                "finished_at": _mtime_iso(failed_path),
                "callback_delivery_state": "not_configured",
            }
        return None


def _mtime_iso(path: Path) -> str:
    """执行作业、保留清理中的内部辅助逻辑：mtimeiso。"""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
