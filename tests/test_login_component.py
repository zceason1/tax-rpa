import unittest
from types import SimpleNamespace

from tax_rpa.components.login import (
    DECLARATION_PASSWORD_LOGIN_TEXT,
    PASSWORD_PLACEHOLDER_TEXT,
    LoginComponent,
)


class FakeLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, step, status, **data):
        self.events.append((step, status, data))


class FakeOcr:
    def __init__(self, events=None) -> None:
        self.clicks = []
        self.events = events

    def click_text(self, rect, text, logger, min_score, dry_run, artifact_name):
        self.clicks.append((rect, text, min_score, dry_run, artifact_name))
        if self.events is not None:
            self.events.append(("click", text))
        return {"label": text, "dry_run": dry_run}


class FakeKeyboard:
    def __init__(self, events=None) -> None:
        self.calls = []
        self.events = events

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))
        if self.events is not None:
            self.events.append(("hotkey", keys))

    def write(self, text, interval=0):
        self.calls.append(("write", text, interval))
        if self.events is not None:
            self.events.append(("write", text, interval))

    def press(self, key, presses=1, interval=0):
        self.calls.append(("press", key, presses, interval))
        if self.events is not None:
            self.events.append(("press", key, presses, interval))


class FakeUia:
    def __init__(self, enabled=True, events=None) -> None:
        self.enabled = enabled
        self.events = events
        self.invoke_calls = []
        self.focus_calls = []

    def invoke_text(self, hwnd, text, artifact_name):
        self.invoke_calls.append((hwnd, text, artifact_name))
        if self.events is not None:
            self.events.append(("uia_invoke", text))
        if not self.enabled:
            return None
        return {"source": "uia", "action": "invoke", "label": text}

    def focus_text(self, hwnd, text, artifact_name):
        self.focus_calls.append((hwnd, text, artifact_name))
        if self.events is not None:
            self.events.append(("uia_focus", text))
        if not self.enabled:
            return None
        return {"source": "uia", "action": "focus", "label": text}


class LoginComponentTests(unittest.TestCase):
    def test_declaration_password_login_uses_uia_before_ocr_when_available(self):
        logger = FakeLogger()
        ocr = FakeOcr()
        keyboard = FakeKeyboard()
        uia = FakeUia(enabled=True)
        component = LoginComponent(
            hwnd=100,
            window_rect=[0, 0, 800, 600],
            logger=logger,
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=False),
            ocr=ocr,
            keyboard=keyboard,
            uia=uia,
        )

        result = component.login_with_declaration_password("secret-password")

        self.assertTrue(result.ok)
        self.assertEqual(ocr.clicks, [])
        self.assertEqual(
            uia.invoke_calls,
            [(100, DECLARATION_PASSWORD_LOGIN_TEXT, "login_method_declaration_password")],
        )
        self.assertEqual(
            uia.focus_calls,
            [(100, PASSWORD_PLACEHOLDER_TEXT, "login_password_field")],
        )
        self.assertEqual(result.evidence["method_click"]["source"], "uia")
        self.assertEqual(result.evidence["password_field_click"]["source"], "uia")

    def test_declaration_password_login_falls_back_to_ocr_when_uia_is_unavailable(self):
        logger = FakeLogger()
        ocr = FakeOcr()
        keyboard = FakeKeyboard()
        uia = FakeUia(enabled=False)
        component = LoginComponent(
            hwnd=100,
            window_rect=[0, 0, 800, 600],
            logger=logger,
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=False),
            ocr=ocr,
            keyboard=keyboard,
            uia=uia,
        )

        result = component.login_with_declaration_password("secret-password")

        self.assertTrue(result.ok)
        self.assertEqual(
            [click[1] for click in ocr.clicks],
            [DECLARATION_PASSWORD_LOGIN_TEXT, PASSWORD_PLACEHOLDER_TEXT],
        )
        self.assertEqual(len(uia.invoke_calls), 1)
        self.assertEqual(len(uia.focus_calls), 1)

    def test_declaration_password_login_selects_method_enters_password_and_submits_with_enter(self):
        logger = FakeLogger()
        ocr = FakeOcr()
        keyboard = FakeKeyboard()
        component = LoginComponent(
            hwnd=100,
            window_rect=[0, 0, 800, 600],
            logger=logger,
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=False),
            ocr=ocr,
            keyboard=keyboard,
            uia=FakeUia(enabled=False),
        )

        result = component.login_with_declaration_password("secret-password")

        self.assertTrue(result.ok)
        self.assertEqual(
            [click[1] for click in ocr.clicks],
            ["申报密码登录", "请输入密码"],
        )
        self.assertIn(("hotkey", ("ctrl", "a")), keyboard.calls)
        self.assertIn(("write", "secret-password", 0), keyboard.calls)
        self.assertIn(("press", "enter", 2, 0.2), keyboard.calls)

    def test_declaration_password_login_focuses_password_field_before_typing(self):
        logger = FakeLogger()
        events = []
        ocr = FakeOcr(events)
        keyboard = FakeKeyboard(events)
        component = LoginComponent(
            hwnd=100,
            window_rect=[0, 0, 800, 600],
            logger=logger,
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=False),
            ocr=ocr,
            keyboard=keyboard,
            uia=FakeUia(enabled=False),
        )

        component.login_with_declaration_password("secret-password")

        self.assertLess(
            events.index(("click", "请输入密码")),
            events.index(("write", "secret-password", 0)),
        )
        self.assertLess(
            events.index(("write", "secret-password", 0)),
            events.index(("press", "enter", 2, 0.2)),
        )

    def test_declaration_password_login_does_not_log_plaintext_password(self):
        logger = FakeLogger()
        component = LoginComponent(
            hwnd=100,
            window_rect=[0, 0, 800, 600],
            logger=logger,
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=False),
            ocr=FakeOcr(),
            keyboard=FakeKeyboard(),
            uia=FakeUia(enabled=False),
        )

        result = component.login_with_declaration_password("secret-password")

        self.assertNotIn("secret-password", repr(result))
        self.assertNotIn("secret-password", repr(logger.events))


if __name__ == "__main__":
    unittest.main()
