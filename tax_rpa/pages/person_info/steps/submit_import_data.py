from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.person_info.page import PersonInfoPage


class SubmitImportDataStep:
    def __init__(self, page: "PersonInfoPage") -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("\u63d0\u4ea4\u4eba\u5458\u4fe1\u606f\u6570\u636e"):
            return self.page.click_submit_data()
