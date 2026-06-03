# RPA 组件架构

组件层封装可复用 UI 操作，让 Page 和 Step 读起来像业务动作，而不是底层窗口脚本。

当前主链路：

```text
Workflow -> Step -> Page -> Component -> Element / Driver
```

`CLI / Job` 位于链路外侧，负责启动和生产运行治理。

## 组件目录

| 目录 | 用途 |
| --- | --- |
| `tax_rpa/pages/shared/components` | 跨页面复用组件。 |
| `tax_rpa/pages/<page>/components` | 页面专属组件。 |

顶层 `tax_rpa/components` 已移除，不再作为兼容包保留。

当前跨页面组件包括：

- `ContentTextComponent`
- `FileDialogComponent`
- `LeftNavComponent`
- `MessageDialogComponent`
- `ToolbarComponent`

页面专属组件示例：

- `tax_rpa/pages/person_info/components/import_dropdown.py`
- `tax_rpa/pages/person_info/components/import_result.py`

## Component 的边界

Component 应该：

- 封装通用 UI 操作。
- 使用 driver 实例执行底层动作。
- 使用 elements 或传入文本定位目标。
- 返回结构化 `StepResult`。
- 使用 `runtime.action_policy.ActionPolicy` 做动作许可。

Component 不应该：

- 编排完整业务流程。
- import `tax_rpa.jobs`。
- 读取 `JobManifest`。
- 决定 workflow 顺序。

## Page 与 Component 的关系

Page 创建或持有组件，并暴露页面能力：

```python
class PersonInfoPage:
    def click_import_button(self) -> StepResult:
        return self.default_toolbar().click_button(IMPORT_BUTTON.text)

    def choose_import_file_option(self) -> StepResult:
        return self.default_import_dropdown().choose_item(import_option)

    def choose_person_file(self, path: Path, dropdown_result: StepResult) -> StepResult | None:
        return self.file_dialog.choose_file(path)
```

Page 不再提供 `import_person_file()` 这种完整流程方法。完整导入流程由 workflow 或 debug CLI 组合 steps。

## ActionPolicy 位置

`ActionPolicy` 属于 runtime：

```python
from tax_rpa.runtime.action_policy import ActionPolicy
```

Page 和 Component 不要 import `tax_rpa.jobs.action_policy`。

当前完整文件归类和调用链见 `docs/architecture_file_map.md`。
