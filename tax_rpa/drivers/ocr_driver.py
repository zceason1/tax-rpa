from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab

from tax_rpa.drivers.mouse_driver import GetSystemMetrics, MouseDriver, SM_CXSCREEN, SM_CYSCREEN
from tax_rpa.runtime.action_guard import assert_safe_action
from tax_rpa.runtime.text import normalize_text, text_matches


def load_ocr_engine():
    """加载OCR识别engine，并转换为当前模块使用的数据对象。"""
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception:
        try:
            from rapidocr import RapidOCR

            return RapidOCR()
        except Exception as exc:
            raise RuntimeError(
                "未安装可用 OCR，请先安装 rapidocr-onnxruntime 或 rapidocr"
            ) from exc


def iter_ocr_rows(raw_result):
    """执行底层驱动、OCR识别驱动中的iterOCR识别rows逻辑，供业务流程或相邻模块调用。"""
    if isinstance(raw_result, tuple):
        raw_result = raw_result[0]
    if raw_result is None:
        return []

    rows = []
    for item in raw_result:
        try:
            box, text, score = item[0], str(item[1]), float(item[2])
            rows.append({"box": box, "text": text, "score": score})
        except Exception:
            pass
    return rows


def box_in_image(box: list[list[float]], image_size: tuple[int, int], tolerance: int = 4) -> bool:
    """执行底层驱动、OCR识别驱动中的boxinimage逻辑，供业务流程或相邻模块调用。"""
    width, height = image_size
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return (
        min(xs) >= -tolerance
        and min(ys) >= -tolerance
        and max(xs) <= width + tolerance
        and max(ys) <= height + tolerance
    )


def box_center(box: list[list[float]]) -> tuple[int, int]:
    """执行底层驱动、OCR识别驱动中的boxcenter逻辑，供业务流程或相邻模块调用。"""
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return round(sum(xs) / len(xs)), round(sum(ys) / len(ys))


def get_mouse_screen_size() -> tuple[int, int]:
    """执行底层驱动、OCR识别驱动中的get鼠标屏幕size逻辑，供业务流程或相邻模块调用。"""
    return GetSystemMetrics(SM_CXSCREEN), GetSystemMetrics(SM_CYSCREEN)


def _scale_axis(value: int | float, scale: float) -> int:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：scaleaxis。"""
    return round(float(value) * scale)


def _unscale_axis(value: int | float, scale: float) -> int:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：unscaleaxis。"""
    if scale <= 0:
        return round(float(value))
    return round(float(value) / scale)


def _coordinate_transform(full_image_size: tuple[int, int]) -> dict[str, Any]:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：coordinatetransform。"""
    mouse_width, mouse_height = get_mouse_screen_size()
    image_width, image_height = full_image_size
    scale_x = image_width / mouse_width if mouse_width > 0 else 1.0
    scale_y = image_height / mouse_height if mouse_height > 0 else 1.0
    return {
        "mouse_screen_size": [mouse_width, mouse_height],
        "image_screen_size": [image_width, image_height],
        "scale": [scale_x, scale_y],
    }


def _image_rect_from_mouse_rect(rect: list[int], transform: dict[str, Any]) -> list[int]:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：image矩形区域从零启动鼠标矩形区域。"""
    scale_x, scale_y = transform["scale"]
    return [
        _scale_axis(rect[0], scale_x),
        _scale_axis(rect[1], scale_y),
        _scale_axis(rect[2], scale_x),
        _scale_axis(rect[3], scale_y),
    ]


def _mouse_point_from_image_point(point: list[int], transform: dict[str, Any]) -> list[int]:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：鼠标point从零启动imagepoint。"""
    scale_x, scale_y = transform["scale"]
    return [
        _unscale_axis(point[0], scale_x),
        _unscale_axis(point[1], scale_y),
    ]


def _capture_ocr_image(rect: list[int], name: str, logger: Any) -> tuple[str, tuple[int, int], dict[str, Any]]:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：captureOCR识别image。"""
    image_path = logger.out_dir / f"{name}.png"
    full_image = ImageGrab.grab()
    transform = _coordinate_transform(full_image.size)
    image_rect = _image_rect_from_mouse_rect(rect, transform)
    cropped = full_image.crop(tuple(image_rect))
    cropped.save(image_path)
    return (
        str(image_path.resolve()),
        cropped.size,
        {
            **transform,
            "mouse_rect": rect,
            "image_rect": image_rect,
        },
    )


def ocr_match_priority(text: str, target: str) -> tuple[int, float, int]:
    """执行底层驱动、OCR识别驱动中的OCR识别matchpriority逻辑，供业务流程或相邻模块调用。"""
    candidate = normalize_text(text)
    normalized_target = normalize_text(target)
    if candidate == normalized_target:
        return (4, 1.0, len(candidate))
    if normalized_target in candidate:
        return (3, len(normalized_target) / max(len(candidate), 1), len(candidate))
    if candidate in normalized_target:
        return (2, len(candidate) / max(len(normalized_target), 1), len(candidate))
    if "人员" in candidate and "采集" in candidate:
        return (1, 0.8, len(candidate))
    return (0, SequenceMatcher(None, candidate, normalized_target).ratio(), len(candidate))


