import dataclasses
from pathlib import Path
from typing import Any


SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "authorization",
    "cookie",
)


def redact_sensitive(value: Any, key: str | None = None) -> Any:
    """递归脱敏敏感字段，避免密码和令牌进入日志。"""
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if dataclasses.is_dataclass(value):
        return redact_sensitive(dataclasses.asdict(value), key=key)
    if isinstance(value, dict):
        return {
            str(item_key): redact_sensitive(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _is_sensitive_key(key: str) -> bool:
    """判断字段名是否属于敏感信息。"""
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
