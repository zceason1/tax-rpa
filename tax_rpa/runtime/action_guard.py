from tax_rpa.runtime.text import normalize_text


class UnsafeActionError(ValueError):
    """不安全动作错误异常，表示运行时、动作保护中的特定错误场景。"""


ALLOWED_ACTION_LABELS = {
    "申报密码登录",
    "综合所得申报",
}
FORBIDDEN_ACTION_KEYWORDS = (
    "报送",
    "发送申报",
    "申报",
    "缴款",
    "缴纳",
    "税款缴纳",
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
