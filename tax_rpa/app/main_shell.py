from typing import Any

from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.pages.special_deduction.page import SpecialDeductionPage
from tax_rpa.runtime.context import RpaContext


class MainShell:
    def __init__(self, context: RpaContext) -> None:
        self.context = context

    def open_person_info_page(self) -> PersonInfoPage:
        return self._open_checked(PersonInfoPage, "person_info_page.open")

    def open_special_deduction_page(self) -> SpecialDeductionPage:
        return self._open_checked(SpecialDeductionPage, "special_deduction_page.open")

    def open_comprehensive_income_page(self) -> ComprehensiveIncomePage:
        return self._open_checked(
            ComprehensiveIncomePage,
            "comprehensive_income_page.open",
        )

    def _open_checked(self, page_class: type[Any], action_name: str) -> Any:
        if self.context.hwnd is None:
            raise RuntimeError("Main window is not available")
        page = page_class(self.context, self.context.hwnd)
        result = page.open()
        if not result.ok:
            message = result.error or f"{action_name} failed with status: {result.status}"
            raise RuntimeError(message)
        return page
