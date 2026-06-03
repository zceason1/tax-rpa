import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


KNOWN_FIELDS = {
    "job_id",
    "idempotency_key",
    "company_name",
    "credit_code",
    "tax_period",
    "person_action",
    "person_type",
    "run_mode",
    "submit_enabled",
    "allow_skip_personal_pension",
    "callback_url",
    "files",
}
REQUIRED_FIELDS = {
    "job_id",
    "idempotency_key",
    "company_name",
    "credit_code",
    "tax_period",
    "person_action",
    "run_mode",
    "submit_enabled",
    "files",
}
REQUIRED_FILE_ROLES = ("person_info", "salary_income")
RUN_MODES = {"inspect_only", "execute_no_send", "submit"}
PERSON_ACTIONS = {"import_file", "add_person"}
PERSON_TYPES = {"domestic", "foreign"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ManifestValidationError(ValueError):
    """清单validation错误异常，表示作业、清单中的特定错误场景。"""
    def __init__(self, message: str, error_type: str, error_code: str) -> None:
        """初始化清单validation错误实例，保存依赖、配置和运行上下文。"""
        super().__init__(message)
        self.error_type = error_type
        self.error_code = error_code


@dataclass(frozen=True)
class ManifestFile:
    """清单文件，封装作业、清单相关状态和行为。"""
    path: Path
    sha256: str


@dataclass(frozen=True)
class JobManifest:
    """作业清单，封装作业、清单相关状态和行为。"""
    job_id: str
    idempotency_key: str
    company_name: str
    credit_code: str
    tax_period: str
    person_action: str
    run_mode: str
    submit_enabled: bool
    files: dict[str, ManifestFile]
    person_type: str | None = None
    allow_skip_personal_pension: bool = False
    callback_url: str | None = None
    manifest_extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobManifest":
        """执行作业、清单中的从零启动dict逻辑，供业务流程或相邻模块调用。"""
        if not isinstance(data, dict):
            raise _invalid("Manifest must be a JSON object", "manifest_not_object")

        for field_name in sorted(REQUIRED_FIELDS):
            if field_name not in data:
                raise _invalid(
                    f"Missing required manifest field: {field_name}",
                    "manifest_missing_required_field",
                )

        person_action = _read_str(data, "person_action")
        if person_action not in PERSON_ACTIONS:
            raise _invalid("Invalid person_action", "manifest_invalid_person_action")
        if person_action == "add_person":
            raise ManifestValidationError(
                "person_action=add_person is reserved but unsupported in phase 1",
                "UNSUPPORTED_ACTION",
                "person_action_add_person_unsupported",
            )

        run_mode = _read_str(data, "run_mode")
        if run_mode not in RUN_MODES:
            raise _invalid("Invalid run_mode", "manifest_invalid_run_mode")

        person_type = data.get("person_type")
        if person_type is not None:
            if not isinstance(person_type, str) or person_type.strip() not in PERSON_TYPES:
                raise _invalid("Invalid person_type", "manifest_invalid_person_type")
            person_type = person_type.strip()

        allow_skip = data.get("allow_skip_personal_pension", False)
        if not isinstance(allow_skip, bool):
            raise _invalid(
                "allow_skip_personal_pension must be a boolean",
                "manifest_invalid_allow_skip_personal_pension",
            )

        callback_url = data.get("callback_url")
        if callback_url is not None:
            if not isinstance(callback_url, str) or not callback_url.strip():
                raise _invalid("callback_url must be a non-empty string", "manifest_invalid_callback_url")
            callback_url = callback_url.strip()

        return cls(
            job_id=_read_str(data, "job_id"),
            idempotency_key=_read_str(data, "idempotency_key"),
            company_name=_read_str(data, "company_name"),
            credit_code=_read_credit_code(data["credit_code"]),
            tax_period=_normalize_tax_period(_read_str(data, "tax_period")),
            person_action=person_action,
            person_type=person_type,
            run_mode=run_mode,
            submit_enabled=_read_bool(data, "submit_enabled"),
            allow_skip_personal_pension=allow_skip,
            callback_url=callback_url,
            files=_read_files(data["files"]),
            manifest_extra={
                key: value for key, value in data.items() if key not in KNOWN_FIELDS
            },
        )


def load_job_manifest(path: str | Path) -> JobManifest:
    """加载作业清单，并转换为当前模块使用的数据对象。"""
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return JobManifest.from_dict(data)


def _invalid(message: str, error_code: str) -> ManifestValidationError:
    """执行作业、清单中的内部辅助逻辑：invalid。"""
    return ManifestValidationError(message, "MATERIAL_INVALID", error_code)


def _read_str(data: dict[str, Any], key: str) -> str:
    """从配置字典读取字符串值，并在缺失时使用默认值。"""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{key} must be a non-empty string", f"manifest_invalid_{key}")
    return value.strip()


def _read_bool(data: dict[str, Any], key: str) -> bool:
    """读取bool，并处理缺失或异常情况。"""
    value = data.get(key)
    if not isinstance(value, bool):
        raise _invalid(f"{key} must be a boolean", f"manifest_invalid_{key}")
    return value


def _read_credit_code(value: Any) -> str:
    """读取creditcode，并处理缺失或异常情况。"""
    if not isinstance(value, str) or len(value.strip()) != 18:
        raise _invalid("credit_code must be an 18-character string", "manifest_invalid_credit_code")
    return value.strip()


def _normalize_tax_period(value: str) -> str:
    """执行作业、清单中的内部辅助逻辑：normalize税务period。"""
    if re.fullmatch(r"\d{6}", value):
        return f"{value[:4]}-{value[4:]}"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return value
    raise _invalid("tax_period must be YYYY-MM or YYYYMM", "manifest_invalid_tax_period")


def _read_files(value: Any) -> dict[str, ManifestFile]:
    """读取files，并处理缺失或异常情况。"""
    if not isinstance(value, dict):
        raise _invalid("files must be a JSON object", "manifest_invalid_files")

    files: dict[str, ManifestFile] = {}
    for role in REQUIRED_FILE_ROLES:
        if role not in value:
            raise _invalid(f"Missing file role: {role}", "manifest_missing_file_role")
        raw_file = value[role]
        if not isinstance(raw_file, dict):
            raise _invalid(f"files.{role} must be a JSON object", "manifest_invalid_file_entry")
        raw_path = raw_file.get("path")
        raw_sha256 = raw_file.get("sha256")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise _invalid(f"files.{role}.path must be a non-empty string", "manifest_invalid_file_path")
        if not isinstance(raw_sha256, str) or not SHA256_RE.fullmatch(raw_sha256):
            raise _invalid(f"files.{role}.sha256 must be a SHA-256 hex digest", "manifest_invalid_file_sha256")
        files[role] = ManifestFile(path=Path(raw_path.strip()), sha256=raw_sha256.lower())
    return files
