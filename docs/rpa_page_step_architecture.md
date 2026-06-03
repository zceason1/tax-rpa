# RPA Page / Step 架构设计

## 目标

Page / Step 架构的目标是让代码结构贴近真实业务路径，同时保持测试和排障清晰：

```text
Workflow -> Step -> Page -> Component -> Element / Driver
```

其中 `CLI / Job` 是运行入口和生产治理层，不是页面自动化层。

## 分层职责

| 层 | 职责 |
| --- | --- |
| `Workflow` | 编排业务步骤顺序。 |
| `Step` | 表示一个用户能理解的业务动作。 |
| `Page` | 表示一个业务页面，提供页面能力。 |
| `Component` | 封装可复用 UI 操作。 |
| `Element` | 保存识别目标和规则。 |
| `Driver` | 执行 Win32、OCR、鼠标、等待等底层动作。 |

## Page 的边界

Page 应该暴露页面能力，例如：

```python
class PersonInfoPage:
    def click_import_button(self) -> StepResult:
        ...

    def choose_import_file_option(self) -> StepResult:
        ...

    def choose_person_file(self, path: Path, dropdown_result: StepResult) -> StepResult | None:
        ...

    def read_import_result(self) -> StepResult:
        ...
```

Page 不应该：

- import `tax_rpa.pages.<page>.steps`
- 编排完整业务流程
- 决定 workflow 顺序
- 直接散落 OCR、坐标、窗口枚举等底层细节

如果一个方法内部已经包含多个业务动作，例如“关闭弹窗 -> 点击导入 -> 选择菜单 -> 选择文件 -> 等待结果”，应拆到 `steps/` 和 `workflows/`。

## Step 的边界

Step 表示一个可复用业务动作：

```python
class ImportPersonFileStep:
    def __init__(self, page: PersonInfoPage) -> None:
        self.page = page

    def run(self, file_path: Path) -> StepResult:
        ...
```

Step 可以调用 Page methods，并返回 `StepResult`。Step 不直接调用 drivers。

## Workflow 的边界

Workflow 只编排业务顺序：

```python
page = OpenPersonInfoPageStep(app.shell()).run()
import_file = ImportPersonFileStep(page).run(config.person_info_file)
validation_result = WaitImportResultStep(page).run()
if validation_result.status == "ready_to_submit":
    submit_result = SubmitImportDataStep(page).run()
    import_result = WaitImportResultStep(page).run()
```

Workflow 不应该直接出现：

- OCR 匹配
- 鼠标点击
- 窗口枚举
- 固定坐标
- 文件对话框控件细节
- 弹窗 class name
- `tax_rpa.jobs` import

## 人员导入当前拆分

```text
pages/person_info/
  page.py
  elements/
    page_markers.py
    import_menu.py
    import_result.py
  components/
    import_dropdown.py
    import_result.py
  steps/
    open_page.py
    import_person_file.py
    wait_import_result.py
    submit_import_data.py
```

当前人员导入流程：

```text
ImportPersonInfoWorkflow
  -> OpenPersonInfoPageStep
  -> ImportPersonFileStep
  -> WaitImportResultStep
  -> SubmitImportDataStep
  -> WaitImportResultStep
```

`PersonInfoPage.import_person_file()` 已删除。生产 workflow 和 debug CLI 都应显式组合 steps。

## Import 方向规则

```text
drivers
  不 import pages/components/steps/workflows

elements
  不 import drivers/workflows

components
  可以 import drivers/elements/runtime/config

page
  可以 import shared components/page components/elements
  不 import page steps

steps
  可以 import runtime 和 page typing
  不 import drivers

workflows
  可以 import app/config/runtime/steps
  不 import jobs/drivers/elements
```

这些规则由 `tests/test_architecture_boundaries.py` 和 `tests/test_page_step_architecture.py` 覆盖。

## 测试策略

优先覆盖架构边界和行为边界：

- Step 是否按正确顺序调用 Page。
- Workflow 是否只编排 Steps。
- Page 是否不 import Steps。
- Workflow 是否不 import Jobs。
- 未知结果是否返回稳定 `status`、`error_type`、`error_code`。
- 副作用开始后是否禁止自动重试。

使用 fake page / fake app 做单元测试，避免每次都依赖真实客户端。
