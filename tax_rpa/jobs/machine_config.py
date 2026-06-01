import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tax_rpa.jobs.preflight import PreflightIssue
from tax_rpa.jobs.redaction import redact_sensitive


class MachineConfigValidationError(ValueError):
    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_type = "SYSTEM_ENVIRONMENT_ERROR"
        self.error_code = error_code


@dataclass(frozen=True)
class MachineConfig:
    path: Path
    data: dict[str, Any]

    @property
    def schema_version(self) -> int:
        return int(self.data["schema_version"])

    @property
    def ocr_engine(self) -> str:
        return str(self.data["ocr"]["engine"])

    def to_summary_dict(self) -> dict[str, Any]:
        return redact_sensitive(self.data)


@dataclass(frozen=True)
class MachineConfigValidationResult:
    issues: list[PreflightIssue]
    config: MachineConfig | None = None

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class MachineConfigValidator:
    path: Path = Path("config/machine_config.json")

    def validate(self) -> MachineConfigValidationResult:
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
    value = data.get(key)
    if not isinstance(value, dict):
        raise MachineConfigValidationError(
            f"machine_config.{key} must be an object",
            f"machine_config_invalid_{key}",
        )
    return value


def _require_equal(data: dict[str, Any], key: str, expected: Any) -> None:
    if data.get(key) != expected:
        raise MachineConfigValidationError(
            f"machine_config.{key} must be {expected!r}",
            f"machine_config_invalid_{key}",
        )


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MachineConfigValidationError(
            f"machine_config field {key} must be a non-empty string",
            f"machine_config_invalid_{key}",
        )
    return value.strip()


def _require_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, (int, float)):
        raise MachineConfigValidationError(
            f"machine_config field {key} must be numeric",
            f"machine_config_invalid_{key}",
        )
    return float(value)


def _require_positive_number(data: dict[str, Any], key: str) -> float:
    value = _require_number(data, key)
    if value <= 0:
        raise MachineConfigValidationError(
            f"machine_config field {key} must be positive",
            f"machine_config_invalid_{key}",
        )
    return value
