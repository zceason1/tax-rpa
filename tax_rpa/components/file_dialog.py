from pathlib import Path
from typing import Any

from tax_rpa.constants import OPEN_BUTTON_TEXTS
from tax_rpa.config.person_import import assert_safe_action
from tax_rpa.drivers.mouse_driver import MouseDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.result import StepResult


class FileDialogComponent:
    def __init__(
        self,
        dialog: dict[str, Any],
        logger: Any,
        dry_run: bool,
        mouse: MouseDriver | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.dialog = dialog
        self.logger = logger
        self.dry_run = dry_run
        self.mouse = mouse or MouseDriver()
        self.win32 = win32 or Win32Driver()

    def choose_file(self, path: Path) -> StepResult:
        assert_safe_action("打开")
        dialog_hwnd = self.dialog["hwnd"]
        self.logger.screenshot("file_dialog", self.dialog["rect"])
        edit = self.win32.find_largest_edit_control(dialog_hwnd)
        open_button = self.win32.find_button_by_labels(
            self.win32.collect_children(dialog_hwnd),
            OPEN_BUTTON_TEXTS,
        )
        result = {
            "dialog": self.dialog,
            "edit": edit,
            "open_button": open_button,
            "file_path": str(path),
            "dry_run": self.dry_run,
        }
        self.logger.log("fill_file_dialog", "dry_run" if self.dry_run else "start", **result)
        if self.dry_run:
            return StepResult(
                ok=True,
                name="file_dialog.choose_file",
                status="dry_run",
                evidence={"result": result},
            )

        self.win32.set_foreground(dialog_hwnd)
        if edit is not None:
            self.win32.set_window_text(edit["hwnd"], str(path))
        else:
            import pyautogui

            pyautogui.hotkey("alt", "n")
            pyautogui.write(str(path), interval=0)

        open_button = self.win32.find_button_by_labels(
            self.win32.collect_children(dialog_hwnd),
            OPEN_BUTTON_TEXTS,
        )
        if open_button is not None:
            result["open_button"] = open_button
            result["submit_method"] = "button_click"
            result["button_click"] = self.mouse.click(self.win32.rect_center(open_button["rect"]))
        else:
            import pyautogui

            result["submit_method"] = "enter_key"
            pyautogui.press("enter")
        self.logger.log("fill_file_dialog", "submitted", **result)
        if not self.dry_run:
            self.win32.wait_for_dialog_closed(self.dialog["hwnd"], 30)
        return StepResult(
            ok=True,
            name="file_dialog.choose_file",
            status=result.get("submit_method", "submitted"),
            evidence={"result": result},
        )
