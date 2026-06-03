from typing import Any

from tax_rpa.runtime.result import StepResult


class DeclarationSubmissionReadinessStep:
    """申报报送就绪检查步骤步骤，封装该页面动作的执行入口。"""
    def __init__(self, page: Any, *, run_mode: str) -> None:
        """初始化申报报送就绪检查步骤实例，保存依赖、配置和运行上下文。"""
        self.page = page
        self.run_mode = run_mode

    def run(self) -> StepResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        with self.page.step("open_declaration_submission_page"):
            open_result = self.page.open_declaration_submission_page()
        if not open_result.ok:
            return self._failed(open_result)

        with self.page.step("locate_send_declaration_button"):
            send_button = self.page.locate_send_declaration_button()
        if not send_button.ok:
            return self._failed(send_button, open_result=open_result)

        return StepResult(
            ok=True,
            name="comprehensive_income.declaration_submission_readiness",
            status="ready_to_submit_not_sent",
            evidence={
                "open": open_result,
                "send_button": send_button,
                "run_mode": self.run_mode,
                **send_button.evidence,
            },
            side_effect_started=False,
            side_effect_committed=False,
            evidence_paths=send_button.evidence_paths,
            ui_text=send_button.ui_text,
        )

    def _failed(self, result: StepResult, **evidence: StepResult) -> StepResult:
        """把失败步骤包装成上层失败结果，并保留已执行步骤证据。"""
        return StepResult(
            ok=False,
            name="comprehensive_income.declaration_submission_readiness",
            status=result.status,
            evidence={**evidence, "result": result, "run_mode": self.run_mode},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=False,
            side_effect_committed=False,
            retry_allowed=result.retry_allowed,
            evidence_paths=result.evidence_paths,
            ui_text=result.ui_text,
        )
