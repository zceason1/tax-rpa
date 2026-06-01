from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.jobs.action_policy import ActionPolicy
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
        action_policy: ActionPolicy | None = None,
    ) -> None:
        self.content_rect = content_rect
        self.logger = logger
        self.min_score = min_score
        self.dry_run = dry_run
        self.ocr = ocr or OcrDriver()
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def click_text(
        self,
        text: str,
        *,
        action_type: str = "data_change",
        permit: Any | None = None,
    ) -> StepResult:
        decision = self.action_policy.before_click(
            text,
            {"step_name": "content_text.click_text"},
            action_type=action_type,
            permit=permit,
        )
        if not decision.allowed:
            return decision.to_step_result("content_text.click_text")
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
