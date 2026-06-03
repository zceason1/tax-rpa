# 当前项目地图

本项目是 Windows 桌面税务客户端 RPA。代码通过 Python 控制税务客户端窗口，完成导入、更新、计算、导出等业务步骤，并由 Job 层提供生产运行治理。

## 当前分层

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

## 目录职责

| 目录 | 职责 |
| --- | --- |
| `tax_rpa/cli` | 命令行入口。解析参数、加载配置、触发 workflow。 |
| `tax_rpa/config` | 配置模型、路径校验和静态安全校验。 |
| `tax_rpa/runtime` | 运行时上下文、结果模型、`ActionPolicy`、`ActionGuard`、`StepRunner`、`WorkflowRuntimeOptions`、结果矩阵、共享文本/对话框目标。 |
| `tax_rpa/app` | 税务客户端生命周期、登录能力和主界面入口。 |
| `tax_rpa/testing` | self-check 和 fake-driver 测试使用的假客户端、假页面对象。 |
| `tax_rpa/drivers` | Win32、OCR、UIA、鼠标、区域推断、等待、日志等底层能力。 |
| `tax_rpa/pages/shared/components` | 跨页面复用 UI 组件，例如 toolbar、file dialog、left nav、message dialog。 |
| `tax_rpa/pages/<page>` | 页面对象、页面元素、页面专属组件和业务步骤。 |
| `tax_rpa/workflows` | 业务流程编排，只组合 app lifecycle 和 page steps。 |
| `tax_rpa/jobs` | Job 运行、manifest、状态、锁、preflight、审计、观测、回调、生产门禁。 |
| `tests` | 单元测试和 fake-driver 测试。 |
| `scripts` | Windows 提权任务和计划任务脚本。 |
| `artifacts` | 运行产物、截图、OCR 结果、summary 和失败包。 |

顶层 `tax_rpa/components` 已移除。当前只有两类 component 目录：

- `tax_rpa/pages/shared/components`：跨页面共享组件。
- `tax_rpa/pages/<page>/components`：页面专属组件。

## 主运行链路

```text
tax_rpa.cli.run_tax_workflow
  -> CombinedTaxWorkflow.run()
  -> AppLifecycleWorkflow.run()
  -> business workflow.run_on_app()
  -> Open*PageStep
  -> Business Step
  -> Page capability
  -> Shared/Page Component
  -> Driver
```

Job 化运行链路：

```text
JobManifest JSON
  -> JobRunner.run()
  -> PreflightValidator
  -> UiRunnerLock
  -> ExistingWorkflowExecutor
  -> CombinedTaxWorkflow
  -> JobStepRunner / WorkflowRuntimeOptions / ActionPolicy
  -> JobObservability / StateStore / CallbackOutbox
```

`Job` 不是页面自动化层。它不直接操作 page/component，也不决定页面步骤顺序。Job 只把生产运行需要的上下文适配给 workflow。

## 如何追踪一段功能

以“人员信息导入”为例：

1. 从 `tax_rpa/workflows/import_person_info_workflow.py` 看业务顺序。
2. 到 `tax_rpa/pages/person_info/steps/import_person_file.py` 看单步动作。
3. 到 `tax_rpa/pages/person_info/page.py` 看页面能力。
4. 到 `tax_rpa/pages/person_info/components` 或 `tax_rpa/pages/shared/components` 看组件能力。
5. 到 `tax_rpa/drivers` 看 OCR、Win32、鼠标等底层细节。

## 当前边界规则

- `workflows` 可以 import `app`、`config`、`runtime` 和 `pages.<page>.steps`。
- `workflows` 不可以 import `tax_rpa.jobs`。
- `pages` 和 `components` 可以使用 `runtime.action_policy`，但不可以 import `tax_rpa.jobs`。
- `steps` 调用 page methods 并返回 `StepResult`，不直接调用 drivers。
- `Page` 暴露页面能力，不编排完整业务流程。
- `tax_rpa/workflows/job_context.py` 已移除；Job 步骤观测在 `tax_rpa/jobs/workflow_step_runner.py`。
- `tax_rpa/workflows/result_matrix.py` 已移到 `tax_rpa/runtime/result_matrix.py`。
- `tax_rpa/constants.py` 和 `tax_rpa/utils.py` 已移除；目标文案放在 page elements 或 `runtime.dialog_targets`，文本工具放在 `runtime.text`。

完整文件归类和调用链见 [../architecture_file_map.md](../architecture_file_map.md)。
