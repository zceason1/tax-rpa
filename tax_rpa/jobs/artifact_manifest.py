import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tax_rpa.jobs.artifact_store import JobArtifacts


@dataclass(frozen=True)
class ArtifactManifestWriter:
    """产物清单写入器，负责列出作业产物、校验和和来源步骤。"""
    artifacts: JobArtifacts

    def write(
        self,
        *,
        job_id: str,
        final_status: str,
        callback_status: str,
    ) -> str:
        """写入目标数据或转发输入，具体行为由所在适配器决定。"""
        manifest = {
            "job_id": job_id,
            "created_at": _now(),
            "final_status": final_status,
            "callback_status": callback_status,
            "artifacts": [
                _artifact_entry(self.artifacts, path)
                for path in _iter_artifact_files(self.artifacts.root)
            ],
        }
        return self.artifacts.write_json("artifact_manifest.json", manifest)


def _iter_artifact_files(root: Path) -> list[Path]:
    """执行作业、产物清单中的内部辅助逻辑：iter产物files。"""
    if not root.exists():
        return []
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != "artifact_manifest.json"
        and not path.name.endswith(".tmp")
    ]


def _artifact_entry(artifacts: JobArtifacts, path: Path) -> dict[str, Any]:
    """执行作业、产物清单中的内部辅助逻辑：产物entry。"""
    relative = path.relative_to(artifacts.root).as_posix()
    return {
        "type": _artifact_type(relative),
        "path": relative,
        "sha256": _sha256(path),
        "created_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(
            timespec="seconds"
        ),
        "produced_by_step": _produced_by_step(relative),
        "required": _is_required(relative),
    }


def _artifact_type(relative_path: str) -> str:
    """执行作业、产物清单中的内部辅助逻辑：产物type。"""
    if relative_path.startswith("input/"):
        return "input"
    if relative_path.startswith("exported/"):
        return "exported"
    if relative_path.startswith("screenshots/"):
        return "screenshot"
    if relative_path.startswith("ocr/"):
        return "ocr"
    if relative_path.startswith("logs/"):
        return "log"
    if relative_path == "summary.json":
        return "summary"
    if relative_path == "state.json":
        return "state"
    if relative_path == "troubleshooting_index.json":
        return "troubleshooting_index"
    if relative_path == "callback_outbox.json":
        return "callback_outbox"
    return "artifact"


def _produced_by_step(relative_path: str) -> str:
    """执行作业、产物清单中的内部辅助逻辑：producedby步骤。"""
    if relative_path.startswith("input/"):
        return "job_intake"
    if relative_path == "summary.json":
        return "job_runner.finalize"
    if relative_path == "state.json":
        return "state_store"
    if relative_path == "troubleshooting_index.json":
        return "job_runner.troubleshooting_index"
    if relative_path == "callback_outbox.json":
        return "callback_outbox"
    if relative_path.startswith("logs/callbacks"):
        return "callback_outbox"
    return "unknown"


def _is_required(relative_path: str) -> bool:
    """判断内部条件是否匹配required。"""
    return relative_path in {
        "summary.json",
        "state.json",
        "troubleshooting_index.json",
    } or relative_path.startswith("logs/")


def _sha256(path: Path) -> str:
    """计算文件 SHA256 校验和。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    """生成当前 UTC 时间字符串，供状态和日志落盘使用。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")
