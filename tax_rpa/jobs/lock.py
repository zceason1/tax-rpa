import getpass
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, ClassVar

try:
    import msvcrt
except ImportError:  # pragma: no cover - this project runs on Windows.
    msvcrt = None


class UiRunnerBusyError(RuntimeError):
    """ui执行器busy错误异常，表示作业、锁中的特定错误场景。"""
    def __init__(self, active_job_id: str | None, metadata: dict[str, object]) -> None:
        """初始化ui执行器busy错误实例，保存依赖、配置和运行上下文。"""
        super().__init__(f"UI runner is busy with job: {active_job_id or 'unknown'}")
        self.active_job_id = active_job_id
        self.metadata = metadata


@dataclass(frozen=True)
class UiRunnerLock:
    """ui执行器锁，封装作业、锁相关状态和行为。"""
    lock_path: Path = Path("artifacts/runner.lock.json")

    _local_locks: ClassVar[dict[Path, dict[str, object]]] = {}

    def acquire(self, job_id: str) -> "UiRunnerLockLease":
        """执行作业、锁中的acquire逻辑，供业务流程或相邻模块调用。"""
        metadata_path = self.lock_path.resolve()
        lock_file_path = _mutex_path(metadata_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_file_path in self._local_locks:
            metadata = self._local_locks[lock_file_path]
            raise UiRunnerBusyError(_active_job_id(metadata), metadata)

        stream = lock_file_path.open("a+b")
        try:
            _lock_stream(stream)
        except OSError:
            metadata = _read_metadata(metadata_path)
            stream.close()
            raise UiRunnerBusyError(_active_job_id(metadata), metadata)

        metadata = _build_metadata(job_id)
        lease = UiRunnerLockLease(
            lock_file_path=lock_file_path,
            metadata_path=metadata_path,
            stream=stream,
            metadata=metadata,
        )
        lease.heartbeat()
        self._local_locks[lock_file_path] = metadata
        return lease


@dataclass
class UiRunnerLockLease:
    """ui执行器锁lease，封装作业、锁相关状态和行为。"""
    lock_file_path: Path
    metadata_path: Path
    stream: BinaryIO
    metadata: dict[str, object]
    released: bool = False

    def heartbeat(self) -> None:
        """执行作业、锁中的heartbeat逻辑，供业务流程或相邻模块调用。"""
        if self.released:
            return
        self.metadata["heartbeat_at"] = _now()
        _write_metadata(self.metadata_path, self.metadata)

    def release(self) -> None:
        """执行作业、锁中的release逻辑，供业务流程或相邻模块调用。"""
        if self.released:
            return
        try:
            _unlock_stream(self.stream)
        finally:
            self.stream.close()
            UiRunnerLock._local_locks.pop(self.lock_file_path, None)
            self.released = True

    def __enter__(self) -> "UiRunnerLockLease":
        """执行作业、锁中的内部辅助逻辑：enter。"""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """执行作业、锁中的内部辅助逻辑：exit。"""
        self.release()


def _build_metadata(job_id: str) -> dict[str, object]:
    """执行作业、锁中的内部辅助逻辑：build元数据。"""
    now = _now()
    return {
        "job_id": job_id,
        "process_id": os.getpid(),
        "windows_user": getpass.getuser(),
        "acquired_at": now,
        "heartbeat_at": now,
    }


def _active_job_id(metadata: dict[str, object]) -> str | None:
    """执行作业、锁中的内部辅助逻辑：active作业id。"""
    job_id = metadata.get("job_id")
    return str(job_id) if job_id else None


def _lock_stream(stream: BinaryIO) -> None:
    """执行作业、锁中的内部辅助逻辑：锁stream。"""
    if msvcrt is None:
        return
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)


def _unlock_stream(stream: BinaryIO) -> None:
    """执行作业、锁中的内部辅助逻辑：unlockstream。"""
    if msvcrt is None:
        return
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _write_metadata(path: Path, metadata: dict[str, object]) -> None:
    """写入元数据，并保持路径和数据格式受控。"""
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _read_metadata(path: Path) -> dict[str, object]:
    """读取元数据，并处理缺失或异常情况。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _now() -> str:
    """生成当前 UTC 时间字符串，供状态和日志落盘使用。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _mutex_path(metadata_path: Path) -> Path:
    """执行作业、锁中的内部辅助逻辑：mutex路径。"""
    return metadata_path.with_name(f"{metadata_path.name}.mutex")
