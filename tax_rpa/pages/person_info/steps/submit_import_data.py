from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.person_info.page import PersonInfoPage


class SubmitImportDataStep:
    """提交导入data步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, page: "PersonInfoPage") -> None:
        """初始化提交导入data步骤实例，保存依赖、配置和运行上下文。"""
        self.page = page

    def run(self) -> StepResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        with self.page.step("提交人员信息数据"):
            return self.page.click_submit_data()
