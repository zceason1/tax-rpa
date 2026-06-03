from tax_rpa.runtime.text import normalize_text


RESULT_TEXTS = {
    "success": (
        "导入成功",
        "导入完成",
        "成功导入",
        "共导入",
        "信息已全部提交成功",
    ),
    "failed": (
        "失败",
        "错误",
        "异常",
        "不能为空",
        "不符合",
        "重复",
        "校验未通过",
    ),
}
READY_TO_SUBMIT_TEXTS = (
    "信息正确",
    "提交数据",
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
