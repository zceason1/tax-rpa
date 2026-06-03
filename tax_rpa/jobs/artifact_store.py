import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactPathError(ValueError):
    """产物路径错误异常，表示作业、产物存储中的特定错误场景。"""
    pass


@dataclass(frozen=True)
class ArtifactStore:
    """作业产物根目录管理器，负责为作业创建产物访问对象。"""
    root: Path = Path("artifacts/jobs")

    def for_job(self, job_id: str) -> "JobArtifacts":
        """为指定作业创建产物目录访问对象。"""
        if not job_id or any(separator in job_id for separator in ("/", "\\")):
            raise ArtifactPathError(f"Invalid job_id for artifact path: {job_id}")
        return JobArtifacts(root=self.root / job_id)


@dataclass(frozen=True)
class JobArtifacts:
    """单个作业的产物目录对象，负责规范化日志、截图和导出文件路径。"""
    root: Path

    @property
    def logs_dir(self) -> Path:
        """执行作业、产物存储中的logsdir逻辑，供业务流程或相邻模块调用。"""
        return self.root / "logs"

    @property
    def screenshots_dir(self) -> Path:
        """执行作业、产物存储中的screenshotsdir逻辑，供业务流程或相邻模块调用。"""
        return self.root / "screenshots"

    @property
    def ocr_dir(self) -> Path:
        """执行作业、产物存储中的OCR识别dir逻辑，供业务流程或相邻模块调用。"""
        return self.root / "ocr"

    @property
    def exported_dir(self) -> Path:
        """执行作业、产物存储中的exporteddir逻辑，供业务流程或相邻模块调用。"""
        return self.root / "exported"

    @property
    def input_dir(self) -> Path:
        """执行作业、产物存储中的输入dir逻辑，供业务流程或相邻模块调用。"""
        return self.root / "input"

    def initialize(self) -> None:
        """初始化作业相关目录或状态文件。"""
        for directory in (
            self.root,
            self.logs_dir,
            self.screenshots_dir,
            self.ocr_dir,
            self.exported_dir,
            self.input_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str | Path, data: Any) -> str:
        """把数据写入作业产物目录下的 JSON 文件。"""
        target = self._resolve_job_relative_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_name(f"{target.name}.tmp")
        temp_path.write_text(
            json.dumps(_to_jsonable(data), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(target)
        return target.relative_to(self.root).as_posix()

    def _resolve_job_relative_path(self, relative_path: str | Path) -> Path:
        """解析作业内相对路径，并阻止写出作业目录。"""
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ArtifactPathError(f"Artifact path must be relative: {relative_path}")
        target = (self.root / candidate).resolve()
        root = self.root.resolve()
        if not target.is_relative_to(root):
            raise ArtifactPathError(f"Artifact path escapes job directory: {relative_path}")
        return target


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
