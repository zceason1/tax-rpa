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
    role: str
    path: str
    error_type: str
    error_code: str
    message: str


@dataclass(frozen=True)
class PreflightResult:
    issues: list[PreflightIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


class PreflightValidator:
    def __init__(
        self,
        base_dir: str | Path,
        *,
        stability_wait_seconds: float = 0.0,
        size_reader: Callable[[Path], int] | None = None,
        sha256_reader: Callable[[Path], str] | None = None,
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.stability_wait_seconds = stability_wait_seconds
        self.size_reader = size_reader or (lambda path: path.stat().st_size)
        self.sha256_reader = sha256_reader or _sha256_file

    def validate(self, manifest: JobManifest) -> PreflightResult:
        issues: list[PreflightIssue] = []
        for role, manifest_file in manifest.files.items():
            path = self._resolve_input_path(manifest_file.path)
            issue = self._validate_one(role, path, manifest_file.sha256)
            if issue is not None:
                issues.append(issue)
        return PreflightResult(issues=issues)

    def _resolve_input_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path.resolve()
        return (self.base_dir / path).resolve()

    def _validate_one(
        self,
        role: str,
        path: Path,
        expected_sha256: str,
    ) -> PreflightIssue | None:
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
    return PreflightIssue(
        role=role,
        path=path.as_posix(),
        error_type=error_type,
        error_code=error_code,
        message=message,
    )


def _incomplete(role: str, path: Path, message: str) -> PreflightIssue:
    return _issue(
        role,
        path,
        "FILE_TRANSFER_INCOMPLETE",
        "file_transfer_incomplete",
        message,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
