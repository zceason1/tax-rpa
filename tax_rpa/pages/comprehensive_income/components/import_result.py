import time
from typing import Any

from tax_rpa.drivers.ocr_driver import ocr_rect
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.comprehensive_income.elements.import_result import (
    classify_salary_income_import_result,
)
from tax_rpa.runtime.result import StepResult


class SalaryIncomeImportResultComponent:
    """工资薪金导入结果组件，负责读取并分类导入反馈。"""
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        allowed_pids: set[int],
        win32: Win32Driver | None = None,
    ) -> None:
        """初始化工资薪金收入导入结果component实例，保存依赖、配置和运行上下文。"""
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.allowed_pids = allowed_pids
        self.win32 = win32 or Win32Driver()

    def read_result(self) -> StepResult:
        """读取当前业务结果并转换成标准步骤结果。"""
        if self.config.dry_run:
            return StepResult(
                ok=True,
                name="salary_income.wait_import_result",
                status="dry_run",
            )
        result = self.wait_for_import_result()
        status = str(result.get("status", "unknown"))
        ok = status == "success"
        if status == "failed":
            error_type = "IMPORT_FAILED"
            error_code = "salary_income_import_failed"
            error = "Salary income import failed"
        elif status == "success":
            error_type = None
            error_code = None
            error = None
        else:
            error_type = "UNKNOWN_RESULT"
            error_code = "salary_income_import_result_unknown"
            error = "Salary income import result was not recognized"
        return StepResult(
            ok=ok,
            name="salary_income.wait_import_result",
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
        """收集当前可能代表导入结果的弹窗文本。"""
        dialogs = []
        for window in self.win32.collect_top_windows():
            if window["pid"] not in self.allowed_pids:
                continue
            if window["class"] == "#32770" and window["area"] > 1000:
                texts = self.win32.collect_window_texts(window["hwnd"])
                dialogs.append(
                    {
                        **window,
                        "texts": texts,
                        "result": classify_salary_income_import_result(texts),
                    }
                )
        return dialogs

    def wait_for_import_result(self) -> dict[str, Any]:
        """等待导入结果出现，并返回分类所需证据。"""
        deadline = time.time() + self.config.result_timeout_seconds
        last_dialogs: list[dict[str, Any]] = []

        while time.time() < deadline:
            dialogs = self.collect_result_dialogs()
            last_dialogs = dialogs
            for dialog in dialogs:
                if dialog["result"] in {"success", "failed"}:
                    self.logger.screenshot(
                        f"salary_result_dialog_{dialog['result']}",
                        dialog["rect"],
                    )
                    return {
                        "status": dialog["result"],
                        "source": "dialog",
                        "dialog": dialog,
                    }

            rect = self.win32.get_rect(self.hwnd)
            rows, _image_size, image_path = ocr_rect(
                rect,
                "after_salary_import_scan",
                self.logger,
            )
            texts = [str(row.get("text", "")) for row in rows]
            result = classify_salary_income_import_result(texts)
            self.logger.log(
                "scan_salary_import_result",
                result,
                texts=texts,
                screenshot=image_path,
            )
            if result in {"success", "failed"}:
                return {"status": result, "source": "main_ocr", "texts": texts}
            time.sleep(2.0)

        return {"status": "unknown", "source": "timeout", "dialogs": last_dialogs}
