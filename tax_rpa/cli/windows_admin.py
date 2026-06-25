import ctypes
import subprocess
import sys
from pathlib import Path


def _shell32():
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Windows shell32 APIs are unavailable on this platform")
    return ctypes.windll.shell32


def is_user_admin() -> bool:
    """Return whether the current Windows process is elevated."""
    try:
        return bool(_shell32().IsUserAnAdmin())
    except Exception:
        return False


def relaunch_module_as_admin(module_name: str, argv: list[str]) -> None:
    """Relaunch a Python module through the Windows UAC prompt."""
    params = subprocess.list2cmdline(["-m", module_name, *argv])
    result = _shell32().ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        str(Path.cwd()),
        1,
    )
    if result <= 32:
        raise RuntimeError(f"Failed to relaunch as administrator. ShellExecuteW={result}")
