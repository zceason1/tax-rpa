# 新页面 / Step / Workflow 代码模板

下面是结构模板，不是可以直接复制运行的完整实现。实际开发时要按当前页面和业务命名。

## elements

```python
from tax_rpa.pages.shared.elements.targets import TextTarget


PAGE_MARKER = TextTarget(
    text="页面名称",
    screenshot_name="new_page_marker",
)

ACTION_BUTTON = TextTarget(
    text="按钮名称",
    screenshot_name="new_page_action_button",
)
```

## page method

```python
from tax_rpa.runtime.result import StepResult


class NewPage:
    def is_ready(self) -> bool:
        # 使用 OCR 或窗口文本判断页面是否 ready。
        ...

    def click_action_button(self) -> StepResult:
        return self._content_text().click_text(ACTION_BUTTON.text)

    def read_action_result(self) -> StepResult:
        # 返回 success / failed / unknown。
        ...
```

## step

```python
from typing import TYPE_CHECKING

from tax_rpa.runtime.result import StepResult

if TYPE_CHECKING:
    from tax_rpa.pages.new_page.page import NewPage


class NewActionStep:
    def __init__(self, page: "NewPage") -> None:
        self.page = page

    def run(self) -> StepResult:
        with self.page.step("点击业务按钮"):
            click_result = self.page.click_action_button()
        if not click_result.ok:
            return StepResult(
                ok=False,
                name="new_page.new_action",
                status=click_result.status,
                evidence={"click": click_result},
                error=click_result.error,
                error_type=click_result.error_type,
                error_code=click_result.error_code,
            )

        with self.page.step("读取业务结果"):
            result = self.page.read_action_result()

        return StepResult(
            ok=result.ok,
            name="new_page.new_action",
            status=result.status,
            evidence={"click": click_result, "result": result},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=True,
            side_effect_committed=result.ok,
            retry_allowed=False,
        )
```

## workflow

```python
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow


class NewWorkflow(BusinessWorkflow):
    name = "new_workflow"

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        *,
        step_runner: Any | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
    ) -> None:
        self._init_workflow(
            config=config,
            logger=logger,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )

    def execute(self, app: Any) -> WorkflowResult:
        steps: list[StepResult] = []

        page = app.shell().open_new_page()
        action_result = self.context.step(
            "new_page.new_action",
            lambda: NewActionStep(page).run(),
            side_effect_step=True,
        )
        steps.append(action_result)

        return self.context.result_from_step(
            action_result,
            steps=steps,
            evidence={"action_result": action_result.evidence},
        )
```

## fake test shape

```python
import unittest

from tax_rpa.runtime.result import StepResult
from tax_rpa.pages.new_page.steps.new_action import NewActionStep


class FakePage:
    def step(self, *_args, **_kwargs):
        from contextlib import nullcontext

        return nullcontext()

    def click_action_button(self):
        return StepResult(ok=True, name="click", status="clicked")

    def read_action_result(self):
        return StepResult(ok=True, name="result", status="success")


class NewActionStepTest(unittest.TestCase):
    def test_success(self):
        result = NewActionStep(FakePage()).run()

        self.assertTrue(result.ok)
        self.assertEqual("success", result.status)


if __name__ == "__main__":
    unittest.main()
```
