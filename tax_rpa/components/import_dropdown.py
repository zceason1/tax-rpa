from typing import Any

from tax_rpa.constants import IMPORT_OPTION_TEXTS
from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.result import StepResult
from tax_rpa.utils import normalize_text


class ImportDropdownComponent:
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        allowed_pids: set[int],
        ocr: OcrDriver | None = None,
        win32: Win32Driver | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.allowed_pids = allowed_pids
        self.ocr = ocr or OcrDriver()
        self.win32 = win32 or Win32Driver()

    def choose_item(self, text: str) -> StepResult:
        dialog = self.win32.find_file_dialog(
            min(3, self.config.import_timeout_seconds),
            self.allowed_pids,
        )
        if not dialog:
            dialog = self.win32.find_file_dialog(1, None)
        if dialog:
            result = {"status": "file_dialog_opened", "dialog": dialog}
            return StepResult(
                ok=True,
                name="import_dropdown.choose_item",
                status=result["status"],
                evidence={"requested": text, "result": result, "dialog": dialog},
            )

        rect = self.win32.get_rect(self.hwnd)
        result = None
        for option in (text, *[item for item in IMPORT_OPTION_TEXTS if item != text]):
            try:
                click_result = self.ocr.click_text(
                    rect,
                    option,
                    self.logger,
                    self.config.ocr_score_threshold,
                    self.config.dry_run,
                    f"import_option_{normalize_text(option)}",
                )
                import time

                time.sleep(1.0)
                dialog = self.win32.find_file_dialog(
                    min(5, self.config.import_timeout_seconds),
                    self.allowed_pids,
                )
                if not dialog:
                    dialog = self.win32.find_file_dialog(1, None)
                if dialog:
                    result = {
                        "status": "option_clicked",
                        "option": option,
                        "click_result": click_result,
                        "dialog": dialog,
                    }
                    break
            except Exception as exc:
                self.logger.log("click_import_option", "not_found", option=option, error=str(exc))

        if result is None:
            self.logger.write_json(
                "top_windows_after_import_option.json",
                self.win32.collect_top_windows(),
            )
            result = {
                "status": "not_found",
                "dialog": None,
                "error": "Import menu opened, but no supported import file option or file dialog was found",
            }

        dialog = result.get("dialog")
        return StepResult(
            ok=bool(dialog),
            name="import_dropdown.choose_item",
            status=result.get("status", "unknown"),
            evidence={"requested": text, "result": result, "dialog": dialog},
            error=None if dialog else "file dialog was not opened",
        )
