from pathlib import Path
from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.person_info.page import PersonInfoPage


class ImportPersonFileStep:
    def __init__(self, page: "PersonInfoPage") -> None:
        self.page = page

    def run(self, path: Path) -> StepResult:
        with self.page.step("关闭提示弹窗"):
            message_result = self.page.close_message_dialog_if_present()

        with self.page.step("点击导入按钮"):
            toolbar_result = self.page.click_import_button()

        with self.page.step("选择导入文件菜单"):
            dropdown_result = self.page.choose_import_file_option()

        with self.page.step("选择人员信息文件", file_path=str(path)):
            file_result = self.page.choose_person_file(path, dropdown_result)
            if file_result is None:
                return StepResult(
                    ok=False,
                    name="person_info.import_person_file",
                    status="file_dialog_missing",
                    evidence={
                        "toolbar": toolbar_result,
                        "dropdown": dropdown_result,
                        "message_dialog": message_result,
                    },
                    error="Import file dialog was not opened",
                )

        return StepResult(
            ok=file_result.ok,
            name="person_info.import_person_file",
            status=file_result.status,
            evidence={
                "toolbar": toolbar_result,
                "dropdown": dropdown_result,
                "file_dialog": file_result,
                "message_dialog": message_result,
            },
            error=file_result.error,
            error_type=file_result.error_type,
            error_code=file_result.error_code,
            side_effect_started=file_result.ok or file_result.side_effect_started,
            side_effect_committed=file_result.ok or file_result.side_effect_committed,
            retry_allowed=False if file_result.ok else file_result.retry_allowed,
        )
