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
    def __init__(self, active_job_id: str | None, metadata: dict[str, object]) -> None:
        super().__init__(f"UI runner is busy with job: {active_job_id or 'unknown'}")
        self.active_job_id = active_job_id
        self.metadata = metadata


@dataclass(frozen=True)
class UiRunnerLock:
    lock_path: Path = Path("artifacts/runner.lock.json")

    _local_locks: ClassVar[dict[Path, dict[str, object]]] = {}

    def acquire(self, job_id: str) -> "UiRunnerLockLease":
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
    lock_file_path: Path
    metadata_path: Path
    stream: BinaryIO
    metadata: dict[str, object]
    released: bool = False

    def heartbeat(self) -> None:
        if self.released:
            return
        self.metadata["heartbeat_at"] = _now()
        _write_metadata(self.metadata_path, self.metadata)

    def release(self) -> None:
        if self.released:
            return
        try:
            _unlock_stream(self.stream)
        finally:
            self.stream.close()
            UiRunnerLock._local_locks.pop(self.lock_file_path, None)
            self.released = True

    def __enter__(self) -> "UiRunnerLockLease":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


def _build_metadata(job_id: str) -> dict[str, object]:
    now = _now()
    return {
        "job_id": job_id,
        "process_id": os.getpid(),
        "windows_user": getpass.getuser(),
        "acquired_at": now,
        "heartbeat_at": now,
    }


def _active_job_id(metadata: dict[str, object]) -> str | None:
    job_id = metadata.get("job_id")
    return str(job_id) if job_id else None


def _lock_stream(stream: BinaryIO) -> None:
    if msvcrt is None:
        return
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)


def _unlock_stream(stream: BinaryIO) -> None:
    if msvcrt is None:
        return
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _write_metadata(path: Path, metadata: dict[str, object]) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _read_metadata(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _mutex_path(metadata_path: Path) -> Path:
    return metadata_path.with_name(f"{metadata_path.name}.mutex")
