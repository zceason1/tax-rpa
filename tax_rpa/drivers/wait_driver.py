import time
from collections.abc import Callable
from typing import Any


class WaitDriver:
    def until(
        self,
        name: str,
        condition: Callable[[], Any],
        timeout_seconds: int,
        interval_seconds: float = 1.0,
    ) -> Any:
        deadline = time.time() + timeout_seconds
        last_value = None
        while time.time() < deadline:
            last_value = condition()
            if last_value:
                return last_value
            time.sleep(interval_seconds)
        raise RuntimeError(f"Timed out waiting for {name}; last_value={last_value!r}")
