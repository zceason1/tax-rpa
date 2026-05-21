from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab

from tax_rpa.config.person_import import assert_safe_action
from tax_rpa.drivers.mouse_driver import MouseDriver
from tax_rpa.utils import normalize_text, text_matches


def load_ocr_engine():
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
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return round(sum(xs) / len(xs)), round(sum(ys) / len(ys))


def ocr_match_priority(text: str, target: str) -> tuple[int, float, int]:
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
    matches = []
    for row in rows:
        box = row.get("box")
        if not box or float(row.get("score", 0)) < min_score:
            continue
        if not box_in_image(box, image_size):
            continue
        if text_matches(str(row.get("text", "")), target):
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


def ocr_rect(rect: list[int], name: str, logger: Any) -> tuple[list[dict[str, Any]], tuple[int, int], str]:
    image_path = logger.out_dir / f"{name}.png"
    ImageGrab.grab(bbox=tuple(rect)).save(image_path)
    image_size = Image.open(image_path).size
    engine = load_ocr_engine()
    rows = iter_ocr_rows(engine(str(image_path)))
    logger.write_json(f"{name}_ocr_rows.json", rows)
    return rows, image_size, str(image_path.resolve())

class OcrDriver:
    def __init__(self, mouse: MouseDriver | None = None) -> None:
        self.mouse = mouse or MouseDriver()

    def find_text(
        self,
        rect: list[int],
        text: str,
        logger: Any,
        min_score: float,
        artifact_name: str,
    ) -> dict[str, Any] | None:
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
        assert_safe_action(text)
        rows, image_size, image_path = ocr_rect(rect, artifact_name, logger)
        match = find_best_ocr_match(rows, text, image_size, min_score)
        if match is None:
            raise RuntimeError(f"OCR did not find text '{text}' in {image_path}")

        offset_x, offset_y = box_center(match["box"])
        x = rect[0] + offset_x
        y = rect[1] + offset_y
        result = {
            "label": text,
            "match": match,
            "click": [x, y],
            "screenshot": image_path,
            "dry_run": dry_run,
        }
        logger.log("ocr_click", "dry_run" if dry_run else "click", **result)
        if not dry_run:
            result["click_result"] = self.mouse.click([x, y])
            logger.log("ocr_click_result", "done", label=text, click_result=result["click_result"])
        return result
