from contextlib import nullcontext
from typing import Any

from tax_rpa.components.content_text import ContentTextComponent
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.drivers.mouse_driver import MouseDriver
from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.special_deduction.elements.download_update import (
    ALL_PERSONS_OPTION,
    DOWNLOAD_UPDATE_BUTTON,
)
from tax_rpa.pages.special_deduction.elements.page_markers import (
    SPECIAL_DEDUCTION_PAGE_MARKER,
)
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class SpecialDeductionPage(PageDialogMixin):
    def __init__(
        self,
        context: RpaContext | None,
        hwnd: int,
        toolbar: Any | None = None,
        content_text: Any | None = None,
        message_dialog: Any | None = None,
        mouse: MouseDriver | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.context = context
        self.hwnd = hwnd
        self.toolbar = toolbar
        self.content_text = content_text
        self.message_dialog = message_dialog
        self.mouse = mouse or MouseDriver()
        self.ocr = OcrDriver()
        self.region = RegionDriver()
        self.win32 = win32 or Win32Driver()

    def inspect(self) -> dict[str, Any]:
        if self.context is None:
            return {"ready": False}

        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _nav_source = self.region.detect_left_nav_rect(rect, children)
        content_rect, _content_source = self.region.detect_content_rect(rect, nav_rect, children)
        rows, image_size, image_path = ocr_rect(
            content_rect,
            "special_deduction_page_verify",
            self.context.logger,
        )
        has_page = find_best_ocr_match(
            rows,
            SPECIAL_DEDUCTION_PAGE_MARKER.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_download = find_best_ocr_match(
            rows,
            DOWNLOAD_UPDATE_BUTTON.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        self.context.logger.log(
            "verify_special_deduction_page",
            "ok" if has_page or has_download else "not_ready",
            page_match=has_page,
            download_match=has_download,
            screenshot=image_path,
        )
        return {
            "ready": bool(has_page or has_download),
            "page_match": has_page,
            "download_match": has_download,
            "content_rect": content_rect,
            "screenshot": image_path,
        }

    def is_ready(self) -> bool:
        return bool(self.inspect()["ready"])

    def open(self) -> StepResult:
        if self.context is None:
            return StepResult(ok=True, name="special_deduction_page.open", status="assumed_ready")
        before_dialog = self.close_message_dialog_if_present("cancel")
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).open_page(
            SPECIAL_DEDUCTION_PAGE_MARKER.text,
            ready_check=self.is_ready,
        )
        after_dialog = self.close_message_dialog_if_present("cancel")
        return StepResult(
            ok=result.ok,
            name="special_deduction_page.open",
            status=result.status,
            evidence={
                **result.evidence,
                "before_dialog": before_dialog,
                "after_dialog": after_dialog,
            },
            error=result.error,
        )

    def step(self, name: str, **data: Any):
        logger = self.context.logger if self.context is not None else None
        step = getattr(logger, "step", None)
        if callable(step):
            return step(name, page="special_deduction_page", **data)
        return nullcontext()

    def click_download_update(self) -> StepResult:
        return self._content_text().click_text(DOWNLOAD_UPDATE_BUTTON.text)

    def click_all_persons(self) -> StepResult:
        return self._content_text().click_text(ALL_PERSONS_OPTION.text)

    def click_all_persons_fallback(
        self,
        download_result: StepResult,
        error: Exception | None = None,
    ) -> StepResult:
        click_info = download_result.evidence.get("click", {})
        origin = click_info.get("click")
        match = click_info.get("match", {})
        box = match.get("box") or []
        if not isinstance(origin, list) or len(origin) != 2:
            return StepResult(
                ok=False,
                name="special_deduction.click_all_persons_fallback",
                status="fallback_coordinates_missing",
                evidence={"download_update": download_result.evidence},
                error="All persons fallback requires the prior download-update click coordinates",
            )

        height = 0
        if len(box) >= 4:
            ys = [point[1] for point in box if isinstance(point, list) and len(point) >= 2]
            if ys:
                height = max(ys) - min(ys)
        offset_y = max(48, round(height * 2.2)) if height else 56
        target = [int(origin[0]), int(origin[1] + offset_y)]

        logger = getattr(self.context, "logger", None) if self.context is not None else None
        action_policy = (
            getattr(self.context, "action_policy", None) if self.context is not None else None
        )
        if action_policy is not None:
            decision = action_policy.before_click(
                ALL_PERSONS_OPTION.text,
                {"step_name": "special_deduction.click_all_persons_fallback"},
            )
            if not decision.allowed:
                return decision.to_step_result("special_deduction.click_all_persons_fallback")
        if logger is not None:
            logger.log(
                "special_deduction_all_persons_fallback",
                "click",
                origin=origin,
                target=target,
                prior_error=str(error) if error else None,
            )

        click_result = self.mouse.click(target)
        return StepResult(
            ok=True,
            name="special_deduction.click_all_persons_fallback",
            status="clicked",
            evidence={
                "download_update": download_result.evidence,
                "fallback_target": target,
                "click_result": click_result,
                "prior_error": str(error) if error else None,
            },
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

    def default_content_text(self) -> ContentTextComponent:
        if self.context is None:
            raise RuntimeError("Default content text requires RpaContext")
        return ContentTextComponent(
            self._content_rect(),
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
            action_policy=self.context.action_policy,
        )

    def _content_text(self) -> Any:
        if self.content_text is not None:
            return self.content_text
        return self.default_content_text()

    def _content_rect(self) -> list[int]:
        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _ = self.region.detect_left_nav_rect(rect, children)
        content_rect, _ = self.region.detect_content_rect(rect, nav_rect, children)
        return content_rect
