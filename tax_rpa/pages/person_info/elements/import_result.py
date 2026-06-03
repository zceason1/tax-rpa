from tax_rpa.runtime.text import normalize_text


RESULT_TEXTS = {
    "success": (
        "\u5bfc\u5165\u6210\u529f",
        "\u5bfc\u5165\u5b8c\u6210",
        "\u6210\u529f\u5bfc\u5165",
        "\u5171\u5bfc\u5165",
        "\u4fe1\u606f\u5df2\u5168\u90e8\u63d0\u4ea4\u6210\u529f",
    ),
    "failed": (
        "\u5931\u8d25",
        "\u9519\u8bef",
        "\u5f02\u5e38",
        "\u4e0d\u80fd\u4e3a\u7a7a",
        "\u4e0d\u7b26\u5408",
        "\u91cd\u590d",
        "\u6821\u9a8c\u672a\u901a\u8fc7",
    ),
}
READY_TO_SUBMIT_TEXTS = (
    "\u4fe1\u606f\u6b63\u786e",
    "\u63d0\u4ea4\u6570\u636e",
)


def classify_import_result(texts: list[str]) -> str:
    """根据人员信息导入反馈文本分类导入结果。"""
    joined = normalize_text(" ".join(texts))
    if any(keyword in joined for keyword in RESULT_TEXTS["success"]):
        return "success"
    if all(keyword in joined for keyword in READY_TO_SUBMIT_TEXTS):
        return "ready_to_submit"
    if any(keyword in joined for keyword in RESULT_TEXTS["failed"]):
        return "failed"
    return "unknown"
