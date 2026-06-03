from tax_rpa.runtime.text import normalize_text


RESULT_TEXTS = {
    "success": (
        "导入成功",
        "导入完成",
        "成功导入",
        "工资薪金导入成功",
        "瀵煎叆鎴愬姛",
        "瀵煎叆瀹屾垚",
        "鎴愬姛瀵煎叆",
    ),
    "failed": (
        "导入失败",
        "失败",
        "错误",
        "异常",
        "格式错误",
        "校验未通过",
        "瀵煎叆澶辫触",
        "澶辫触",
        "閿欒",
        "寮傚父",
        "鏍煎紡閿欒",
        "鏍￠獙鏈€氳繃",
    ),
}


def classify_salary_income_import_result(texts: list[str]) -> str:
    """根据工资薪金导入反馈文本分类导入结果。"""
    joined = normalize_text(" ".join(texts))
    if any(keyword in joined for keyword in RESULT_TEXTS["failed"]):
        return "failed"
    if any(keyword in joined for keyword in RESULT_TEXTS["success"]):
        return "success"
    return "unknown"
