import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PersonImportConfigError(ValueError):
    """人员导入配置错误异常，表示配置、人员导入中的特定错误场景。"""


EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}


@dataclass(frozen=True)
class ImportFileConfig:
    """导入文件配置配置对象，承载运行当前流程所需的配置项。"""
    file: Path


@dataclass(frozen=True)
class LoginConfig:
    """登录配置配置对象，承载运行当前流程所需的配置项。"""
    method: str = "申报密码登录"
    declaration_password: str | None = None


@dataclass(frozen=True)
class PersonImportConfig:
    """人员导入配置配置对象，承载运行当前流程所需的配置项。"""
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
    imports: dict[str, ImportFileConfig] = field(default_factory=dict)
    login: LoginConfig = field(default_factory=LoginConfig)

    def import_file(self, location: str) -> Path:
        """按业务位置读取对应的导入文件路径。"""
        if location in self.imports:
            return validate_excel_path(self.imports[location].file)
        if location == "person_info":
            return validate_excel_path(self.person_info_file)
        raise PersonImportConfigError(f"Unknown import location: {location}")


def validate_excel_path(path: str | Path) -> Path:
    """校验路径存在且是 Excel 文件，返回规范化路径。"""
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
    """校验客户端启动路径存在，返回规范化路径。"""
    app_path = Path(path).expanduser()
    if not app_path.exists():
        raise FileNotFoundError(f"Client app path does not exist: {app_path}")
    if not app_path.is_file():
        raise PersonImportConfigError(f"Client app path is not a file: {app_path}")
    if app_path.suffix.lower() not in {".exe", ".lnk"}:
        raise PersonImportConfigError(f"Client app path must be an .exe or .lnk file: {app_path}")
    return app_path.resolve()


def _read_int(data: dict[str, Any], key: str, default: int) -> int:
    """从配置字典读取整数值，并在缺失时使用默认值。"""
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PersonImportConfigError(f"{key} must be a positive integer")
    return value


def _read_float(data: dict[str, Any], key: str, default: float) -> float:
    """从配置字典读取浮点值，并在缺失时使用默认值。"""
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise PersonImportConfigError(f"{key} must be a positive number")
    return float(value)


def _read_str(data: dict[str, Any], key: str, default: str) -> str:
    """从配置字典读取字符串值，并在缺失时使用默认值。"""
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise PersonImportConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _resolve_config_relative_path(config_path: Path, raw_path: str) -> Path:
    """把配置文件中的相对路径解析为绝对路径。"""
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate


def _read_imports(
    data: dict[str, Any],
    config_path: Path,
    person_info_file: Path,
) -> dict[str, ImportFileConfig]:
    """读取命名导入文件配置，并校验必要导入文件。"""
    raw_imports = data.get("imports", {})
    if raw_imports is None:
        raw_imports = {}
    if not isinstance(raw_imports, dict):
        raise PersonImportConfigError("imports must be a JSON object")

    imports: dict[str, ImportFileConfig] = {
        "person_info": ImportFileConfig(file=person_info_file),
    }
    for location, raw_config in raw_imports.items():
        if not isinstance(location, str) or not location.strip():
            raise PersonImportConfigError("import location keys must be non-empty strings")
        if not isinstance(raw_config, dict):
            raise PersonImportConfigError(f"imports.{location} must be a JSON object")
        raw_file = raw_config.get("file")
        if not isinstance(raw_file, str) or not raw_file.strip():
            raise PersonImportConfigError(
                f"imports.{location}.file must be a non-empty string"
            )
        imports[location.strip()] = ImportFileConfig(
            file=_resolve_config_relative_path(config_path, raw_file).resolve()
        )
    return imports


def _read_login(data: dict[str, Any]) -> LoginConfig:
    """读取登录配置，并规范化登录方式、密码和超时时间。"""
    raw_login = data.get("login", {})
    if raw_login is None:
        raw_login = {}
    if not isinstance(raw_login, dict):
        raise PersonImportConfigError("login must be a JSON object")

    raw_method = raw_login.get("method", "申报密码登录")
    if not isinstance(raw_method, str) or not raw_method.strip():
        raise PersonImportConfigError("login.method must be a non-empty string")

    raw_password = raw_login.get("declaration_password")
    if raw_password is None or raw_password == "":
        password = None
    elif isinstance(raw_password, str):
        password = raw_password
    else:
        raise PersonImportConfigError("login.declaration_password must be a string")

    return LoginConfig(
        method=raw_method.strip(),
        declaration_password=password,
    )


def load_import_config(path: str | Path) -> PersonImportConfig:
    """读取人员导入配置文件，并转换成运行时配置对象。"""
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
    imports = _read_imports(data, config_path, person_info_file)
    login = _read_login(data)
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
        imports=imports,
        login=login,
    )
