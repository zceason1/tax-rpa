import getpass
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


ValueReader = Callable[[], Any]


@dataclass(frozen=True)
class RuntimeMetadata:
    script_version: str
    git_commit: str
    tax_client_version: str
    ocr_engine_version: str
    windows_user: str
    resolution: dict[str, int | None]
    dpi: int | None

    @classmethod
    def collect(
        cls,
        *,
        script_version_reader: ValueReader | None = None,
        git_commit_reader: ValueReader | None = None,
        tax_client_version_reader: ValueReader | None = None,
        ocr_engine_version_reader: ValueReader | None = None,
        screen_reader: ValueReader | None = None,
        windows_user_reader: ValueReader | None = None,
    ) -> "RuntimeMetadata":
        screen = _safe_dict(screen_reader or _read_screen)
        return cls(
            script_version=_safe_text(script_version_reader or _read_script_version),
            git_commit=_safe_text(git_commit_reader or _read_git_commit),
            tax_client_version=_safe_text(tax_client_version_reader or _unknown),
            ocr_engine_version=_safe_text(ocr_engine_version_reader or _unknown),
            windows_user=_safe_text(windows_user_reader or getpass.getuser),
            resolution={
                "width": _safe_int(screen.get("width")),
                "height": _safe_int(screen.get("height")),
            },
            dpi=_safe_int(screen.get("dpi")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_text(reader: ValueReader) -> str:
    try:
        value = reader()
    except Exception:
        return "unknown"
    if value is None:
        return "unknown"
    text = str(value).strip()
    return text or "unknown"


def _safe_dict(reader: ValueReader) -> dict[str, Any]:
    try:
        value = reader()
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_script_version() -> str:
    try:
        import tax_rpa

        return str(getattr(tax_rpa, "__version__", "unknown"))
    except Exception:
        return "unknown"


def _read_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _read_screen() -> dict[str, int | None]:
    return {"width": None, "height": None, "dpi": None}


def _unknown() -> str:
    return "unknown"
