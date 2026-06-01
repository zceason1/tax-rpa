from typing import Any

from tax_rpa.utils import normalize_text


class UiaDriver:
    def invoke_text(
        self,
        hwnd: int,
        text: str,
        artifact_name: str | None = None,
    ) -> dict[str, Any] | None:
        element = self._find_text_element(hwnd, text)
        if element is None:
            return None
        action = self._try_invoke(element)
        if action is None:
            return None
        return {
            "source": "uia",
            "action": action,
            "label": text,
            "artifact_name": artifact_name,
            "hwnd": hwnd,
        }

    def focus_text(
        self,
        hwnd: int,
        text: str,
        artifact_name: str | None = None,
    ) -> dict[str, Any] | None:
        element = self._find_text_element(hwnd, text)
        if element is None:
            return None
        try:
            element.set_focus()
        except Exception:
            return None
        return {
            "source": "uia",
            "action": "focus",
            "label": text,
            "artifact_name": artifact_name,
            "hwnd": hwnd,
        }

    def _find_text_element(self, hwnd: int, text: str) -> Any | None:
        try:
            from pywinauto import Desktop

            window = Desktop(backend="uia").window(handle=hwnd)
            if not window.exists(timeout=1):
                return None
            elements = [window, *window.descendants()]
        except Exception:
            return None

        for element in elements:
            if _element_matches_text(element, text):
                return element
        return None

    def _try_invoke(self, element: Any) -> str | None:
        for action in ("invoke", "select"):
            method = getattr(element, action, None)
            if not callable(method):
                continue
            try:
                method()
            except Exception:
                continue
            return action
        return None


def _element_matches_text(element: Any, target: str) -> bool:
    target_text = normalize_text(target)
    if not target_text:
        return False
    for candidate in _element_texts(element):
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        if normalized == target_text or target_text in normalized:
            return True
        if normalized in target_text and len(normalized) >= max(3, int(len(target_text) * 0.75)):
            return True
    return False


def _element_texts(element: Any) -> list[str]:
    values: list[str] = []
    for getter_name in ("window_text",):
        getter = getattr(element, getter_name, None)
        if callable(getter):
            try:
                values.append(str(getter()))
            except Exception:
                pass

    info = getattr(element, "element_info", None)
    if info is not None:
        for attr_name in ("name", "automation_id", "class_name"):
            try:
                value = getattr(info, attr_name, None)
            except Exception:
                value = None
            if value:
                values.append(str(value))
    return values
