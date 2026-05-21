from tax_rpa.utils import normalize_text


RESULT_TEXTS = {
    "success": ("导入成功", "导入完成", "成功导入", "共导入"),
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


def classify_import_result(texts: list[str]) -> str:
    joined = normalize_text(" ".join(texts))
    if any(keyword in joined for keyword in RESULT_TEXTS["failed"]):
        return "failed"
    if any(keyword in joined for keyword in RESULT_TEXTS["success"]):
        return "success"
    return "unknown"

