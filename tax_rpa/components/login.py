import time
from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.runtime.result import StepResult


DECLARATION_PASSWORD_LOGIN_TEXT = "申报密码登录"
PASSWORD_PLACEHOLDER_TEXT = "请输入密码"
class PyAutoGuiKeyboard:
    def hotkey(self, *keys: str) -> None:
        import pyautogui

        pyautogui.hotkey(*keys)

    def write(self, text: str, interval: float = 0) -> None:
        import pyautogui

        pyautogui.write(text, interval=interval)

    def press(self, key: str, presses: int = 1, interval: float = 0) -> None:
        import pyautogui

        pyautogui.press(key, presses=presses, interval=interval)


class LoginComponent:
    def __init__(
        self,
        hwnd: int,
        window_rect: list[int],
        logger: Any,
        config: Any,
        ocr: OcrDriver | None = None,
        keyboard: Any | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.window_rect = window_rect
        self.logger = logger
        self.config = config
        self.ocr = ocr or OcrDriver()
        self.keyboard = keyboard or PyAutoGuiKeyboard()

    def login_with_declaration_password(self, password: str) -> StepResult:
        self.logger.log(
            "login",
            "start",
            method=DECLARATION_PASSWORD_LOGIN_TEXT,
            password_configured=bool(password),
        )
        method_click = self.ocr.click_text(
            self.window_rect,
            DECLARATION_PASSWORD_LOGIN_TEXT,
            self.logger,
            self.config.ocr_score_threshold,
            self.config.dry_run,
            "login_method_declaration_password",
        )
        if not self.config.dry_run:
            time.sleep(0.3)
        password_field_click = self.ocr.click_text(
            self.window_rect,
            PASSWORD_PLACEHOLDER_TEXT,
            self.logger,
            self.config.ocr_score_threshold,
            self.config.dry_run,
            "login_password_field",
        )
        if not self.config.dry_run:
            time.sleep(0.2)
            self.keyboard.hotkey("ctrl", "a")
            self.keyboard.write(password, interval=0)
            time.sleep(0.2)
            self.keyboard.press("enter", presses=2, interval=0.2)
        submit_action = {
            "method": "enter",
            "presses": 2,
            "dry_run": self.config.dry_run,
        }
        self.logger.log("login_submit", "dry_run" if self.config.dry_run else "enter", **submit_action)
        return StepResult(
            ok=True,
            name="login.declaration_password",
            status="dry_run" if self.config.dry_run else "submitted",
            evidence={
                "method": DECLARATION_PASSWORD_LOGIN_TEXT,
                "password_configured": bool(password),
                "method_click": method_click,
                "password_field_click": password_field_click,
                "submit_action": submit_action,
            },
        )
