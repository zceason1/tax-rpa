from typing import Any


class OpenComprehensiveIncomePageStep:
    """open综合所得收入页面步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, shell: Any) -> None:
        """初始化open综合所得收入页面步骤实例，保存依赖、配置和运行上下文。"""
        self.shell = shell

    def run(self):
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        return self.shell.open_comprehensive_income_page()
