from typing import Any

from tax_rpa.pages.shared.components.message_dialog import MessageDialogComponent
from tax_rpa.runtime.result import StepResult


class PageDialogMixin:
    """页面弹窗混入能力，为页面统一提供阻塞弹窗关闭动作。"""
    context: Any
    hwnd: int
    win32: Any
    message_dialog: Any | None

    def close_message_dialog_if_present(self, action: str = "cancel") -> StepResult:
        """关闭当前页面可能出现的消息弹窗，保证后续操作不被阻塞。"""
        if self.message_dialog is not None:
            closer = getattr(self.message_dialog, "close_with_action", None)
            if callable(closer):
                return closer(action)
            return self.message_dialog.close_if_present()

        if self.context is not None and self.context.main_window is not None:
            allowed_pids = {int(self.context.main_window["pid"])}
            result = MessageDialogComponent(
                allowed_pids,
                self.context.logger,
                self.context.config.dry_run,
                win32=self.win32,
                action_policy=self.context.action_policy,
            ).close_with_action(action)
            self.win32.set_foreground(self.hwnd)
            return result

        return StepResult(ok=True, name="message_dialog.close_if_present", status="skipped")
