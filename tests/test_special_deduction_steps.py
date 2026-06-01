import unittest
from contextlib import nullcontext
from types import SimpleNamespace

from tax_rpa.jobs.action_policy import ActionPolicy
from tax_rpa.pages.special_deduction.elements.download_update import DOWNLOAD_UPDATE_BUTTON
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


class FallbackSpecialDeductionPage(FakeSpecialDeductionPage):
    def click_all_persons(self):
        self.events.append("all_persons")
        raise RuntimeError("OCR did not find text")

    def click_all_persons_fallback(self, download_result, error=None):
        self.events.append("fallback")
        self.asserted_download_result = download_result
        self.asserted_error = error
        return StepResult(ok=True, name="all_persons_fallback", status="clicked")


class FakeMouse:
    def __init__(self) -> None:
        self.clicked: list[list[int]] = []

    def click(self, point):
        self.clicked.append(point)
        return {"requested": point, "actual": point}


class FakeLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, step, status, **data):
        self.events.append((step, status, data))


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
        self.assertEqual(text.clicks, [DOWNLOAD_UPDATE_BUTTON.text])

    def test_download_update_all_persons_step_orders_business_actions(self):
        page = FakeSpecialDeductionPage()

        result = DownloadUpdateAllPersonsStep(page).run()

        self.assertTrue(result.ok)
        self.assertEqual(page.events, ["download_update", "all_persons"])

    def test_download_update_all_persons_step_uses_fallback_when_ocr_target_is_missing(self):
        page = FallbackSpecialDeductionPage()

        result = DownloadUpdateAllPersonsStep(page).run()

        self.assertTrue(result.ok)
        self.assertEqual(page.events, ["download_update", "all_persons", "fallback"])
        self.assertEqual(result.status, "clicked")

    def test_click_all_persons_fallback_clicks_below_download_update_button(self):
        mouse = FakeMouse()
        logger = FakeLogger()
        page = SpecialDeductionPage(
            context=SimpleNamespace(
                logger=logger,
                action_policy=ActionPolicy(run_mode="execute_no_send"),
            ),
            hwnd=100,
            mouse=mouse,
        )
        download_result = StepResult(
            ok=True,
            name="download_update",
            status="clicked",
            evidence={
                "click": {
                    "click": [714, 484],
                    "match": {
                        "box": [
                            [375.0, 338.0],
                            [466.0, 338.0],
                            [466.0, 366.0],
                            [375.0, 366.0],
                        ]
                    },
                }
            },
        )

        result = page.click_all_persons_fallback(download_result, RuntimeError("ocr miss"))

        self.assertTrue(result.ok)
        self.assertEqual(mouse.clicked, [[714, 546]])
        self.assertEqual(result.evidence["fallback_target"], [714, 546])


if __name__ == "__main__":
    unittest.main()
