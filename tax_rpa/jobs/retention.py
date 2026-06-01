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
    success_days: int = 30
    failed_days: int = 90


@dataclass
class RetentionReport:
    deleted_jobs: list[str] = field(default_factory=list)
    preserved_jobs: list[str] = field(default_factory=list)
    skipped_jobs: list[str] = field(default_factory=list)


class RetentionCleaner:
    def __init__(
        self,
        artifacts_root: str | Path,
        *,
        policy: RetentionPolicy | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.artifacts_root = Path(artifacts_root)
        self.policy = policy or RetentionPolicy()
        self.now = now or (lambda: datetime.now().astimezone())

    def cleanup(self) -> RetentionReport:
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
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
