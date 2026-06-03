from pathlib import Path
from typing import Any

from tax_rpa.drivers.mouse_driver import MouseDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.shared.elements.dialogs import OPEN_BUTTON_TEXTS
from tax_rpa.runtime.action_guard import assert_safe_action
from tax_rpa.runtime.action_policy import ActionPolicy
from tax_rpa.runtime.result import StepResult

CANCEL_BUTTON_TEXTS = ("\u53d6\u6d88", "\u5173\u95ed", "Cancel")


class FileDialogComponent:
    """共享文件选择框组件，负责填入 Excel 路径并按执行模式提交或取消。"""
    def __init__(
        self,
        dialog: dict[str, Any],
        logger: Any,
        dry_run: bool,
        mouse: MouseDriver | None = None,
        win32: Win32Driver | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        """初始化文件弹窗component实例，保存依赖、配置和运行上下文。"""
        self.dialog = dialog
        self.logger = logger
        self.dry_run = dry_run
        self.mouse = mouse or MouseDriver()
        self.win32 = win32 or Win32Driver()
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def choose_file(self, path: Path) -> StepResult:
        """在文件选择框中填入文件路径，并根据运行模式提交或取消。"""
        decision = self.action_policy.before_action(
            label="open file",
            action_type="file_submit",
            context={"step_name": "file_dialog.choose_file"},
        )
        if not decision.allowed:
            return decision.to_step_result("file_dialog.choose_file")
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
            result["dry_run_close"] = self._close_dry_run_dialog(dialog_hwnd)
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

    def _close_dry_run_dialog(self, dialog_hwnd: int) -> dict[str, Any]:
        """在 dry-run 模式下关闭文件选择框，避免模态窗口阻塞后续导航。"""
        self.win32.set_foreground(dialog_hwnd)
        children = self.win32.collect_children(dialog_hwnd)
        cancel_button = self.win32.find_button_by_labels(children, CANCEL_BUTTON_TEXTS)
        if cancel_button is not None:
            click_result = self.mouse.click(self.win32.rect_center(cancel_button["rect"]))
            closed = self.win32.wait_for_dialog_closed(dialog_hwnd, 5)
            return {
                "method": "cancel_button",
                "button": cancel_button,
                "click_result": click_result,
                "closed": closed,
            }

        import pyautogui

        pyautogui.press("esc")
        closed = self.win32.wait_for_dialog_closed(dialog_hwnd, 5)
        return {"method": "escape_key", "closed": closed}
