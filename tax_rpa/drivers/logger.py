import dataclasses
import json
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    """执行底层驱动、日志中的now逻辑，供业务流程或相邻模块调用。"""
    return datetime.now().isoformat(timespec="seconds")


def to_jsonable(value: Any) -> Any:
    """执行底层驱动、日志中的tojsonable逻辑，供业务流程或相邻模块调用。"""
    if dataclasses.is_dataclass(value):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


class RunLogger:
    """run日志，封装底层驱动、日志相关状态和行为。"""
    def __init__(self) -> None:
        """初始化run日志实例，保存依赖、配置和运行上下文。"""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out_dir = Path("artifacts") / f"person_import_{stamp}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.out_dir / "steps.jsonl"

    def log(self, step: str, status: str, **data: Any) -> None:
        """写入日志事件，记录当前动作或状态。"""
        item = {"time": now(), "step": step, "status": status, **data}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(to_jsonable(item), ensure_ascii=False) + "\n")
        print(f"[{item['time']}] {step}: {status}")

    @contextmanager
    def step(self, name: str, **data: Any):
        """创建页面局部步骤上下文，用于记录日志和截图。"""
        started = time.perf_counter()
        self.log(name, "start", **data)
        try:
            yield
        except Exception as exc:
            failed_data = {
                **data,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "duration_ms": round((time.perf_counter() - started) * 1000),
            }
            self.log(
                name,
                "failed",
                **failed_data,
            )
            raise
        else:
            passed_data = {
                **data,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            }
            self.log(
                name,
                "passed",
                **passed_data,
            )

    def write_json(self, name: str, data: Any) -> str:
        """把数据写入作业产物目录下的 JSON 文件。"""
        path = self.out_dir / name
        path.write_text(
            json.dumps(to_jsonable(data), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path.resolve())

    def screenshot(self, name: str, rect: list[int]) -> str:
        """执行底层驱动、日志中的截图逻辑，供业务流程或相邻模块调用。"""
        from PIL import ImageGrab

        path = self.out_dir / f"{name}.png"
        ImageGrab.grab(bbox=tuple(rect)).save(path)
        return str(path.resolve())
