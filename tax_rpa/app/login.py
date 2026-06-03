import time
from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.drivers.uia_driver import UiaDriver
from tax_rpa.runtime.result import StepResult


DECLARATION_PASSWORD_LOGIN_TEXT = "申报密码登录"
PASSWORD_PLACEHOLDER_TEXT = "请输入密码"


class PyAutoGuiKeyboard:
    """键盘适配器，隔离 pyautogui 键盘输入以便测试替换。"""
    def hotkey(self, *keys: str) -> None:
        """转发组合键输入，供登录流程控制焦点和选择文本。"""
        import pyautogui

        pyautogui.hotkey(*keys)

    def write(self, text: str, interval: float = 0) -> None:
        """写入目标数据或转发输入，具体行为由所在适配器决定。"""
        import pyautogui

        pyautogui.write(text, interval=interval)

    def press(self, key: str, presses: int = 1, interval: float = 0) -> None:
        """转发单键输入，供登录流程提交或切换焦点。"""
        import pyautogui

        pyautogui.press(key, presses=presses, interval=interval)


class LoginComponent:
    """登录组件，负责在登录窗口中选择申报密码登录并提交密码。"""
    def __init__(
        self,
        hwnd: int,
        window_rect: list[int],
        logger: Any,
        config: Any,
        ocr: OcrDriver | None = None,
        keyboard: Any | None = None,
        uia: Any | None = None,
    ) -> None:
        """初始化登录component实例，保存依赖、配置和运行上下文。"""
        self.hwnd = hwnd
        self.window_rect = window_rect
        self.logger = logger
        self.config = config
        self.ocr = ocr or OcrDriver()
        self.keyboard = keyboard or PyAutoGuiKeyboard()
        self.uia = uia or UiaDriver()

    def login_with_declaration_password(self, password: str) -> StepResult:
        """选择申报密码登录方式，输入密码并提交登录。"""
        self.logger.log(
            "login",
            "start",
            method=DECLARATION_PASSWORD_LOGIN_TEXT,
            password_configured=bool(password),
        )
        method_click = self._invoke_text(
            DECLARATION_PASSWORD_LOGIN_TEXT,
            "login_method_declaration_password",
        )
        if not self.config.dry_run:
            time.sleep(0.3)
        password_field_click = self._focus_text(
            PASSWORD_PLACEHOLDER_TEXT,
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

    def _invoke_text(self, text: str, artifact_name: str) -> dict[str, Any]:
        """优先用 UIA 触发文本控件，失败时回退到 OCR 点击。"""
        if not self.config.dry_run:
            result = self.uia.invoke_text(self.hwnd, text, artifact_name)
            if result is not None:
                self.logger.log("uia_action", "invoke", **result)
                return result
            self.logger.log("uia_action", "fallback_ocr", label=text, artifact_name=artifact_name)
        return self.ocr.click_text(
            self.window_rect,
            text,
            self.logger,
            self.config.ocr_score_threshold,
            self.config.dry_run,
            artifact_name,
        )

    def _focus_text(self, text: str, artifact_name: str) -> dict[str, Any]:
        """优先用 UIA 聚焦文本控件，失败时回退到 OCR 点击。"""
        if not self.config.dry_run:
            result = self.uia.focus_text(self.hwnd, text, artifact_name)
            if result is not None:
                self.logger.log("uia_action", "focus", **result)
                return result
            self.logger.log("uia_action", "fallback_ocr", label=text, artifact_name=artifact_name)
        return self.ocr.click_text(
            self.window_rect,
            text,
            self.logger,
            self.config.ocr_score_threshold,
            self.config.dry_run,
            artifact_name,
        )
