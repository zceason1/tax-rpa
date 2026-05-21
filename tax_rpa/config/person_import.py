import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PersonImportConfigError(ValueError):
    """Raised when the bounded personnel import POC is configured unsafely."""


EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}
FORBIDDEN_ACTION_KEYWORDS = (
    "报送",
    "发送申报",
    "申报",
    "缴款",
    "缴纳",
    "税款缴纳",
)


@dataclass(frozen=True)
class PersonImportConfig:
    person_info_file: Path
    app_path: Path | None = None
    process_name: str = "EPPortalITS.exe"
    dry_run: bool = False
    launch_timeout_seconds: int = 60
    login_timeout_seconds: int = 300
    window_timeout_seconds: int = 90
    import_timeout_seconds: int = 120
    result_timeout_seconds: int = 60
    ocr_score_threshold: float = 0.35
    config_path: Path | None = None


def validate_excel_path(path: str | Path) -> Path:
    excel_path = Path(path).expanduser()
    if not excel_path.exists():
        raise FileNotFoundError(f"Personnel import file does not exist: {excel_path}")
    if not excel_path.is_file():
        raise PersonImportConfigError(f"Excel path is not a file: {excel_path}")
    if excel_path.suffix.lower() not in EXCEL_SUFFIXES:
        raise PersonImportConfigError(
            f"Personnel import file must be an Excel file ({', '.join(sorted(EXCEL_SUFFIXES))}): {excel_path}"
        )
    return excel_path.resolve()


def validate_app_path(path: str | Path) -> Path:
    app_path = Path(path).expanduser()
    if not app_path.exists():
        raise FileNotFoundError(f"Client app path does not exist: {app_path}")
    if not app_path.is_file():
        raise PersonImportConfigError(f"Client app path is not a file: {app_path}")
    if app_path.suffix.lower() not in {".exe", ".lnk"}:
        raise PersonImportConfigError(f"Client app path must be an .exe or .lnk file: {app_path}")
    return app_path.resolve()


def assert_safe_action(label: str) -> None:
    normalized = "".join(str(label).split())
    for keyword in FORBIDDEN_ACTION_KEYWORDS:
        if keyword in normalized:
            raise PersonImportConfigError(
                f"Action is forbidden in the personnel import POC: {label}"
            )


def _read_int(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PersonImportConfigError(f"{key} must be a positive integer")
    return value


def _read_float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise PersonImportConfigError(f"{key} must be a positive number")
    return float(value)


def _read_str(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise PersonImportConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _resolve_config_relative_path(config_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate


def load_import_config(path: str | Path) -> PersonImportConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Import config does not exist: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PersonImportConfigError("Import config must be a JSON object")

    raw_file = data.get("person_info_file")
    if not isinstance(raw_file, str) or not raw_file.strip():
        raise PersonImportConfigError("person_info_file must be a non-empty string")

    dry_run = data.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise PersonImportConfigError("dry_run must be a boolean")

    person_info_file = validate_excel_path(
        _resolve_config_relative_path(config_path, raw_file)
    )
    raw_app_path = data.get("app_path")
    if raw_app_path is None or raw_app_path == "":
        app_path = None
    elif isinstance(raw_app_path, str):
        app_path = validate_app_path(_resolve_config_relative_path(config_path, raw_app_path))
    else:
        raise PersonImportConfigError("app_path must be a string when provided")

    return PersonImportConfig(
        person_info_file=person_info_file,
        app_path=app_path,
        process_name=_read_str(data, "process_name", "EPPortalITS.exe"),
        dry_run=dry_run,
        launch_timeout_seconds=_read_int(data, "launch_timeout_seconds", 60),
        login_timeout_seconds=_read_int(data, "login_timeout_seconds", 300),
        window_timeout_seconds=_read_int(data, "window_timeout_seconds", 90),
        import_timeout_seconds=_read_int(data, "import_timeout_seconds", 120),
        result_timeout_seconds=_read_int(data, "result_timeout_seconds", 60),
        ocr_score_threshold=_read_float(data, "ocr_score_threshold", 0.35),
        config_path=config_path,
    )
