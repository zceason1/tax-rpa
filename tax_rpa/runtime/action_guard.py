from tax_rpa.runtime.text import normalize_text


class UnsafeActionError(ValueError):
    """不安全动作错误异常，表示运行时、动作保护中的特定错误场景。"""


ALLOWED_ACTION_LABELS = {
    "\u7533\u62a5\u5bc6\u7801\u767b\u5f55",
    "\u7efc\u5408\u6240\u5f97\u7533\u62a5",
}
FORBIDDEN_ACTION_KEYWORDS = (
    "\u62a5\u9001",
    "\u53d1\u9001\u7533\u62a5",
    "\u7533\u62a5",
    "\u7f34\u6b3e",
    "\u7f34\u7eb3",
    "\u7a0e\u6b3e\u7f34\u7eb3",
)


def assert_safe_action(label: str) -> None:
    """按本地安全规则检查 UI 动作标签是否允许。"""
    normalized = normalize_text(label)
    allowed = {normalize_text(item) for item in ALLOWED_ACTION_LABELS}
    if normalized in allowed:
        return
    for keyword in FORBIDDEN_ACTION_KEYWORDS:
        if normalize_text(keyword) in normalized:
            raise UnsafeActionError(
                f"Action is forbidden in the personnel import POC: {label}"
            )
