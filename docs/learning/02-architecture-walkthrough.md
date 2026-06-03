# 架构导读

当前项目采用分层 RPA 架构。每一层只处理自己的问题，避免业务流程、页面语义和底层自动化细节混在一起。

## 分层模型

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

## 各层职责

| 层 | 应该做什么 | 不应该做什么 |
| --- | --- | --- |
| `cli` | 参数、配置、入口、提权。 | 维护业务步骤细节。 |
| `jobs` | 生产任务治理：manifest、preflight、锁、状态、产物、回调、审计。 | 写页面点击细节，或被 workflow 直接依赖。 |
| `workflows` | 编排多个业务步骤的顺序。 | 直接写坐标、OCR、窗口枚举，或 import `tax_rpa.jobs`。 |
| `steps` | 表示一个用户能理解的业务动作。 | 决定完整 workflow 顺序，或直接调用 drivers。 |
| `page` | 表示一个业务页面，暴露页面级能力。 | 编排完整业务流程，或 import `pages/*/steps`。 |
| `components` | 封装可复用 UI 操作，例如工具栏点击、文件选择、弹窗关闭。 | 编排完整业务流程。 |
| `elements` | 保存页面识别目标，例如按钮文字、页面标识、结果文本。 | 执行点击或等待。 |
| `drivers` | 操作系统、窗口、OCR、鼠标、键盘、截图、等待。 | 写税务业务逻辑。 |

边界例外：

- `runtime` 是跨层共享的运行时契约层，可以包含 `result_matrix` 和 `workflow_options` 这类业务运行契约，不是纯通用工具目录。
- debug CLI 可以直接组合 Page 和 Step，用于排查单页问题；生产入口仍应走 workflow。
- Page 可以为了 ready check、页面识别和默认组件构造使用 driver；Step 不直接 import driver。

## Job 的位置

`Job` 不是页面自动化层的一部分。它负责生产运行治理，包括：

- `JobManifest`
- preflight
- UI 运行锁
- 状态存储
- 运行产物
- callback outbox
- 审计和观测

业务顺序仍由 `Workflow` 编排。页面动作仍由 `Step -> Page -> Component -> Driver` 执行。

Job 层通过三类显式运行时输入适配 workflow：

- `JobStepRunner`：记录 step start/result、result matrix 和 side-effect marker。
- `WorkflowRuntimeOptions`：传递 manifest 派生出来的业务运行选项，例如 `run_mode`、`allow_skip_personal_pension`。
- `ActionPolicy`：运行时动作许可模型，位于 `tax_rpa/runtime/action_policy.py`。

## 人员信息导入示例

当前人员导入流程由 workflow 和 debug CLI 显式组合 steps：

```text
ImportPersonInfoWorkflow
  -> OpenPersonInfoPageStep
  -> ImportPersonFileStep
  -> WaitImportResultStep
  -> SubmitImportDataStep
  -> WaitImportResultStep
```

`PersonInfoPage` 只提供能力：

```python
page.click_import_button()
page.choose_import_file_option()
page.choose_person_file(path, dropdown_result)
page.click_submit_data()
page.read_import_result()
```

`PersonInfoPage.import_person_file()` 已删除。不要在 Page 里 import 或编排 steps。

## 判断代码应该放哪里

| 问题 | 放置位置 |
| --- | --- |
| 这是识别哪个按钮、标题或文本？ | `elements` |
| 这是怎么点击、输入或选择文件？ | `components` 或 `drivers` |
| 这是一个页面能做的能力？ | `page` |
| 这是一个业务动作，例如导入文件、等待结果、提交数据？ | `steps` |
| 这是多个业务动作的顺序？ | `workflows` |
| 这是生产运行、任务状态、失败包或回调？ | `jobs` |
| 这是命令行参数和启动方式？ | `cli` |

## 扩展默认路径

新增功能时按这个顺序推进：

```text
elements
  -> page/component
  -> step
  -> workflow
  -> tests
  -> job executor/result matrix
  -> calibration/canary
```

不要在 workflow 里直接调用 `OcrDriver.click_text()`。那会让流程难测试、难排障，也更难适配客户端 UI 变化。
