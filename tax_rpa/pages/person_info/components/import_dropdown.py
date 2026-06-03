from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.runtime.action_policy import ActionPolicy
from tax_rpa.pages.person_info.elements.import_menu import IMPORT_FILE_OPTIONS
from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.text import normalize_text


class ImportDropdownComponent:
    """导入下拉组件，负责从导入菜单中选择指定导入项。"""
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        allowed_pids: set[int],
        ocr: OcrDriver | None = None,
        win32: Win32Driver | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        """初始化导入dropdowncomponent实例，保存依赖、配置和运行上下文。"""
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.allowed_pids = allowed_pids
        self.ocr = ocr or OcrDriver()
        self.win32 = win32 or Win32Driver()
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def choose_item(self, text: str) -> StepResult:
        """在已展开的导入菜单中选择指定文本项。"""
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
        option_texts = tuple(target.text for target in IMPORT_FILE_OPTIONS)
        result = None
        for option in (text, *[item for item in option_texts if item != text]):
            try:
                decision = self.action_policy.before_click(
                    option,
                    {"step_name": "import_dropdown.choose_item"},
                    action_type="import",
                )
                if not decision.allowed:
                    return decision.to_step_result("import_dropdown.choose_item")
                click_result = self.ocr.click_text(
                    rect,
                    option,
                    self.logger,
                    self.config.ocr_score_threshold,
                    False,
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
