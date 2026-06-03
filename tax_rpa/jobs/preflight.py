import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tax_rpa.jobs.manifest import JobManifest


EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}
TEMP_SUFFIXES = {".tmp", ".part", ".download", ".crdownload"}


@dataclass(frozen=True)
class PreflightIssue:
    """预检问题，封装作业、预检相关状态和行为。"""
    role: str
    path: str
    error_type: str
    error_code: str
    message: str


@dataclass(frozen=True)
class PreflightResult:
    """预检结果结果对象，承载执行状态、证据和后续判断所需字段。"""
    issues: list[PreflightIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """判断当前结果是否满足成功条件。"""
        return not self.issues


class PreflightValidator:
    """作业预检器，负责校验输入文件存在性、完整性和校验和。"""
    def __init__(
        self,
        base_dir: str | Path,
        *,
        stability_wait_seconds: float = 0.0,
        size_reader: Callable[[Path], int] | None = None,
        sha256_reader: Callable[[Path], str] | None = None,
    ) -> None:
        """初始化预检validator实例，保存依赖、配置和运行上下文。"""
        self.base_dir = Path(base_dir).resolve()
        self.stability_wait_seconds = stability_wait_seconds
        self.size_reader = size_reader or (lambda path: path.stat().st_size)
        self.sha256_reader = sha256_reader or _sha256_file

    def validate(self, manifest: JobManifest) -> PreflightResult:
        """校验输入对象是否满足当前模块的规则。"""
        issues: list[PreflightIssue] = []
        for role, manifest_file in manifest.files.items():
            path = self._resolve_input_path(manifest_file.path)
            issue = self._validate_one(role, path, manifest_file.sha256)
            if issue is not None:
                issues.append(issue)
        return PreflightResult(issues=issues)

    def _resolve_input_path(self, path: Path) -> Path:
        """把清单中的输入路径解析到实际文件路径。"""
        if path.is_absolute():
            return path.resolve()
        return (self.base_dir / path).resolve()

    def _validate_one(
        self,
        role: str,
        path: Path,
        expected_sha256: str,
    ) -> PreflightIssue | None:
        """校验单个输入文件并生成预检问题。"""
        if not path.is_relative_to(self.base_dir):
            return _issue(
                role,
                path,
                "MATERIAL_INVALID",
                "input_file_path_outside_base",
                "Input file path escapes the job base directory",
            )
        if path.suffix.lower() in TEMP_SUFFIXES:
            return _incomplete(role, path, "Input file still has a temporary transfer suffix")
        if not path.exists() or not path.is_file():
            return _issue(role, path, "MATERIAL_INVALID", "input_file_missing", "Input file is missing")
        if path.suffix.lower() not in EXCEL_SUFFIXES:
            return _issue(
                role,
                path,
                "MATERIAL_INVALID",
                "input_file_invalid_suffix",
                "Input file must be an Excel file",
            )

        size_1 = self.size_reader(path)
        if self.stability_wait_seconds > 0:
            time.sleep(self.stability_wait_seconds)
        size_2 = self.size_reader(path)
        if size_1 != size_2:
            return _incomplete(role, path, "Input file size changed during preflight")

        sha_1 = self.sha256_reader(path)
        sha_2 = self.sha256_reader(path)
        if sha_1 != sha_2:
            return _incomplete(role, path, "Input file checksum changed during preflight")
        if sha_1.lower() != expected_sha256.lower():
            return _issue(
                role,
                path,
                "MATERIAL_INVALID",
                "input_file_checksum_mismatch",
                "Input file checksum does not match manifest",
            )
        return None


def _issue(
    role: str,
    path: Path,
    error_type: str,
    error_code: str,
    message: str,
) -> PreflightIssue:
    """执行作业、预检中的内部辅助逻辑：问题。"""
    return PreflightIssue(
        role=role,
        path=path.as_posix(),
        error_type=error_type,
        error_code=error_code,
        message=message,
    )


def _incomplete(role: str, path: Path, message: str) -> PreflightIssue:
    """执行作业、预检中的内部辅助逻辑：incomplete。"""
    return _issue(
        role,
        path,
        "FILE_TRANSFER_INCOMPLETE",
        "file_transfer_incomplete",
        message,
    )


def _sha256_file(path: Path) -> str:
    """计算输入文件 SHA256 校验和。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
