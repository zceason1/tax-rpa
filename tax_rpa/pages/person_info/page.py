from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.components.toolbar import ToolbarComponent
from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.person_info.components.import_dropdown import ImportDropdownComponent
from tax_rpa.pages.person_info.components.import_result import ImportResultComponent
from tax_rpa.pages.person_info.elements.import_menu import (
    IMPORT_BUTTON,
    IMPORT_FILE_OPTIONS,
    SUBMIT_DATA_BUTTON,
)
from tax_rpa.pages.person_info.elements.page_markers import PERSON_INFO_PAGE_MARKER
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class PersonInfoPage(PageDialogMixin):
    def __init__(
        self,
        context: RpaContext | None,
        hwnd: int,
        toolbar: Any | None = None,
        import_dropdown: Any | None = None,
        file_dialog: Any | None = None,
        message_dialog: Any | None = None,
        import_result_reader: Callable[[], StepResult] | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.context = context
        self.hwnd = hwnd
        self.toolbar = toolbar
        self.import_dropdown = import_dropdown
        self.file_dialog = file_dialog
        self.message_dialog = message_dialog
        self.import_result_reader = import_result_reader
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
        rows, image_size, image_path = ocr_rect(content_rect, "person_page_verify", self.context.logger)
        has_page = find_best_ocr_match(
            rows,
            PERSON_INFO_PAGE_MARKER.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_import = find_best_ocr_match(
            rows,
            IMPORT_BUTTON.text,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        self.context.logger.log(
            "verify_person_page",
            "ok" if has_page and has_import else "not_ready",
            page_match=has_page,
            import_match=has_import,
            screenshot=image_path,
        )
        return {
            "ready": bool(has_page and has_import),
            "page_match": has_page,
            "import_match": has_import,
            "content_rect": content_rect,
            "screenshot": image_path,
        }

    def is_ready(self) -> bool:
        return bool(self.inspect()["ready"])

    def open(self) -> StepResult:
        if self.context is None:
            return StepResult(ok=True, name="person_info_page.open", status="assumed_ready")
        before_dialog = self.close_message_dialog_if_present("cancel")
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).open_page(
            PERSON_INFO_PAGE_MARKER.text,
            ready_check=self.is_ready,
        )
        after_dialog = self.close_message_dialog_if_present("cancel")
        return StepResult(
            ok=result.ok,
            name="person_info_page.open",
            status=result.status,
            evidence={
                **result.evidence,
                "before_dialog": before_dialog,
                "after_dialog": after_dialog,
            },
            error=result.error,
        )

    def import_person_file(self, path: Path) -> StepResult:
        from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
        from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
        from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep

        import_file = ImportPersonFileStep(self).run(path)
        if not import_file.ok:
            return StepResult(
                ok=False,
                name="person_info_page.import_person_file",
                status=import_file.status,
                evidence=import_file.evidence,
                error=import_file.error,
            )

        validation_result = WaitImportResultStep(self).run()
        if validation_result.status == "ready_to_submit":
            submit_result = SubmitImportDataStep(self).run()
            if not submit_result.ok:
                return StepResult(
                    ok=False,
                    name="person_info_page.import_person_file",
                    status=submit_result.status,
                    evidence={
                        **import_file.evidence,
                        "validation_result": validation_result,
                        "submit_result": submit_result,
                    },
                    error=submit_result.error,
                )
            import_result = WaitImportResultStep(self).run()
            if import_result.status == "ready_to_submit":
                import_result = StepResult(
                    ok=False,
                    name=import_result.name,
                    status="unknown",
                    evidence={
                        **import_result.evidence,
                        "post_submit_status": "ready_to_submit",
                    },
                    error="Personnel import remained at submit-data confirmation after submit",
                    error_type="UNKNOWN_RESULT",
                    error_code="person_import_result_unknown",
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            evidence = {
                **import_file.evidence,
                "validation_result": validation_result,
                "submit_result": submit_result,
                "import_result": import_result,
            }
        else:
            import_result = validation_result
            evidence = {**import_file.evidence, "import_result": import_result}
        return StepResult(
            ok=import_result.ok,
            name="person_info_page.import_person_file",
            status=import_result.status,
            evidence=evidence,
            error=import_result.error,
            error_type=import_result.error_type,
            error_code=import_result.error_code,
            side_effect_started=import_result.side_effect_started,
            side_effect_committed=import_result.side_effect_committed,
            retry_allowed=import_result.retry_allowed,
        )

    def step(self, name: str, **data: Any):
        logger = self.context.logger if self.context is not None else None
        step = getattr(logger, "step", None)
        if callable(step):
            return step(name, page="person_info_page", **data)
        return nullcontext()

    def _step(self, name: str, **data: Any):
        return self.step(name, **data)

    def click_import_button(self) -> StepResult:
        if self.toolbar is not None:
            return self.toolbar.click_button(IMPORT_BUTTON.text)
        return self.default_toolbar().click_button(IMPORT_BUTTON.text)

    def choose_import_file_option(self) -> StepResult:
        import_option = IMPORT_FILE_OPTIONS[0].text
        if self.import_dropdown is not None:
            return self.import_dropdown.choose_item(import_option)
        return self.default_import_dropdown().choose_item(import_option)

    def click_submit_data(self) -> StepResult:
        if self.toolbar is not None:
            return self.toolbar.click_button(SUBMIT_DATA_BUTTON.text)
        return self.default_toolbar().click_button(SUBMIT_DATA_BUTTON.text)

    def choose_person_file(
        self,
        path: Path,
        dropdown_result: StepResult,
    ) -> StepResult | None:
        dialog = dropdown_result.evidence.get("dialog")
        if self.file_dialog is not None:
            return self.file_dialog.choose_file(path)
        if not dialog:
            return None
        return FileDialogComponent(
            dialog,
            self.context.logger,
            self.context.config.dry_run,
            win32=self.win32,
            action_policy=self.context.action_policy,
        ).choose_file(path)

    def read_import_result(self) -> StepResult:
        if self.import_result_reader is not None:
            return self.import_result_reader()
        return self.default_import_result_component().read_result()

    def default_toolbar(self) -> ToolbarComponent:
        if self.context is None:
            raise RuntimeError("Default toolbar requires RpaContext")
        rect = self.win32.get_rect(self.hwnd)
        children = self.win32.collect_children(self.hwnd)
        nav_rect, _ = self.region.detect_left_nav_rect(rect, children)
        content_rect, _ = self.region.detect_content_rect(rect, nav_rect, children)
        return ToolbarComponent(
            content_rect,
            self.context.logger,
            self.context.config.ocr_score_threshold,
            self.context.config.dry_run,
            action_policy=self.context.action_policy,
        )

    def _default_toolbar(self) -> ToolbarComponent:
        return self.default_toolbar()

    def default_import_dropdown(self) -> ImportDropdownComponent:
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import dropdown requires RpaContext with main_window")
        allowed_pids = {int(self.context.main_window["pid"])}
        return ImportDropdownComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            allowed_pids,
            win32=self.win32,
            action_policy=self.context.action_policy,
        )

    def _default_import_dropdown(self) -> ImportDropdownComponent:
        return self.default_import_dropdown()

    def default_import_result_component(self) -> ImportResultComponent:
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import result requires RpaContext with main_window")
        allowed_pids = {int(self.context.main_window["pid"])}
        return ImportResultComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            allowed_pids,
            win32=self.win32,
        )

    def _click_import_button(self) -> StepResult:
        return self.click_import_button()

    def _choose_import_file_option(self) -> StepResult:
        return self.choose_import_file_option()

    def _click_submit_data(self) -> StepResult:
        return self.click_submit_data()

    def _choose_person_file(self, path: Path, dropdown_result: StepResult) -> StepResult | None:
        return self.choose_person_file(path, dropdown_result)

    def _read_import_result(self) -> StepResult:
        return self.read_import_result()

    def _close_message_dialog_if_present(self) -> StepResult:
        return self.close_message_dialog_if_present()
