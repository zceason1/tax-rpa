from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.components.content_text import ContentTextComponent
from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.components.toolbar import ToolbarComponent
from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.comprehensive_income.elements.import_menu import (
    IMPORT_BUTTON,
    IMPORT_DATA_OPTION,
)
from tax_rpa.pages.comprehensive_income.elements.page_markers import (
    COMPREHENSIVE_INCOME_PAGE_MARKER,
)
from tax_rpa.pages.comprehensive_income.elements.salary_income import (
    FILL_BUTTON,
    SALARY_INCOME_ROW,
)
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class ComprehensiveIncomePage(PageDialogMixin):
    def __init__(
        self,
        context: RpaContext | None,
        hwnd: int,
        toolbar: Any | None = None,
        content_text: Any | None = None,
        file_dialog: Any | None = None,
        message_dialog: Any | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.context = context
        self.hwnd = hwnd
        self.toolbar = toolbar
        self.content_text = content_text
        self.file_dialog = file_dialog
        self.message_dialog = message_dialog
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
            "comprehensive_income_page_verify",
            self.context.logger,
        )
        has_page = find_best_ocr_match(
            rows,
            COMPREHENSIVE_INCOME_PAGE_MARKER.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_salary = find_best_ocr_match(
            rows,
            SALARY_INCOME_ROW.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        self.context.logger.log(
            "verify_comprehensive_income_page",
            "ok" if has_page or has_salary else "not_ready",
            page_match=has_page,
            salary_match=has_salary,
            screenshot=image_path,
        )
        return {
            "ready": bool(has_page or has_salary),
            "page_match": has_page,
            "salary_match": has_salary,
            "content_rect": content_rect,
            "screenshot": image_path,
        }

    def is_ready(self) -> bool:
        return bool(self.inspect()["ready"])

    def open(self) -> StepResult:
        if self.context is None:
            return StepResult(
                ok=True,
                name="comprehensive_income_page.open",
                status="assumed_ready",
            )
        before_dialog = self.close_message_dialog_if_present("cancel")
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
        ).open_page(
            COMPREHENSIVE_INCOME_PAGE_MARKER.text,
            ready_check=self.is_ready,
        )
        after_dialog = self.close_message_dialog_if_present("cancel")
        return StepResult(
            ok=result.ok,
            name="comprehensive_income_page.open",
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
            return step(name, page="comprehensive_income_page", **data)
        return nullcontext()

    def is_dry_run(self) -> bool:
        if self.context is None:
            return False
        return bool(self.context.config.dry_run)

    def click_salary_income_row(self) -> StepResult:
        return self._content_text().click_text(SALARY_INCOME_ROW.text)

    def click_salary_income_fill(self) -> StepResult:
        return self._content_text().click_text(FILL_BUTTON.text)

    def click_import_button(self) -> StepResult:
        if self.toolbar is not None:
            return self.toolbar.click_button(IMPORT_BUTTON.text)
        return self.default_toolbar().click_button(IMPORT_BUTTON.text)

    def choose_import_data_option(self) -> StepResult:
        return self._content_text().click_text(IMPORT_DATA_OPTION.text)

    def choose_salary_income_file(self, path: Path, import_option_result: StepResult) -> StepResult | None:
        dialog = import_option_result.evidence.get("dialog")
        if self.file_dialog is not None:
            return self.file_dialog.choose_file(path)
        if not dialog:
            dialog = self._find_file_dialog()
        if not dialog:
            return None
        return FileDialogComponent(
            dialog,
            self.context.logger,
            self.context.config.dry_run,
            win32=self.win32,
        ).choose_file(path)

    def default_toolbar(self) -> ToolbarComponent:
        if self.context is None:
            raise RuntimeError("Default toolbar requires RpaContext")
        return ToolbarComponent(
            self._content_rect(),
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
        )

    def default_content_text(self) -> ContentTextComponent:
        if self.context is None:
            raise RuntimeError("Default content text requires RpaContext")
        return ContentTextComponent(
            self._content_rect(),
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
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

    def _find_file_dialog(self) -> dict[str, Any] | None:
        if self.context is None or self.context.main_window is None:
            return None
        allowed_pids = {int(self.context.main_window["pid"])}
        dialog = self.win32.find_file_dialog(
            min(5, self.context.config.import_timeout_seconds),
            allowed_pids,
        )
        if dialog:
            return dialog
        return self.win32.find_file_dialog(1, None)
