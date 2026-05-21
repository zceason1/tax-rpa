from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.runtime.result import StepResult


class ToolbarComponent:
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

    def click_button(self, text: str) -> StepResult:
        click = self.ocr.click_text(
            self.content_rect,
            text,
            self.logger,
            self.min_score,
            self.dry_run,
            f"toolbar_{text}",
        )
        return StepResult(
            ok=True,
            name="toolbar.click_button",
            status="clicked",
            evidence={"click": click},
        )