def find_best_ocr_match(
    rows: list[dict[str, Any]],
    target: str,
    image_size: tuple[int, int],
    min_score: float,
) -> dict[str, Any] | None:
    """查找bestOCR识别match，找到时返回匹配对象或证据。"""
    matches = []
    for row in rows:
        box = row.get("box")
        if not box or float(row.get("score", 0)) < min_score:
            continue
        if not box_in_image(box, image_size):
            continue
        if _ocr_text_matches(str(row.get("text", "")), target):
            matches.append(row)

    if not matches:
        return None
    return sorted(
        matches,
        key=lambda item: (
            ocr_match_priority(str(item.get("text", "")), target),
            float(item.get("score", 0)),
        ),
        reverse=True,
    )[0]


def _ocr_text_matches(text: str, target: str) -> bool:
    """执行底层驱动、OCR识别驱动中的内部辅助逻辑：OCR识别文本matches。"""
    candidate = normalize_text(text)
    normalized_target = normalize_text(target)
    if not candidate or not normalized_target:
        return False
    if candidate == normalized_target:
        return True
    if normalized_target in candidate:
        return True
    if candidate in normalized_target:
        return len(candidate) >= max(3, int(len(normalized_target) * 0.75))
    if len(candidate) < max(3, int(len(normalized_target) * 0.75)):
        return False
    return text_matches(candidate, normalized_target)


def ocr_rect(rect: list[int], name: str, logger: Any) -> tuple[list[dict[str, Any]], tuple[int, int], str]:
    """执行底层驱动、OCR识别驱动中的OCR识别矩形区域逻辑，供业务流程或相邻模块调用。"""
    image_path, image_size, _transform = _capture_ocr_image(rect, name, logger)
    engine = load_ocr_engine()
    rows = iter_ocr_rows(engine(str(image_path)))
    logger.write_json(f"{name}_ocr_rows.json", rows)
    return rows, image_size, image_path


def ocr_rect_with_coordinates(
    rect: list[int],
    name: str,
    logger: Any,
) -> tuple[list[dict[str, Any]], tuple[int, int], str, dict[str, Any]]:
    """执行底层驱动、OCR识别驱动中的OCR识别矩形区域withcoordinates逻辑，供业务流程或相邻模块调用。"""
    image_path, image_size, transform = _capture_ocr_image(rect, name, logger)
    engine = load_ocr_engine()
    rows = iter_ocr_rows(engine(str(image_path)))
    logger.write_json(f"{name}_ocr_rows.json", rows)
    return rows, image_size, image_path, transform

class OcrDriver:
    """OCR识别驱动驱动，封装底层系统能力，供页面组件调用。"""
    def __init__(self, mouse: MouseDriver | None = None) -> None:
        """初始化OCR识别驱动实例，保存依赖、配置和运行上下文。"""
        self.mouse = mouse or MouseDriver()

    def find_text(
        self,
        rect: list[int],
        text: str,
        logger: Any,
        min_score: float,
        artifact_name: str,
    ) -> dict[str, Any] | None:
        """查找文本，找到时返回匹配对象或证据。"""
        rows, image_size, image_path = ocr_rect(rect, artifact_name, logger)
        match = find_best_ocr_match(rows, text, image_size, min_score)
        if match is not None:
            match = {**match, "screenshot": image_path}
        return match

    def click_text(
        self,
        rect: list[int],
        text: str,
        logger: Any,
        min_score: float,
        dry_run: bool,
        artifact_name: str,
    ) -> dict[str, Any]:
        """在指定内容区域通过 OCR 文本定位并点击目标。"""
        assert_safe_action(text)
        rows, image_size, image_path, transform = ocr_rect_with_coordinates(rect, artifact_name, logger)
        match = find_best_ocr_match(rows, text, image_size, min_score)
        if match is None:
            raise RuntimeError(f"OCR did not find text '{text}' in {image_path}")

        offset_x, offset_y = box_center(match["box"])
        image_x = transform["image_rect"][0] + offset_x
        image_y = transform["image_rect"][1] + offset_y
        x, y = _mouse_point_from_image_point([image_x, image_y], transform)
        result = {
            "label": text,
            "match": match,
            "click": [x, y],
            "image_click": [image_x, image_y],
            "screenshot": image_path,
            "dry_run": dry_run,
            "coordinate_transform": transform,
        }
        logger.log("ocr_click", "dry_run" if dry_run else "click", **result)
        if not dry_run:
            result["click_result"] = self.mouse.click([x, y])
            logger.log("ocr_click_result", "done", label=text, click_result=result["click_result"])
        return result
