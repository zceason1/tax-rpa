from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.steps.open_page import OpenPersonInfoPageStep
from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class ImportPersonInfoWorkflow(BusinessWorkflow):
    """导入人员信息工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    name = "import_person_info_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Any | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        reset: bool = False,
    ) -> None:
        """初始化导入人员信息工作流实例，保存依赖、配置和运行上下文。"""
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
            reset=reset,
        )

    def execute(self, app: Any) -> WorkflowResult:
        """在已经登录的客户端应用上执行当前业务工作流。"""
        steps: list[StepResult] = []
        page = OpenPersonInfoPageStep(app.shell()).run()
        import_file = self.context.step(
            "person_info.import_person_file",
            lambda: ImportPersonFileStep(page).run(self.config.person_info_file),
            side_effect_step=True,
        )
        steps.append(import_file)
        if not import_file.ok:
            return self.context.failed_from_step(
                import_file,
                steps=steps,
                evidence={"import_file": import_file.evidence},
            )

        validation_result = self.context.step(
            "person_info.wait_import_result",
            lambda: WaitImportResultStep(page).run(),
            matrix_step="personnel_import",
        )
        steps.append(validation_result)

        if validation_result.status == "ready_to_submit":
            submit_result = self.context.step(
                "person_info.submit_import_data",
                lambda: SubmitImportDataStep(page).run(),
                side_effect_step=True,
            )
            steps.append(submit_result)
            if not submit_result.ok:
                return self.context.failed_from_step(
                    submit_result,
                    steps=steps,
                    evidence={
                        "import_file": import_file.evidence,
                        "validation_result": validation_result.evidence,
                        "submit_result": submit_result.evidence,
                    },
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            import_result = self.context.step(
                "person_info.wait_submit_result",
                lambda: WaitImportResultStep(page).run(),
                matrix_step="personnel_import",
            )
            if import_result.status == "ready_to_submit":
                import_result = StepResult(
                    ok=False,
                    name=import_result.name,
                    status="unknown",
                    evidence={
                        **import_result.evidence,
                        "post_submit_status": "ready_to_submit",
                    },
                    error="Personnel import remained at submit-data confirmation after submit",
                    error_type="UNKNOWN_RESULT",
                    error_code="person_import_result_unknown",
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            steps.append(import_result)
        else:
            import_result = validation_result

        side_effect_started = (
            import_file.ok
            or import_file.side_effect_started
            or validation_result.side_effect_started
            or import_result.side_effect_started
        )
        side_effect_committed = (
            import_file.ok
            or import_file.side_effect_committed
            or validation_result.side_effect_committed
            or import_result.side_effect_committed
        )

        evidence = {
            "import_file": import_file.evidence,
            "validation_result": validation_result.evidence,
            "import_result": import_result.evidence,
        }
        if validation_result.status == "ready_to_submit":
            evidence["submit_result"] = steps[-2].evidence

        return self.context.result_from_step(
            import_result,
            steps=steps,
            evidence=evidence,
            side_effect_started=side_effect_started,
            side_effect_committed=side_effect_committed,
            retry_allowed=False if side_effect_started else import_result.retry_allowed,
        )
