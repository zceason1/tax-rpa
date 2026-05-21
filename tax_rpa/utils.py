from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    return "".join(str(text).split())


def text_matches(text: str, target: str) -> bool:
    candidate = normalize_text(text)
    normalized_target = normalize_text(target)
    if not candidate or not normalized_target:
        return False
    if normalized_target in candidate or candidate in normalized_target:
        return True
    return SequenceMatcher(None, candidate, normalized_target).ratio() >= 0.62
