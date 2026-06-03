import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tax_rpa.jobs.preflight import PreflightIssue
from tax_rpa.jobs.redaction import redact_sensitive


class MachineConfigValidationError(ValueError):
    """机器配置validation错误异常，表示作业、机器配置中的特定错误场景。"""
    def __init__(self, message: str, error_code: str) -> None:
        """初始化机器配置validation错误实例，保存依赖、配置和运行上下文。"""
        super().__init__(message)
        self.error_type = "SYSTEM_ENVIRONMENT_ERROR"
        self.error_code = error_code


@dataclass(frozen=True)
class MachineConfig:
    """机器配置对象，描述真实客户端运行所需的本机环境。"""
    path: Path
    data: dict[str, Any]

    @property
    def schema_version(self) -> int:
        """执行作业、机器配置中的schema版本逻辑，供业务流程或相邻模块调用。"""
        return int(self.data["schema_version"])

    @property
    def ocr_engine(self) -> str:
        """执行作业、机器配置中的OCR识别engine逻辑，供业务流程或相邻模块调用。"""
        return str(self.data["ocr"]["engine"])

    def to_summary_dict(self) -> dict[str, Any]:
        """执行作业、机器配置中的to摘要dict逻辑，供业务流程或相邻模块调用。"""
        return redact_sensitive(self.data)


@dataclass(frozen=True)
class MachineConfigValidationResult:
    """机器配置validation结果结果对象，承载执行状态、证据和后续判断所需字段。"""
    issues: list[PreflightIssue]
    config: MachineConfig | None = None

    @property
    def ok(self) -> bool:
        """判断当前结果是否满足成功条件。"""
        return not self.issues


@dataclass(frozen=True)
class MachineConfigValidator:
    """机器配置validator，封装作业、机器配置相关状态和行为。"""
    path: Path = Path("config/machine_config.json")

    def validate(self) -> MachineConfigValidationResult:
        """校验输入对象是否满足当前模块的规则。"""
        try:
            return MachineConfigValidationResult(
                issues=[],
                config=load_machine_config(self.path),
            )
        except MachineConfigValidationError as exc:
            return MachineConfigValidationResult(
                issues=[
                    PreflightIssue(
                        role="machine_config",
                        path=self.path.as_posix(),
                        error_type=exc.error_type,
                        error_code=exc.error_code,
                        message=str(exc),
                    )
                ]
            )


def load_machine_config(path: str | Path) -> MachineConfig:
    """加载机器配置，并转换为当前模块使用的数据对象。"""
    config_path = Path(path)
    if not config_path.exists():
        raise MachineConfigValidationError(
            "machine_config.json is missing",
            "machine_config_missing",
        )
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MachineConfigValidationError(
            f"machine_config.json is unreadable: {exc}",
            "machine_config_unreadable",
        ) from exc

    if not isinstance(data, dict):
        raise MachineConfigValidationError(
            "machine_config.json must be a JSON object",
            "machine_config_not_object",
        )
    _require_equal(data, "schema_version", 1)
    _require_section(data, "app")
    _require_section(data, "screen")
    _require_section(data, "ocr")
    _require_section(data, "artifacts")
    _require_section(data, "callback")
    _require_section(data, "submit")

    app_path = _require_str(data["app"], "app_path")
    if not Path(app_path).exists():
        raise MachineConfigValidationError(
            "Configured tax client app_path does not exist",
            "missing_app_path",
        )
    _require_str(data["app"], "process_name")
    _require_positive_number(data["app"], "launch_timeout_seconds")
    _require_positive_number(data["app"], "login_timeout_seconds")
    _require_positive_number(data["app"], "window_timeout_seconds")

    _require_positive_number(data["screen"], "required_width")
    _require_positive_number(data["screen"], "required_height")
    _require_positive_number(data["screen"], "required_dpi")

    _require_str(data["ocr"], "engine")
    _require_number(data["ocr"], "default_score_threshold")

    _require_str(data["artifacts"], "root")
    _require_positive_number(data["artifacts"], "min_free_gb")
    _require_positive_number(data["artifacts"], "retention_success_days")
    _require_positive_number(data["artifacts"], "retention_failed_days")

    _require_positive_number(data["callback"], "timeout_seconds")
    _require_positive_number(data["callback"], "retry_window_hours")
    _require_str(data["callback"], "secret_credential_name")

    _require_str(data["submit"], "production_switch_path")
    return MachineConfig(path=config_path, data=data)


def _require_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    """执行作业、机器配置中的内部辅助逻辑：requiresection。"""
    value = data.get(key)
    if not isinstance(value, dict):
        raise MachineConfigValidationError(
            f"machine_config.{key} must be an object",
            f"machine_config_invalid_{key}",
        )
    return value


def _require_equal(data: dict[str, Any], key: str, expected: Any) -> None:
    """执行作业、机器配置中的内部辅助逻辑：requireequal。"""
    if data.get(key) != expected:
        raise MachineConfigValidationError(
            f"machine_config.{key} must be {expected!r}",
            f"machine_config_invalid_{key}",
        )


def _require_str(data: dict[str, Any], key: str) -> str:
    """执行作业、机器配置中的内部辅助逻辑：requirestr。"""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MachineConfigValidationError(
            f"machine_config field {key} must be a non-empty string",
            f"machine_config_invalid_{key}",
        )
    return value.strip()


def _require_number(data: dict[str, Any], key: str) -> float:
    """执行作业、机器配置中的内部辅助逻辑：requirenumber。"""
    value = data.get(key)
    if not isinstance(value, (int, float)):
        raise MachineConfigValidationError(
            f"machine_config field {key} must be numeric",
            f"machine_config_invalid_{key}",
        )
    return float(value)


def _require_positive_number(data: dict[str, Any], key: str) -> float:
    """执行作业、机器配置中的内部辅助逻辑：requirepositivenumber。"""
    value = _require_number(data, key)
    if value <= 0:
        raise MachineConfigValidationError(
            f"machine_config field {key} must be positive",
            f"machine_config_invalid_{key}",
        )
    return value
