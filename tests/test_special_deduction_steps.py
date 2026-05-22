import unittest
from contextlib import nullcontext

from tax_rpa.pages.special_deduction.page import SpecialDeductionPage
from tax_rpa.pages.special_deduction.steps.download_update_all_persons import (
    DownloadUpdateAllPersonsStep,
)
from tax_rpa.runtime.result import StepResult


class RecordingTextComponent:
    def __init__(self) -> None:
        self.clicks: list[str] = []

    def click_text(self, text):
        self.clicks.append(text)
        return StepResult(ok=True, name="content_text", status="dry_run")


class FailingToolbar:
    def click_button(self, text):
        raise AssertionError(f"business action should not use toolbar click: {text}")


class FakeSpecialDeductionPage:
    def __init__(self) -> None:
        self.events: list[str] = []

    def step(self, _name, **_data):
        return nullcontext()

    def click_download_update(self):
        self.events.append("download_update")
        return StepResult(ok=True, name="download_update", status="dry_run")

    def click_all_persons(self):
        self.events.append("all_persons")
        return StepResult(ok=True, name="all_persons", status="dry_run")


class SpecialDeductionStepTests(unittest.TestCase):
    def test_download_update_button_uses_dry_run_aware_text_click(self):
        text = RecordingTextComponent()
        page = SpecialDeductionPage(
            context=None,
            hwnd=100,
            toolbar=FailingToolbar(),
            content_text=text,
        )

        result = page.click_download_update()

        self.assertTrue(result.ok)
        self.assertEqual(text.clicks, ["下载更新"])

    def test_download_update_all_persons_step_orders_business_actions(self):
        page = FakeSpecialDeductionPage()

        result = DownloadUpdateAllPersonsStep(page).run()

        self.assertTrue(result.ok)
        self.assertEqual(page.events, ["download_update", "all_persons"])


if __name__ == "__main__":
    unittest.main()
