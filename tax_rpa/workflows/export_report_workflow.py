from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.export_declaration_report import (
    ExportDeclarationReportStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class ExportReportWorkflow(BusinessWorkflow):
    """导出报表工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "export_report_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        app_factory: Any | None = None,
    ) -> None:
        """初始化导出报表工作流实例，保存依赖、配置和运行上下文。"""
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )

    def execute(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        readiness = self.context.step(
            "comprehensive_income.declaration_submission_readiness_for_export",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            side_effect_step=False,
        )
        steps = [readiness]
        if not readiness.ok:
            return self.context.failed_from_step(
                readiness,
                steps=steps,
                evidence={"readiness": readiness.evidence},
            )

        export = self.context.step(
            "comprehensive_income.export_report",
            lambda: ExportDeclarationReportStep(
                page,
                run_mode=self._run_mode(),
            ).run(),
            matrix_step="export_report",
            side_effect_step=True,
        )
        steps.append(export)
        return self.context.result_from_step(
            export,
            steps=steps,
            evidence={
                "readiness": readiness.evidence,
                "export": export.evidence,
                "export_status": export.evidence.get("export_status"),
            },
        )

    def _run_mode(self) -> str:
        """执行工作流、导出报表工作流中的内部辅助逻辑：run模式。"""
        return self.runtime_options.run_mode
