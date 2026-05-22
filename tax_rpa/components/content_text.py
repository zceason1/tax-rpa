from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.runtime.result import StepResult
from tax_rpa.utils import normalize_text


class ContentTextComponent:
    def __init__(
        self,
        content_rect: list[int],
        logger: Any,
        min_score: float,
        dry_run: bool,
        ocr: OcrDriver | None = None,
    ) -> None:
        self.content_rect = content_rect
        self.logger = logger
        self.min_score = min_score
        self.dry_run = dry_run
        self.ocr = ocr or OcrDriver()

    def click_text(self, text: str) -> StepResult:
        click = self.ocr.click_text(
            self.content_rect,
            text,
            self.logger,
            self.min_score,
            self.dry_run,
            f"content_{normalize_text(text)}",
        )
        return StepResult(
            ok=True,
            name="content_text.click_text",
            status="clicked",
            evidence={"click": click},
        )
