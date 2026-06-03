from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult


class AppLifecycleWorkflow:
    """客户端生命周期工作流工作流，负责编排该业务链路的页面步骤和失败结果。"""
    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        reset: bool = False,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
    ) -> None:
        """初始化客户端生命周期工作流实例，保存依赖、配置和运行上下文。"""
        self.config = config
        self.logger = logger
        self.reset = reset
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))
        self.app: Any | None = None

    def run(self) -> WorkflowResult:
        """执行当前步骤或工作流的主流程，并返回标准结果。"""
        steps: list[StepResult] = []
        app = self.app_factory(self.config, self.logger)
        self.app = app

        if self.reset:
            reset_result = app.reset()
            steps.append(reset_result)
            if not reset_result.ok:
                return self._failed(reset_result, steps)

        start = app.start_if_needed()
        steps.append(start)
        if not start.ok:
            return self._failed(start, steps)

        login = app.wait_for_login()
        steps.append(login)
        if not login.ok:
            return self._failed(login, steps)

        return WorkflowResult(
            ok=True,
            name="app_lifecycle_workflow",
            status=login.status,
            steps=steps,
            evidence={"login": login.evidence},
        )

    def _failed(self, result: StepResult, steps: list[StepResult]) -> WorkflowResult:
        """把失败步骤包装成上层失败结果，并保留已执行步骤证据。"""
        return WorkflowResult(
            ok=False,
            name="app_lifecycle_workflow",
            status=result.status,
            steps=steps,
            evidence=result.evidence,
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=result.side_effect_started,
            side_effect_committed=result.side_effect_committed,
            retry_allowed=result.retry_allowed,
        )
