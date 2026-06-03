from typing import Any

from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.pages.special_deduction.page import SpecialDeductionPage
from tax_rpa.runtime.context import RpaContext


class MainShell:
    """税务客户端主界面门面，负责打开各业务页面。"""
    def __init__(self, context: RpaContext) -> None:
        """初始化主入口主界面实例，保存依赖、配置和运行上下文。"""
        self.context = context

    def open_person_info_page(self) -> PersonInfoPage:
        """打开人员信息页面，并返回后续流程需要的对象或结果。"""
        return self._open_checked(PersonInfoPage, "person_info_page.open")

    def open_special_deduction_page(self) -> SpecialDeductionPage:
        """打开专项扣除页面，并返回后续流程需要的对象或结果。"""
        return self._open_checked(SpecialDeductionPage, "special_deduction_page.open")

    def open_comprehensive_income_page(self) -> ComprehensiveIncomePage:
        """打开综合所得收入页面，并返回后续流程需要的对象或结果。"""
        return self._open_checked(
            ComprehensiveIncomePage,
            "comprehensive_income_page.open",
        )

    def _open_checked(self, page_class: type[Any], action_name: str) -> Any:
        """执行客户端、主入口主界面中的内部辅助逻辑：openchecked。"""
        if self.context.hwnd is None:
            raise RuntimeError("Main window is not available")
        page = page_class(self.context, self.context.hwnd)
        result = page.open()
        if not result.ok:
            message = result.error or f"{action_name} failed with status: {result.status}"
            raise RuntimeError(message)
        return page
