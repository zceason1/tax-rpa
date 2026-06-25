from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.comprehensive_income.steps.import_salary_income_data import (
    ImportSalaryIncomeDataStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_salary_income_form import (
    OpenSalaryIncomeFormStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class ImportSalaryIncomeWorkflow(BusinessWorkflow):
    """导入工资薪金收入工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "import_salary_income_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Any | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
    ) -> None:
        """初始化导入工资薪金收入工作流实例，保存依赖、配置和运行上下文。"""
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
        steps = []
        open_form = self.context.step(
            "comprehensive_income.open_salary_income_form",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self.context.failed_from_step(
                open_form,
                steps=steps,
                evidence={"open_form": open_form.evidence},
            )

        import_file = self.context.step(
            "comprehensive_income.import_salary_income_data",
            lambda: ImportSalaryIncomeDataStep(page).run(
                self.config.import_file("salary_income")
            ),
            matrix_step="salary_income_import",
            side_effect_step=True,
        )
        steps.append(import_file)

        return self.context.result_from_step(
            import_file,
            steps=steps,
            evidence={
                "open_form": open_form.evidence,
                "import_file": import_file.evidence,
            },
        )
