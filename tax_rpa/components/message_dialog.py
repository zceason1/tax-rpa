from typing import Any

from tax_rpa.constants import FILE_DIALOG_TITLE_HINTS
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.result import StepResult


def is_blocking_dialog(window: dict[str, Any]) -> bool:
    class_name = str(window.get("class", ""))
    title = str(window.get("title", ""))
    area = int(window.get("area", 0) or 0)
    if area <= 1000:
        return False
    if class_name == "Tfrm_MsgDlgRich":
        return True
    if class_name == "#32770" and any(hint in title for hint in FILE_DIALOG_TITLE_HINTS):
        return False
    return class_name in {"TMessageForm", "Tfrm_MessageDlg"}


def collect_blocking_dialogs(
    allowed_pids: set[int],
    win32: Win32Driver | None = None,
) -> list[dict[str, Any]]:
    driver = win32 or Win32Driver()
    dialogs = []
    for window in driver.collect_top_windows():
        if window["pid"] not in allowed_pids:
            continue
        if is_blocking_dialog(window):
            dialogs.append({**window, "texts": driver.collect_window_texts(window["hwnd"])})
    return dialogs


def close_blocking_dialogs(
    allowed_pids: set[int],
    logger: Any,
    dry_run: bool,
    timeout_seconds: int = 5,
    win32: Win32Driver | None = None,
) -> list[dict[str, Any]]:
    import time

    driver = win32 or Win32Driver()
    closed = []
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        dialogs = collect_blocking_dialogs(allowed_pids, driver)
        if not dialogs:
            return closed
        dialog = sorted(dialogs, key=lambda item: item["area"], reverse=True)[0]
        logger.log("blocking_dialog", "found", dialog=dialog, dry_run=dry_run)
        if dry_run:
            return closed

        import pyautogui

        driver.set_foreground(dialog["hwnd"])
        pyautogui.press("esc")
        closed.append(dialog)
        time.sleep(0.8)
    return closed


class MessageDialogComponent:
    def __init__(
        self,
        allowed_pids: set[int],
        logger: Any,
        dry_run: bool,
        win32: Win32Driver | None = None,
    ) -> None:
        self.allowed_pids = allowed_pids
        self.logger = logger
        self.dry_run = dry_run
        self.win32 = win32 or Win32Driver()

    def close_if_present(self) -> StepResult:
        closed = close_blocking_dialogs(
            self.allowed_pids,
            self.logger,
            self.dry_run,
            win32=self.win32,
        )
        return StepResult(
            ok=True,
            name="message_dialog.close_if_present",
            status="closed" if closed else "none",
            evidence={"closed_dialogs": closed},
        )
