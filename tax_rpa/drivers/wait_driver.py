import time
from collections.abc import Callable
from typing import Any


class WaitDriver:
    """等待驱动驱动，封装底层系统能力，供页面组件调用。"""
    def until(
        self,
        name: str,
        condition: Callable[[], Any],
        timeout_seconds: int,
        interval_seconds: float = 1.0,
    ) -> Any:
        """执行底层驱动、等待驱动中的until逻辑，供业务流程或相邻模块调用。"""
        deadline = time.time() + timeout_seconds
        last_value = None
        while time.time() < deadline:
            last_value = condition()
            if last_value:
                return last_value
            time.sleep(interval_seconds)
        raise RuntimeError(f"Timed out waiting for {name}; last_value={last_value!r}")
