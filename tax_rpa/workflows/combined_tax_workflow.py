from collections.abc import Callable
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.recovery_policy import can_retry_after_failure


BusinessWorkflowFactory = Callable[..., Any]


class CombinedTaxWorkflow:
    """组合税务工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        workflow_factories: list[BusinessWorkflowFactory],
        reset: bool = False,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        name: str = "combined_tax_workflow",
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: Any | None = None,
        action_policy: Any | None = None,
    ) -> None:
        """初始化组合税务工作流实例，保存依赖、配置和运行上下文。"""
        self.config = config
        self.logger = logger
        self.workflow_factories = workflow_factories
        self.reset = reset
        self.app_factory = app_factory
        self.name = name
        self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
        self.step_runner = step_runner
        self.action_policy = action_policy

    def run(self) -> WorkflowResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        self._attach_action_policy(lifecycle.app)
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name=self.name,
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                evidence={"lifecycle": lifecycle_result.evidence},
                error=lifecycle_result.error,
                error_type=lifecycle_result.error_type,
                error_code=lifecycle_result.error_code,
                side_effect_started=lifecycle_result.side_effect_started,
                side_effect_committed=lifecycle_result.side_effect_committed,
                retry_allowed=lifecycle_result.retry_allowed,
            )

        business_results: list[WorkflowResult] = []
        for factory in self.workflow_factories:
            workflow = self._build_business_workflow(factory)
            result = workflow.run_on_app(lifecycle.app)
            if not result.ok and can_retry_after_failure(result):
                recovered = self._reset_and_wait_for_login()
                if recovered.ok:
                    self._attach_action_policy(recovered.evidence["app"])
                    workflow = self._build_business_workflow(factory)
                    result = workflow.run_on_app(recovered.evidence["app"])
            business_results.append(result)
            if not result.ok:
                return WorkflowResult(
                    ok=False,
                    name=self.name,
                    status=result.status,
                    steps=lifecycle_result.steps,
                    evidence={
                        "lifecycle": lifecycle_result.evidence,
                        "business_results": business_results,
                    },
                    error=result.error,
                    error_type=result.error_type,
                    error_code=result.error_code,
                    side_effect_started=result.side_effect_started,
                    side_effect_committed=result.side_effect_committed,
                    retry_allowed=result.retry_allowed,
                )

        status = business_results[-1].status if business_results else lifecycle_result.status
        return WorkflowResult(
            ok=True,
            name=self.name,
            status=status,
            steps=lifecycle_result.steps,
            evidence={
                "lifecycle": lifecycle_result.evidence,
                "business_results": business_results,
            },
        )

    def _reset_and_wait_for_login(self) -> WorkflowResult:
        """执行工作流、组合税务工作流中的内部辅助逻辑：resetand等待for登录。"""
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=True,
            app_factory=self.app_factory,
        )
        result = lifecycle.run()
        self._attach_action_policy(lifecycle.app)
        if not result.ok:
            return result
        return WorkflowResult(
            ok=True,
            name=result.name,
            status=result.status,
            steps=result.steps,
            evidence={**result.evidence, "app": lifecycle.app},
        )

    def _build_business_workflow(self, factory: BusinessWorkflowFactory) -> Any:
        """执行工作流、组合税务工作流中的内部辅助逻辑：build业务工作流。"""
        return factory(
            self.config,
            self.logger,
            step_runner=self.step_runner,
            runtime_options=self.runtime_options,
        )

    def _attach_action_policy(self, app: Any) -> None:
        """执行工作流、组合税务工作流中的内部辅助逻辑：attach动作策略。"""
        if self.action_policy is None:
            return
        app_context = getattr(app, "context", None)
        if app_context is None:
            return
        if hasattr(app_context, "action_policy"):
            app_context.action_policy = self.action_policy
