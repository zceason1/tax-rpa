from collections.abc import Callable
from typing import Protocol

from tax_rpa.runtime.result import StepResult


class StepRunner(Protocol):
    """步骤执行器，封装运行时、步骤执行器相关状态和行为。"""
    def run_step(
        self,
        *,
        workflow: str,
        step: str,
        operation: Callable[[], StepResult],
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        """执行运行时、步骤执行器中的run步骤逻辑，供业务流程或相邻模块调用。"""
        ...


class DirectStepRunner:
    """直接步骤执行器，用于无作业上下文时顺序执行步骤函数。"""
    def run_step(
        self,
        *,
        workflow: str,
        step: str,
        operation: Callable[[], StepResult],
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        """执行运行时、步骤执行器中的run步骤逻辑，供业务流程或相邻模块调用。"""
        return operation()
