import time
from typing import Any

from tax_rpa.config.person_import import assert_safe_action
from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.jobs.action_policy import ActionPolicy
from tax_rpa.runtime.result import StepResult


def should_try_home_card_fallback(
    page_match: dict[str, Any] | None,
    import_match: dict[str, Any] | None,
) -> bool:
    return bool(page_match and not import_match)


class LeftNavComponent:
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        ocr: OcrDriver | None = None,
        region: RegionDriver | None = None,
        win32: Win32Driver | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.ocr = ocr or OcrDriver()
        self.region = region or RegionDriver()
        self.win32 = win32 or Win32Driver()
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def open_page(self, text: str, ready_check=None) -> StepResult:
        decision = self.action_policy.before_click(
            text,
            {"step_name": "left_nav.open_page"},
            action_type="navigation",
        )
        if not decision.allowed:
            return decision.to_step_result("left_nav.open_page")
        assert_safe_action(text)
        if ready_check and ready_check():
            return StepResult(ok=True, name="left_nav.open_page", status="already_on_page")

        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, nav_source = self.region.detect_left_nav_rect(rect, children)
        self.logger.screenshot("before_navigation", rect)

        click_result = self.ocr.click_text(
            nav_rect,
            text,
            self.logger,
            self.config.ocr_score_threshold,
            False,
            "left_nav",
        )

        if ready_check:
            deadline = time.time() + self.config.window_timeout_seconds
            while time.time() < deadline:
                time.sleep(1.0)
                if ready_check():
                    result = {
                        "status": "navigated",
                        "click_result": click_result,
                        "nav_rect": nav_rect,
                        "nav_source": nav_source,
                    }
                    return StepResult(
                        ok=True,
                        name="left_nav.open_page",
                        status="navigated",
                        evidence={"requested": text, "result": result},
                    )
            return StepResult(
                ok=False,
                name="left_nav.open_page",
                status="timeout",
                evidence={"requested": text, "click_result": click_result},
                error=f"Timed out waiting for page: {text}",
            )

        result = {
            "status": "clicked",
            "click_result": click_result,
            "nav_rect": nav_rect,
            "nav_source": nav_source,
        }
        return StepResult(
            ok=True,
            name="left_nav.open_page",
            status=result.get("status", "navigated"),
            evidence={"requested": text, "result": result},
        )
