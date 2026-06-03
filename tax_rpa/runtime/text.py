from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """规范化文本，去除空白差异以便 OCR 匹配。"""
    return "".join(str(text).split())


def text_matches(text: str, target: str) -> bool:
    """判断识别文本是否命中目标文本。"""
    candidate = normalize_text(text)
    normalized_target = normalize_text(target)
    if not candidate or not normalized_target:
        return False
    if normalized_target in candidate or candidate in normalized_target:
        return True
    return SequenceMatcher(None, candidate, normalized_target).ratio() >= 0.62
