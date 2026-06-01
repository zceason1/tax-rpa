from typing import Any

from tax_rpa.runtime.result import StepResult


class DeclarationSubmissionReadinessStep:
    def __init__(self, page: Any, *, run_mode: str) -> None:
        self.page = page
        self.run_mode = run_mode

    def run(self) -> StepResult:
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
