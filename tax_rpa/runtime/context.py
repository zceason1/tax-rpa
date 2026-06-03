from dataclasses import dataclass
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig


@dataclass
class RpaContext:
    """RPA 运行上下文，集中保存窗口句柄、日志器和底层驱动。"""
    config: PersonImportConfig
    logger: Any
    main_window: dict[str, Any] | None = None
    action_policy: Any | None = None

    @property
    def hwnd(self) -> int | None:
        """执行运行时、上下文中的hwnd逻辑，供业务流程或相邻模块调用。"""
        if not self.main_window:
            return None
        return int(self.main_window["hwnd"])
