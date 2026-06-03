from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.person_info.page import PersonInfoPage


class WaitImportResultStep:
    """等待导入结果步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, page: "PersonInfoPage") -> None:
        """初始化等待导入结果步骤实例，保存依赖、配置和运行上下文。"""
        self.page = page

    def run(self) -> StepResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        with self.page.step("等待导入结果"):
            return self.page.read_import_result()
