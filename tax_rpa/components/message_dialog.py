from typing import Any

from tax_rpa.constants import FILE_DIALOG_TITLE_HINTS
from tax_rpa.drivers.mouse_driver import MouseDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.jobs.action_policy import ActionPolicy
from tax_rpa.runtime.result import StepResult

CONFIRM_BUTTON_TEXTS = ("确定", "确认", "是", "OK", "Yes")
CANCEL_BUTTON_TEXTS = ("取消", "否", "关闭", "Cancel", "No")
DialogAction = str


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
    action: DialogAction = "escape",
    mouse: MouseDriver | None = None,
    win32: Win32Driver | None = None,
) -> list[dict[str, Any]]:
    import time

    driver = win32 or Win32Driver()
    mouse_driver = mouse or MouseDriver()
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
        if action == "confirm":
            button = driver.find_button_by_labels(
                driver.collect_children(dialog["hwnd"]),
                CONFIRM_BUTTON_TEXTS,
            )
            if button is not None:
                mouse_driver.click(driver.rect_center(button["rect"]))
            else:
                pyautogui.press("enter")
        elif action == "cancel":
            button = driver.find_button_by_labels(
                driver.collect_children(dialog["hwnd"]),
                CANCEL_BUTTON_TEXTS,
            )
            if button is not None:
                mouse_driver.click(driver.rect_center(button["rect"]))
            else:
                pyautogui.press("esc")
        elif action == "escape":
            pyautogui.press("esc")
        else:
            raise ValueError(f"Unsupported dialog action: {action}")
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
        mouse: MouseDriver | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        self.allowed_pids = allowed_pids
        self.logger = logger
        self.dry_run = dry_run
        self.win32 = win32 or Win32Driver()
        self.mouse = mouse
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def close_if_present(self) -> StepResult:
        return self.close_with_action("escape")

    def close_with_action(self, action: DialogAction) -> StepResult:
        action_type = "dialog_confirm" if action == "confirm" else "read_only_click"
        decision = self.action_policy.before_action(
            label=f"dialog_{action}",
            action_type=action_type,
            context={"step_name": "message_dialog.close_if_present"},
        )
        if not decision.allowed:
            return decision.to_step_result("message_dialog.close_if_present")
        effective_dry_run = self.dry_run and action != "cancel"
        closed = close_blocking_dialogs(
            self.allowed_pids,
            self.logger,
            effective_dry_run,
            action=action,
            mouse=self.mouse,
            win32=self.win32,
        )
        return StepResult(
            ok=True,
            name="message_dialog.close_if_present",
            status="closed" if closed else "none",
            evidence={"closed_dialogs": closed},
        )
