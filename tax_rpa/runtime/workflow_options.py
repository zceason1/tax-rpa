from dataclasses import dataclass
from typing import Any

from tax_rpa.runtime.action_policy import RUN_MODES


@dataclass(frozen=True)
class WorkflowRuntimeOptions:
    """工作流运行选项，承载 dry-run、运行模式和业务开关。"""
    run_mode: str
    allow_skip_personal_pension: bool = False

    def __post_init__(self) -> None:
        """在 dataclass 初始化后规范化字段，保证后续流程拿到一致的运行值。"""
        if self.run_mode not in RUN_MODES:
            raise ValueError(f"Unsupported run_mode: {self.run_mode}")

    @classmethod
    def from_config(cls, config: Any) -> "WorkflowRuntimeOptions":
        """执行运行时、工作流选项中的从零启动配置逻辑，供业务流程或相邻模块调用。"""
        return cls(
            run_mode="inspect_only"
            if getattr(config, "dry_run", False)
            else "execute_no_send",
        )
