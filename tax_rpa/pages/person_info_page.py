from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.import_dropdown import ImportDropdownComponent
from tax_rpa.components.import_result import classify_import_result
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.components.message_dialog import MessageDialogComponent
from tax_rpa.components.toolbar import ToolbarComponent
from tax_rpa.constants import IMPORT_BUTTON_TEXT, IMPORT_OPTION_TEXTS, PERSON_PAGE_TEXT
from tax_rpa.drivers.ocr_driver import OcrDriver, find_best_ocr_match, ocr_rect
from tax_rpa.drivers.region_driver import RegionDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.context import RpaContext
from tax_rpa.runtime.result import StepResult


class PersonInfoPage:
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
            PERSON_PAGE_TEXT,
            image_size,
            self.context.config.ocr_score_threshold,
        )
        has_import = find_best_ocr_match(
            rows,
            IMPORT_BUTTON_TEXT,
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
        result = LeftNavComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            win32=self.win32,
        ).open_page(
            PERSON_PAGE_TEXT,
            ready_check=self.is_ready,
        )
        return StepResult(
            ok=result.ok,
            name="person_info_page.open",
            status=result.status,
            evidence=result.evidence,
            error=result.error,
        )

    def import_person_file(self, path: Path) -> StepResult:
        with self._step("关闭提示弹窗"):
            message_result = self._close_message_dialog_if_present()

        with self._step("点击导入按钮"):
            toolbar_result = self._click_import_button()

        with self._step("选择导入文件菜单"):
            dropdown_result = self._choose_import_file_option()

        with self._step("选择人员信息文件", file_path=str(path)):
            file_result = self._choose_person_file(path, dropdown_result)
            if file_result is None:
                return StepResult(
                    ok=False,
                    name="person_info_page.import_person_file",
                    status="file_dialog_missing",
                    evidence={
                        "toolbar": toolbar_result,
                        "dropdown": dropdown_result,
                        "message_dialog": message_result,
                    },
                    error="Import file dialog was not opened",
                )

        with self._step("等待导入结果"):
            result = self._read_import_result()

        return StepResult(
            ok=result.ok,
            name="person_info_page.import_person_file",
            status=result.status,
            evidence={
                "toolbar": toolbar_result,
                "dropdown": dropdown_result,
                "file_dialog": file_result,
                "import_result": result,
                "message_dialog": message_result,
            },
            error=result.error,
        )

    def _step(self, name: str, **data: Any):
        logger = self.context.logger if self.context is not None else None
        step = getattr(logger, "step", None)
        if callable(step):
            return step(name, page="person_info_page", **data)
        return nullcontext()

    def _click_import_button(self) -> StepResult:
        if self.toolbar is not None:
            return self.toolbar.click_button(IMPORT_BUTTON_TEXT)
        return self._default_toolbar().click_button(IMPORT_BUTTON_TEXT)

    def _choose_import_file_option(self) -> StepResult:
        import_option = IMPORT_OPTION_TEXTS[0]
        if self.import_dropdown is not None:
            return self.import_dropdown.choose_item(import_option)
        return self._default_import_dropdown().choose_item(import_option)

    def _choose_person_file(
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
        ).choose_file(path)

    def _read_import_result(self) -> StepResult:
        if self.import_result_reader is not None:
            return self.import_result_reader()
        return self._default_import_result()

    def _close_message_dialog_if_present(self) -> StepResult:
        if self.message_dialog is not None:
            return self.message_dialog.close_if_present()
        if self.context is not None and self.context.main_window is not None:
            allowed_pids = {int(self.context.main_window["pid"])}
            result = MessageDialogComponent(
                allowed_pids,
                self.context.logger,
                self.context.config.dry_run,
                win32=self.win32,
            ).close_if_present()
            self.win32.set_foreground(self.hwnd)
            return result
        return StepResult(ok=True, name="message_dialog.close_if_present", status="skipped")

    def _default_toolbar(self) -> ToolbarComponent:
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
        )

    def _default_import_dropdown(self) -> ImportDropdownComponent:
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import dropdown requires RpaContext with main_window")
        allowed_pids = {int(self.context.main_window["pid"])}
        return ImportDropdownComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            allowed_pids,
            win32=self.win32,
        )

    def _default_import_result(self) -> StepResult:
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Default import result requires RpaContext with main_window")
        if self.context.config.dry_run:
            return StepResult(ok=True, name="wait_import_result", status="dry_run")
        allowed_pids = {int(self.context.main_window["pid"])}
        result = self._wait_for_import_result(allowed_pids)
        return StepResult(
            ok=result["status"] != "failed",
            name="wait_import_result",
            status=result["status"],
            evidence={"result": result},
        )

    def _collect_result_dialogs(self, allowed_pids: set[int]) -> list[dict[str, Any]]:
        dialogs = []
        for window in self.win32.collect_top_windows():
            if window["pid"] not in allowed_pids:
                continue
            if window["class"] == "#32770" and window["area"] > 1000:
                texts = self.win32.collect_window_texts(window["hwnd"])
                dialogs.append({**window, "texts": texts, "result": classify_import_result(texts)})
        return dialogs

    def _wait_for_import_result(self, allowed_pids: set[int]) -> dict[str, Any]:
        import time

        deadline = time.time() + self.context.config.result_timeout_seconds
        last_dialogs: list[dict[str, Any]] = []

        while time.time() < deadline:
            dialogs = self._collect_result_dialogs(allowed_pids)
            last_dialogs = dialogs
            for dialog in dialogs:
                if dialog["result"] in {"success", "failed"}:
                    self.context.logger.screenshot(f"result_dialog_{dialog['result']}", dialog["rect"])
                    return {
                        "status": dialog["result"],
                        "source": "dialog",
                        "dialog": dialog,
                    }

            rect = self.win32.get_rect(self.hwnd)
            rows, _image_size, image_path = ocr_rect(rect, "after_import_scan", self.context.logger)
            texts = [str(row.get("text", "")) for row in rows]
            result = classify_import_result(texts)
            self.context.logger.log("scan_import_result", result, texts=texts, screenshot=image_path)
            if result in {"success", "failed"}:
                return {"status": result, "source": "main_ocr", "texts": texts}
            time.sleep(2.0)

        return {"status": "unknown", "source": "timeout", "dialogs": last_dialogs}
