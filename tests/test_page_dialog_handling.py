import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.pages.special_deduction.page import SpecialDeductionPage
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class FakeLogger:
    def log(self, *_args, **_kwargs):
        pass


class FakeDialog:
    def __init__(self):
        self.actions = []

    def close_with_action(self, action):
        self.actions.append(action)
        return StepResult(ok=True, name="dialog", status="closed")


class PageDialogHandlingTests(unittest.TestCase):
    def _context(self):
        return RpaContext(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx"), dry_run=True),
            logger=FakeLogger(),
            main_window={"pid": 10, "hwnd": 100},
        )

    def test_person_info_open_closes_dialog_before_and_after_navigation(self):
        dialog = FakeDialog()
        page = PersonInfoPage(context=self._context(), hwnd=100, message_dialog=dialog)

        with patch("tax_rpa.pages.person_info.page.LeftNavComponent") as component:
            component.return_value.open_page.return_value = StepResult(
                ok=True,
                name="left_nav.open_page",
                status="navigated",
            )

            result = page.open()

        self.assertTrue(result.ok)
        self.assertEqual(dialog.actions, ["cancel", "cancel"])

    def test_special_deduction_open_closes_dialog_before_and_after_navigation(self):
        dialog = FakeDialog()
        page = SpecialDeductionPage(
            context=self._context(),
            hwnd=100,
            message_dialog=dialog,
        )

        with patch("tax_rpa.pages.special_deduction.page.LeftNavComponent") as component:
            component.return_value.open_page.return_value = StepResult(
                ok=True,
                name="left_nav.open_page",
                status="navigated",
            )

            result = page.open()

        self.assertTrue(result.ok)
        self.assertEqual(dialog.actions, ["cancel", "cancel"])

    def test_comprehensive_income_open_closes_dialog_before_and_after_navigation(self):
        dialog = FakeDialog()
        page = ComprehensiveIncomePage(
            context=self._context(),
            hwnd=100,
            message_dialog=dialog,
        )

        with patch("tax_rpa.pages.comprehensive_income.page.LeftNavComponent") as component:
            component.return_value.open_page.return_value = StepResult(
                ok=True,
                name="left_nav.open_page",
                status="navigated",
            )

            result = page.open()

        self.assertTrue(result.ok)
        self.assertEqual(dialog.actions, ["cancel", "cancel"])


if __name__ == "__main__":
    unittest.main()
