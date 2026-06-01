import unittest
from pathlib import Path
from unittest.mock import patch

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import LoginConfig, PersonImportConfig
from tax_rpa.runtime.result import StepResult


class FakeLogger:
    def __init__(self):
        self.entries = []

    def log(self, *_args, **_kwargs):
        self.entries.append((_args, _kwargs))


class FakeWin32:
    def __init__(self) -> None:
        self.main_window_calls = 0
        self.foreground = []

    def find_process_ids(self, process_name):
        return [100]

    def find_main_window(self, pids, logger):
        self.main_window_calls += 1
        if self.main_window_calls == 1:
            raise RuntimeError("login window only")
        return {"hwnd": 200, "pid": 100, "rect": [0, 0, 800, 600]}

    def collect_top_windows_for_pids(self, pids):
        return [{"hwnd": 150, "pid": 100, "rect": [0, 0, 800, 600], "area": 480000}]

    def set_foreground(self, hwnd):
        self.foreground.append(hwnd)


class AutoLoginAppTests(unittest.TestCase):
    def test_wait_for_login_attempts_declaration_password_login_before_main_window_is_found(self):
        calls = []

        class FakeLoginComponent:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs["hwnd"], kwargs["window_rect"]))

            def login_with_declaration_password(self, password):
                calls.append(("login", password))
                return StepResult(ok=True, name="login", status="submitted")

        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login_timeout_seconds=2,
            login=LoginConfig(declaration_password="secret-password"),
        )
        app = TaxClientApp(config, FakeLogger(), win32=FakeWin32())

        with patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent):
            result = app.wait_for_login()

        self.assertTrue(result.ok)
        self.assertEqual(calls[0], ("init", 150, [0, 0, 800, 600]))
        self.assertEqual(calls[1], ("login", "secret-password"))
        self.assertEqual(app.context.main_window["hwnd"], 200)

    def test_auto_login_uses_real_clicks_even_when_business_workflow_is_dry_run(self):
        calls = []

        class FakeLoginComponent:
            def __init__(self, **kwargs):
                calls.append(("dry_run", kwargs["config"].dry_run))

            def login_with_declaration_password(self, password):
                calls.append(("login", password))
                return StepResult(ok=True, name="login", status="submitted")

        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            dry_run=True,
            login_timeout_seconds=2,
            login=LoginConfig(declaration_password="secret-password"),
        )
        app = TaxClientApp(config, FakeLogger(), win32=FakeWin32())

        with patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent):
            result = app.wait_for_login()

        self.assertTrue(result.ok)
        self.assertEqual(calls[0], ("dry_run", False))
        self.assertEqual(calls[1], ("login", "secret-password"))
        self.assertTrue(app.config.dry_run)

    def test_auto_login_brings_login_window_to_foreground_before_login_click(self):
        calls = []

        class FakeLoginComponent:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs["hwnd"]))

            def login_with_declaration_password(self, password):
                calls.append(("login", password))
                return StepResult(ok=True, name="login", status="submitted")

        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login=LoginConfig(declaration_password="secret-password"),
        )
        win32 = FakeWin32()
        app = TaxClientApp(config, FakeLogger(), win32=win32)

        with patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent):
            result = app._try_auto_login([100])

        self.assertTrue(result.ok)
        self.assertEqual(calls, [("init", 150), ("login", "secret-password")])
        self.assertEqual(win32.foreground, [150])

    def test_auto_login_prefers_real_login_viewer_over_shadow_window(self):
        calls = []

        class LoginViewerWin32(FakeWin32):
            def collect_top_windows_for_pids(self, pids):
                return [
                    {
                        "hwnd": 150,
                        "pid": 100,
                        "class": "TFormShadow",
                        "rect": [0, 0, 820, 640],
                        "area": 524800,
                    },
                    {
                        "hwnd": 151,
                        "pid": 100,
                        "class": "Tfrm_LoginViewer",
                        "rect": [10, 10, 810, 630],
                        "area": 496000,
                    },
                ]

        class FakeLoginComponent:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs["hwnd"], kwargs["window_rect"]))

            def login_with_declaration_password(self, password):
                calls.append(("login", password))
                return StepResult(ok=True, name="login", status="submitted")

        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login=LoginConfig(declaration_password="secret-password"),
        )
        app = TaxClientApp(config, FakeLogger(), win32=LoginViewerWin32())

        with patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent):
            result = app._try_auto_login([100])

        self.assertTrue(result.ok)
        self.assertEqual(calls[0], ("init", 151, [10, 10, 810, 630]))

    def test_wait_for_login_does_not_attempt_auto_login_without_password(self):
        calls = []

        class FakeLoginComponent:
            def __init__(self, **_kwargs):
                calls.append("init")

            def login_with_declaration_password(self, _password):
                calls.append("login")
                return StepResult(ok=True, name="login", status="submitted")

        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login_timeout_seconds=2,
            login=LoginConfig(declaration_password=None),
        )
        app = TaxClientApp(config, FakeLogger(), win32=FakeWin32())

        with patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent):
            result = app.wait_for_login()

        self.assertTrue(result.ok)
        self.assertEqual(calls, [])

    def test_wait_for_login_keeps_waiting_when_login_page_is_not_ready(self):
        calls = []

        class SplashThenMainWin32(FakeWin32):
            def find_main_window(self, pids, logger):
                self.main_window_calls += 1
                if self.main_window_calls <= 2:
                    raise RuntimeError("splash window only")
                return {"hwnd": 300, "pid": 100, "rect": [0, 0, 800, 600]}

        class FakeLoginComponent:
            def __init__(self, **_kwargs):
                calls.append("init")

            def login_with_declaration_password(self, _password):
                calls.append("login")
                raise RuntimeError("OCR did not find text '申报密码登录'")

        logger = FakeLogger()
        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login_timeout_seconds=3,
            login=LoginConfig(declaration_password="secret-password"),
        )
        app = TaxClientApp(config, logger, win32=SplashThenMainWin32())

        with (
            patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent),
            patch("tax_rpa.app.tax_client_app.time.sleep", lambda _seconds: None),
        ):
            result = app.wait_for_login()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "main_window_found")
        self.assertEqual(app.context.main_window["hwnd"], 300)
        self.assertEqual(calls, ["init", "login", "init", "login"])
        self.assertTrue(
            any(
                args[:2] == ("auto_login", "not_ready")
                for args, _kwargs in logger.entries
            )
        )

    def test_wait_for_login_stops_after_repeated_auto_login_element_failures(self):
        calls = []

        class LoginNeverBecomesMainWin32(FakeWin32):
            def find_main_window(self, pids, logger):
                self.main_window_calls += 1
                raise RuntimeError("login window only")

        class FakeLoginComponent:
            def __init__(self, **_kwargs):
                calls.append("init")

            def login_with_declaration_password(self, _password):
                calls.append("login")
                raise RuntimeError("OCR did not find text '申报密码登录' in login.png")

        logger = FakeLogger()
        config = PersonImportConfig(
            person_info_file=Path("persons.xlsx"),
            login_timeout_seconds=1,
            login=LoginConfig(declaration_password="secret-password"),
        )
        app = TaxClientApp(config, logger, win32=LoginNeverBecomesMainWin32())

        with (
            patch("tax_rpa.app.tax_client_app.LoginComponent", FakeLoginComponent),
            patch("tax_rpa.app.tax_client_app.time.sleep", lambda _seconds: None),
        ):
            result = app.wait_for_login()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "auto_login_failed")
        self.assertIn("Auto login failed after 3 attempts", result.error)
        self.assertIn("申报密码登录", result.error)
        self.assertEqual(calls, ["init", "login", "init", "login", "init", "login"])
        self.assertTrue(
            any(
                args[:2] == ("auto_login", "failed")
                for args, _kwargs in logger.entries
            )
        )


if __name__ == "__main__":
    unittest.main()
