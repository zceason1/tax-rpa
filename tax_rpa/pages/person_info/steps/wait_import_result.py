from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.person_info.page import PersonInfoPage


class WaitImportResultStep:
    def __init__(self, page: "PersonInfoPage") -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("等待导入结果"):
            return self.page.read_import_result()
