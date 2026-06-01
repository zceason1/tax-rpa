import time
from typing import Any

from tax_rpa.drivers.ocr_driver import ocr_rect
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.person_info.elements.import_result import classify_import_result
from tax_rpa.runtime.result import StepResult


class ImportResultComponent:
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        allowed_pids: set[int],
        win32: Win32Driver | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.allowed_pids = allowed_pids
        self.win32 = win32 or Win32Driver()

    def read_result(self) -> StepResult:
        if self.config.dry_run:
            return StepResult(ok=True, name="wait_import_result", status="dry_run")
        result = self.wait_for_import_result()
        status = str(result.get("status", "unknown"))
        ok = status in {"success", "ready_to_submit"}
        if status == "failed":
            error_type = "IMPORT_FAILED"
            error_code = "person_import_failed"
            error = "Personnel import failed"
        elif status in {"success", "ready_to_submit"}:
            error_type = None
            error_code = None
            error = None
        else:
            error_type = "UNKNOWN_RESULT"
            error_code = "person_import_result_unknown"
            error = "Personnel import result was not recognized"
        return StepResult(
            ok=ok,
            name="wait_import_result",
            status=status,
            evidence={"result": result},
            error=error,
            error_type=error_type,
            error_code=error_code,
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

    def collect_result_dialogs(self) -> list[dict[str, Any]]:
        dialogs = []
        for window in self.win32.collect_top_windows():
            if window["pid"] not in self.allowed_pids:
                continue
            if (
                window["class"] in {"#32770", "Tfrm_MsgDlgRich", "TMessageForm", "Tfrm_MessageDlg"}
                and window["area"] > 1000
            ):
                texts = self.win32.collect_window_texts(window["hwnd"])
                dialogs.append({**window, "texts": texts, "result": classify_import_result(texts)})
        return dialogs

    def wait_for_import_result(self) -> dict[str, Any]:
        deadline = time.time() + self.config.result_timeout_seconds
        last_dialogs: list[dict[str, Any]] = []

        while time.time() < deadline:
            dialogs = self.collect_result_dialogs()
            last_dialogs = dialogs
            for dialog in dialogs:
                if dialog["result"] in {"success", "failed", "ready_to_submit"}:
                    self.logger.screenshot(f"result_dialog_{dialog['result']}", dialog["rect"])
                    return {
                        "status": dialog["result"],
                        "source": "dialog",
                        "dialog": dialog,
                    }

            rect = self.win32.get_rect(self.hwnd)
            rows, _image_size, image_path = ocr_rect(rect, "after_import_scan", self.logger)
            texts = [str(row.get("text", "")) for row in rows]
            result = classify_import_result(texts)
            self.logger.log("scan_import_result", result, texts=texts, screenshot=image_path)
            if result in {"success", "failed", "ready_to_submit"}:
                return {"status": result, "source": "main_ocr", "texts": texts}
            time.sleep(2.0)

        return {"status": "unknown", "source": "timeout", "dialogs": last_dialogs}
