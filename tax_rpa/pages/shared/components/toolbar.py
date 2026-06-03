from typing import Any

from tax_rpa.drivers.ocr_driver import OcrDriver
from tax_rpa.runtime.action_policy import ActionPolicy
from tax_rpa.runtime.result import StepResult


class ToolbarComponent:
    """共享工具栏组件，负责按文本目标点击页面工具栏按钮。"""
    def __init__(
        self,
        content_rect: list[int],
        logger: Any,
        min_score: float,
        dry_run: bool,
        ocr: OcrDriver | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        """初始化工具栏component实例，保存依赖、配置和运行上下文。"""
        self.content_rect = content_rect
        self.logger = logger
        self.min_score = min_score
        self.dry_run = dry_run
        self.ocr = ocr or OcrDriver()
        self.action_policy = action_policy or ActionPolicy(run_mode="execute_no_send")

    def click_button(
        self,
        text: str,
        *,
        action_type: str = "data_change",
        permit: Any | None = None,
    ) -> StepResult:
        """按按钮文本定位并点击工具栏按钮，返回点击证据。"""
        decision = self.action_policy.before_click(
            text,
            {"step_name": "toolbar.click_button"},
            action_type=action_type,
            permit=permit,
        )
        if not decision.allowed:
            return decision.to_step_result("toolbar.click_button")
        click = self.ocr.click_text(
            self.content_rect,
            text,
            self.logger,
            self.min_score,
            False,
            f"toolbar_{text}",
        )
        return StepResult(
            ok=True,
            name="toolbar.click_button",
            status="clicked",
            evidence={"click": click},
        )
