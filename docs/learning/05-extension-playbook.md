# 功能扩展手册

这份手册用于新增一个税务客户端 RPA 流程。默认遵守当前分层：

```text
CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver
```

## 扩展前先判断类型

| 新需求 | 推荐起点 |
| --- | --- |
| 新增按钮、文本或结果识别 | `pages/<page>/elements` |
| 新增页面内点击、输入、选择文件能力 | `Page` 或 `Component` |
| 新增一个业务动作 | `pages/<page>/steps` |
| 新增完整业务流程 | `workflows` |
| 新增 manifest 字段 | `jobs/manifest.py`，再通过 `WorkflowRuntimeOptions` 传给 workflow |
| 新增动作安全限制 | `runtime/action_policy.py` |
| 新增生产门禁 | `jobs/production_gate.py` |
| 新增排障信息 | `jobs/observability.py` |

## 标准步骤

### 1. 定义元素

在对应页面目录下新增或修改 `elements` 文件。

```python
from tax_rpa.pages.shared.elements.targets import TextTarget

REPORT_EXPORT_BUTTON = TextTarget(
    text="导出",
    screenshot_name="report_export_button",
)
```

元素层只描述“找什么”，不执行动作。

### 2. 增加页面能力

在 `page.py` 中添加语义化方法。

```python
def open_report_export_menu(self) -> StepResult:
    return self._content_text().click_text(REPORT_EXPORT_BUTTON.text)
```

页面方法应该像业务语言，不应该暴露坐标。

### 3. 增加 Step

在 `pages/<page>/steps` 下新增 step。

```python
class ExportReportStep:
    def __init__(self, page: "ComprehensiveIncomePage") -> None:
        self.page = page

    def run(self) -> StepResult:
        open_menu = self.page.open_report_export_menu()
        if not open_menu.ok:
            return open_menu
        return self.page.read_export_result()
```

Step 负责返回清晰的成功、失败、未知结果和 side-effect 状态。

### 4. 增加 Workflow

Workflow 只编排业务顺序：

```python
page = OpenComprehensiveIncomePageStep(app.shell()).run()
export_result = ExportReportStep(page).run()
```

不要在 workflow 里写 OCR、鼠标点击、窗口枚举或固定坐标。

### 5. 接入 StepRunner

如果这个 workflow 会被 JobRunner 调用，构造函数应接受 `step_runner` 和 `runtime_options`。

```python
from collections.abc import Callable

from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


class YourWorkflow:
    def __init__(
        self,
        config,
        logger,
        *,
        step_runner=None,
        runtime_options: WorkflowRuntimeOptions | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.step_runner = step_runner
        self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)

    def _run_step(self, step: str, operation: Callable[[], StepResult]) -> StepResult:
        if self.step_runner is None:
            return operation()
        return self.step_runner.run_step(
            workflow="your_workflow",
            step=step,
            operation=operation,
        )
```

新代码只使用 `step_runner` 和 `runtime_options`。workflow 不可以 import `tax_rpa.workflows.job_context`，也不可以读取 `JobManifest` 字段。

Manifest 派生出来的业务选项应放进 `WorkflowRuntimeOptions`，例如：

```python
if self.runtime_options.allow_skip_personal_pension:
    ...
```

### 6. 写测试

至少覆盖：

- 成功路径。
- 文件、页面或弹窗缺失。
- OCR 未识别。
- 结果未知。
- `inspect_only` 下拒绝副作用动作。
- 高风险动作没有 permit 时拒绝。
- 架构边界：workflow 不 import jobs，page 不 import steps，steps 不 import drivers。

优先使用 fake page / fake driver。不要一开始就依赖真实客户端。

## 文件导入流程提示

文件导入通常有副作用，应更谨慎：

1. 定义导入按钮和菜单项。
2. 复用 `ToolbarComponent`、`ContentTextComponent`、`FileDialogComponent`。
3. 在 step 结果中标记 `side_effect_started=True`。
4. 失败后默认 `retry_allowed=False`，除非能证明没有副作用。
5. Job 层使用 `ActionPolicy` 拦截 `inspect_only`。
6. 增加 result matrix 分类。

## 常见错误

| 错误做法 | 问题 |
| --- | --- |
| 在 workflow 里直接调用 `OcrDriver.click_text()` | 难测试、难复用、难排障。 |
| 在 step 里写固定坐标 | 分辨率和窗口变化后容易失败。 |
| 在 Page 里 import 并编排 steps | Page 会变成第二个 workflow，职责混乱。 |
| workflow 读取 `JobManifest` | workflow 变成 Job 专属，无法独立测试。 |
| 新共享组件放在顶层 `tax_rpa/components` | 会恢复旧的双 components 结构；该目录已移除。 |
| 真实提交只靠 `--submit` 控制 | 缺少生产门禁和审计。 |
