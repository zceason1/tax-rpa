from typing import Any

from tax_rpa.runtime.result import StepResult


class ExportDeclarationReportStep:
    def __init__(self, page: Any, *, run_mode: str) -> None:
        self.page = page
        self.run_mode = run_mode

    def run(self) -> StepResult:
        with self.page.step("open_export_report_menu"):
            menu_result = self.page.open_export_report_menu()
        if not menu_result.ok:
            return self._failed(menu_result, side_effect_started=False)

        if self.run_mode == "inspect_only":
            return StepResult(
                ok=True,
                name="comprehensive_income.export_report",
                status="export_entry_visible",
                evidence={
                    "menu": menu_result,
                    "export_status": "entry_visible_only",
                    "run_mode": self.run_mode,
                },
                side_effect_started=False,
                side_effect_committed=False,
                evidence_paths=menu_result.evidence_paths,
                ui_text=menu_result.ui_text,
            )

        with self.page.step("choose_standard_report_option"):
            standard_result = self.page.choose_standard_report_option()
        if not standard_result.ok:
            return self._failed(
                standard_result,
                side_effect_started=True,
                menu_result=menu_result,
            )

        with self.page.step("read_export_result"):
            result = self.page.read_export_result(run_mode=self.run_mode)
        if not result.ok:
            return self._failed(
                result,
                side_effect_started=True,
                menu_result=menu_result,
                standard_result=standard_result,
            )

        export_status = result.evidence.get("export_status", result.status)
        return StepResult(
            ok=True,
            name="comprehensive_income.export_report",
            status=result.status,
            evidence={
                "menu": menu_result,
                "standard": standard_result,
                "result": result,
                "export_status": export_status,
                "run_mode": self.run_mode,
                **result.evidence,
            },
            side_effect_started=True,
            side_effect_committed=result.status != "not_available_before_submit",
            evidence_paths=result.evidence_paths,
            ui_text=result.ui_text,
        )

    def _failed(
        self,
        result: StepResult,
        *,
        side_effect_started: bool,
        **evidence: StepResult,
    ) -> StepResult:
        return StepResult(
            ok=False,
            name="comprehensive_income.export_report",
            status=result.status,
            evidence={**evidence, "result": result, "run_mode": self.run_mode},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
            evidence_paths=result.evidence_paths,
            ui_text=result.ui_text,
        )
