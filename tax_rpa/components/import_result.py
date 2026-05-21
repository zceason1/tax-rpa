from tax_rpa.utils import normalize_text


def classify_import_result(texts: list[str]) -> str:
    joined = normalize_text(" ".join(texts))
    failure_keywords = (
        "失败",
        "错误",
        "异常",
        "不能为空",
        "不符合",
        "重复",
        "校验未通过",
    )
    success_keywords = ("导入成功", "导入完成", "成功导入", "共导入")

    if any(keyword in joined for keyword in failure_keywords):
        return "failed"
    if any(keyword in joined for keyword in success_keywords):
        return "success"
    return "unknown"
