import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.app.main_shell import MainShell
from tax_rpa.runtime.result import StepResult


class FakePage:
    def __init__(self, _context, _hwnd, result):
        self.result = result

    def open(self):
        return self.result


class MainShellOpenChecksTests(unittest.TestCase):
    def test_person_info_open_failure_raises(self):
        shell = MainShell(SimpleNamespace(hwnd=100))

        with patch(
            "tax_rpa.app.main_shell.PersonInfoPage",
            lambda context, hwnd: FakePage(
                context,
                hwnd,
                StepResult(
                    ok=False,
                    name="person_info_page.open",
                    status="timeout",
                    error="Timed out waiting for page",
                ),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Timed out waiting for page"):
                shell.open_person_info_page()

    def test_comprehensive_income_open_success_returns_page(self):
        shell = MainShell(SimpleNamespace(hwnd=100))

        with patch(
            "tax_rpa.app.main_shell.ComprehensiveIncomePage",
            lambda context, hwnd: FakePage(
                context,
                hwnd,
                StepResult(
                    ok=True,
                    name="comprehensive_income_page.open",
                    status="navigated",
                ),
            ),
        ):
            page = shell.open_comprehensive_income_page()

        self.assertIsInstance(page, FakePage)


if __name__ == "__main__":
    unittest.main()
