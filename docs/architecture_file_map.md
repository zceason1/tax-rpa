# 架构文件地图

本文档描述当前代码，而不是历史迁移计划。阅读主线是：

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

`Job` 是生产运行外壳，负责 manifest、preflight、锁、状态、产物、观测、回调和生产门禁。`Workflow` 才负责业务顺序。`Page / Component / Driver` 才负责 UI 自动化动作。

三个边界例外需要明确：

- `tax_rpa/runtime` 是跨 workflow/job/page 共享的运行时契约层，不是纯工具包；因此可以包含 `result_matrix`、`workflow_options` 这类业务运行契约。
- `tax_rpa/cli/debug_person_info_page.py` 是调试入口，可以直接组合 Page 和 Step；正常生产入口仍然走 workflow。
- Page 可以为了 ready check、页面识别和默认组件构造使用 driver；Step 不直接 import driver。

## 放置规则

| 类型 | 放置位置 | 说明 |
| --- | --- | --- |
| 命令入口 | `tax_rpa/cli` | 解析参数、加载配置、启动 workflow 或工具动作。 |
| 生产任务治理 | `tax_rpa/jobs` | JobRunner、manifest、state、artifact、callback、retention、canary、production gate。 |
| 业务流程编排 | `tax_rpa/workflows` | 串联业务步骤，不直接操作 Win32/OCR。 |
| 页面步骤 | `tax_rpa/pages/<page>/steps` | 单个可命名业务动作，调用 page capability。 |
| 页面对象 | `tax_rpa/pages/<page>/page.py` | 暴露页面能力，组合组件、元素和 driver。 |
| 页面元素 | `tax_rpa/pages/<page>/elements` | UI 文案、页面标记、结果识别规则、目标对象。 |
| 页面专属组件 | `tax_rpa/pages/<page>/components` | 只服务当前页面的可复用 UI 片段。 |
| 跨页面组件 | `tax_rpa/pages/shared/components` | toolbar、left nav、file dialog、message dialog、content text 等共享 UI 操作。 |
| 跨页面元素 | `tax_rpa/pages/shared/elements` | 共享目标对象、对话框目标出口。 |
| 底层驱动 | `tax_rpa/drivers` | Win32、OCR、UIA、鼠标、区域推断、等待、运行日志。 |
| 运行时基础 | `tax_rpa/runtime` | StepResult、WorkflowResult、ActionPolicy、ActionGuard、StepRunner、WorkflowOptions、文本和结果矩阵。 |
| 配置 | `tax_rpa/config` | 配置模型、配置文件读取、Excel/app 路径校验。 |
| 客户端应用外壳 | `tax_rpa/app` | 启动/登录/主界面入口和页面入口聚合。 |

当前没有顶层 `tax_rpa/components`。保留的 component 目录只有两类：`pages/shared/components` 和 `pages/<page>/components`。这不是重复分层，而是“跨页面共享组件”和“页面专属组件”的边界。

## 关键追踪路径

人员信息导入：

```text
tax_rpa.cli.run_tax_workflow
  -> CombinedTaxWorkflow
  -> ImportPersonInfoWorkflow
  -> OpenPersonInfoPageStep
  -> ImportPersonFileStep
  -> WaitImportResultStep
  -> SubmitImportDataStep
  -> PersonInfoPage
  -> pages/person_info/components + pages/shared/components
  -> pages/person_info/elements + drivers
```

人员导入调试路径：

```text
tax_rpa.cli.debug_person_info_page
  -> PersonInfoPage
  -> ImportPersonFileStep / WaitImportResultStep / SubmitImportDataStep
```

薪资收入导入：

```text
tax_rpa.cli.import_salary_income
  -> ImportSalaryIncomeWorkflow
  -> OpenComprehensiveIncomePageStep
  -> OpenSalaryIncomeFormStep
  -> ImportSalaryIncomeDataStep
  -> ComprehensiveIncomePage
  -> pages/comprehensive_income/components/import_result.py
  -> pages/comprehensive_income/elements/*
  -> shared components + drivers
```

专项附加扣除更新：

```text
tax_rpa.cli.update_special_deduction
  -> UpdateSpecialDeductionWorkflow
  -> OpenSpecialDeductionPageStep
  -> DownloadUpdateAllPersonsStep
  -> SpecialDeductionPage
  -> pages/special_deduction/elements/*
  -> shared components + drivers
```

预填、税款计算、申报就绪、导出：

```text
ExistingWorkflowExecutor(include_phase5=True)
  -> PrefillDeductionWorkflow
  -> TaxCalculationWorkflow
  -> DeclarationSubmissionWorkflow
  -> ExportReportWorkflow
  -> pages/comprehensive_income/steps/*
  -> ComprehensiveIncomePage
```

Job 生产运行：

```text
JobManifest JSON
  -> JobRunner
  -> PreflightValidator
  -> UiRunnerLock
  -> ExistingWorkflowExecutor
  -> WorkflowRuntimeOptions + ActionPolicy + JobStepRunner
  -> CombinedTaxWorkflow
  -> JobObservability / StateStore / CallbackOutbox / ArtifactManifestWriter
```

结果和观测：

```text
Page/Step returns StepResult
  -> Workflow decides stop/continue
  -> JobStepRunner calls runtime.result_matrix.classify_step_result()
  -> JobObservability writes logs/steps.jsonl and logs/step_journal.jsonl
  -> JobRunner writes summary.json and artifact_manifest.json
```

## 文件归类

### `tax_rpa/app`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | app 包入口。 |
| `login.py` | 登录能力，使用 OCR/UIA 识别登录方式。 |
| `main_shell.py` | 主界面页面入口，打开人员信息、综合所得、专项扣除页面。 |
| `tax_client_app.py` | 税务客户端生命周期、启动决策、主窗口绑定、上下文创建。 |

### `tax_rpa/cli`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | CLI 包入口。 |
| `cleanup_artifacts.py` | 产物留存清理入口。 |
| `debug_person_info_page.py` | 人员信息页面调试入口，直接组合 page steps。 |
| `execution_mode.py` | CLI 执行模式辅助。 |
| `from_zero_import_person_info.py` | 从启动客户端到人员导入的旧自检/入口能力。 |
| `import_salary_income.py` | 薪资收入导入入口。 |
| `run_tax_workflow.py` | 综合 workflow 入口和 self-check 入口。 |
| `update_special_deduction.py` | 专项附加扣除更新入口。 |

### `tax_rpa/config`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 配置类型导出。 |
| `person_import.py` | `PersonImportConfig`、导入文件配置、登录配置、Excel/app 路径校验、JSON 配置读取。 |

### `tax_rpa/runtime`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | runtime 包说明。 |
| `action_guard.py` | 本地 UI 动作标签安全守卫，阻止高风险文案误点。 |
| `action_policy.py` | 运行模式动作授权、审计日志、拒绝结果。 |
| `context.py` | RPA 运行上下文：窗口、配置、logger、action policy。 |
| `dialog_targets.py` | 文件对话框标题和按钮文案等跨层共享目标。 |
| `result.py` | `StepResult` 和 `WorkflowResult`。 |
| `result_matrix.py` | Job 观测需要的步骤结果矩阵分类。 |
| `step_runner.py` | workflow 可注入的步骤执行接口和直接执行器。 |
| `text.py` | 文本归一化和模糊匹配。 |
| `workflow_options.py` | workflow 运行选项，如 run mode、是否允许跳过个人养老金。 |

### `tax_rpa/drivers`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | drivers 包入口。 |
| `logger.py` | 旧版运行日志、截图、JSON 输出工具；保留在 drivers 中是历史适配，Job 级观测看 `jobs/observability.py`。 |
| `mouse_driver.py` | 鼠标点击和屏幕尺寸封装。 |
| `ocr_driver.py` | OCR 截图、文字识别、目标匹配、OCR 点击。 |
| `region_driver.py` | 左侧导航区域等 UI 区域推断。 |
| `uia_driver.py` | UI Automation 文本/控件辅助。 |
| `wait_driver.py` | 等待和轮询辅助。 |
| `win32_driver.py` | Win32 窗口枚举、主窗口定位、文件对话框、按钮查找、进程启动/终止。 |

### `tax_rpa/pages/shared`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | shared 包入口。 |
| `dialogs.py` | 页面级对话框 mixin，组合 message dialog。 |
| `components/content_text.py` | 跨页面文本点击/读取组件。 |
| `components/file_dialog.py` | 文件对话框填充和提交组件。 |
| `components/left_nav.py` | 左侧导航组件。 |
| `components/message_dialog.py` | 阻塞弹窗识别和关闭组件。 |
| `components/toolbar.py` | 工具栏按钮点击组件。 |
| `components/__init__.py` | 共享组件导出。 |
| `elements/dialogs.py` | 对话框目标的页面元素出口。 |
| `elements/targets.py` | `TextTarget` 共享目标模型。 |
| `elements/__init__.py` | 共享元素导出。 |

### `tax_rpa/pages/person_info`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 人员信息页面导出。 |
| `page.py` | 人员信息页面能力：打开页面、点击导入、选择导入方式、选择文件、提交数据、读取结果。 |
| `components/import_dropdown.py` | 人员信息导入下拉选项组件。 |
| `components/import_result.py` | 人员信息导入结果读取组件。 |
| `components/__init__.py` | 页面专属组件导出。 |
| `elements/import_menu.py` | 导入按钮、导入选项、提交按钮目标。 |
| `elements/import_result.py` | 人员导入结果文本分类。 |
| `elements/page_markers.py` | 人员信息页面可见标记。 |
| `elements/targets.py` | 人员信息页面目标模型出口。 |
| `elements/__init__.py` | 页面元素导出。 |
| `steps/open_page.py` | 打开人员信息页面步骤。 |
| `steps/import_person_file.py` | 人员导入文件选择步骤。 |
| `steps/wait_import_result.py` | 等待并识别人员导入结果步骤。 |
| `steps/submit_import_data.py` | 提交人员导入数据步骤。 |
| `steps/__init__.py` | 页面步骤导出。 |

### `tax_rpa/pages/comprehensive_income`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 综合所得页面导出。 |
| `page.py` | 综合所得页面能力：打开页面、打开工资薪金、导入薪资、预填扣除、计算税款、检查申报就绪、导出报告。 |
| `components/import_result.py` | 综合所得导入结果读取组件。 |
| `elements/declaration_submission.py` | 申报发送页面和发送按钮目标。 |
| `elements/export_report.py` | 导出申报表相关目标。 |
| `elements/import_menu.py` | 综合所得导入按钮和选项目标。 |
| `elements/import_result.py` | 薪资导入结果分类。 |
| `elements/page_markers.py` | 综合所得页面标记。 |
| `elements/prefill_deduction.py` | 预填扣除相关目标。 |
| `elements/salary_income.py` | 工资薪金表单目标。 |
| `elements/tax_calculation.py` | 税款计算相关目标。 |
| `elements/__init__.py` | 综合所得元素导出。 |
| `steps/open_page.py` | 打开综合所得页面步骤。 |
| `steps/open_salary_income_form.py` | 打开工资薪金表单步骤。 |
| `steps/import_salary_income_data.py` | 导入薪资数据步骤。 |
| `steps/prefill_deduction.py` | 预填扣除步骤。 |
| `steps/tax_calculation.py` | 税款计算步骤。 |
| `steps/declaration_submission_readiness.py` | 申报就绪检查步骤，不发送申报。 |
| `steps/export_declaration_report.py` | 导出申报表步骤。 |
| `steps/__init__.py` | 综合所得步骤导出。 |

### `tax_rpa/pages/special_deduction`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 专项附加扣除页面导出。 |
| `page.py` | 专项附加扣除页面能力：打开页面、下载更新全部人员。 |
| `elements/download_update.py` | 下载更新按钮/结果目标。 |
| `elements/page_markers.py` | 专项附加扣除页面标记。 |
| `elements/__init__.py` | 专项附加扣除元素导出。 |
| `steps/open_page.py` | 打开专项附加扣除页面步骤。 |
| `steps/download_update_all_persons.py` | 下载更新全部人员步骤。 |
| `steps/__init__.py` | 专项附加扣除步骤导出。 |

### `tax_rpa/workflows`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | 常用 workflow 导出。 |
| `app_lifecycle_workflow.py` | 客户端启动、登录、主窗口准备。 |
| `combined_tax_workflow.py` | 组合完整税务业务链，处理失败恢复和 action policy 注入。 |
| `import_person_info_workflow.py` | 人员信息导入业务顺序。 |
| `import_salary_income_workflow.py` | 薪资收入导入业务顺序。 |
| `update_special_deduction_workflow.py` | 专项附加扣除更新业务顺序。 |
| `prefill_deduction_workflow.py` | 预填专项扣除业务顺序。 |
| `tax_calculation_workflow.py` | 税款计算业务顺序。 |
| `declaration_submission_workflow.py` | 申报发送前就绪检查业务顺序。 |
| `export_report_workflow.py` | 申报表导出业务顺序。 |
| `recovery_policy.py` | 组合 workflow 失败后是否可重启恢复的判断。 |

### `tax_rpa/jobs`

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | job 基础类型导出；不导出会引起循环依赖的 executor。 |
| `artifact_manifest.py` | 产物清单写入。 |
| `artifact_store.py` | job 产物目录和路径管理。 |
| `calibration.py` | 实机校准门禁。 |
| `callback_outbox.py` | 回调发送、待重试、死信和签名。 |
| `canary.py` | canary 运行记录和维护票据。 |
| `existing_workflow_executor.py` | Job 到现有 workflow 的适配器。 |
| `lock.py` | UI runner 跨进程锁。 |
| `machine_config.py` | 部署机器配置校验。 |
| `manifest.py` | JobManifest 加载和校验。 |
| `observability.py` | job 级日志、截图、OCR JSON、排障索引。 |
| `preflight.py` | manifest 文件和环境前置检查。 |
| `production_gate.py` | 生产提交门禁。 |
| `redaction.py` | 敏感字段脱敏。 |
| `retention.py` | 产物留存清理。 |
| `runner.py` | JobRunner 主流程。 |
| `runtime_metadata.py` | 运行时版本、用户、分辨率、DPI 等 metadata。 |
| `state_store.py` | job 状态机和状态文件。 |
| `submit_authorization.py` | 提交授权聚合门禁和一次性 permit。 |
| `workflow_step_runner.py` | job 级 step journal、steps 日志和 result matrix 记录。 |

## 已移除的旧路径

以下路径不再作为当前架构入口：

| 旧路径 | 当前位置 |
| --- | --- |
| `tax_rpa/components/*` | `tax_rpa/pages/shared/components/*` 或 `tax_rpa/pages/<page>/components/*` |
| `tax_rpa/constants.py` | 页面元素模块、`runtime.dialog_targets` |
| `tax_rpa/utils.py` | `tax_rpa/runtime/text.py` |
| `tax_rpa/pages/person_info_page.py` | `tax_rpa/pages/person_info/page.py` |
| `tax_rpa/jobs/action_policy.py` | `tax_rpa/runtime/action_policy.py` |
| `tax_rpa/workflows/job_context.py` | `tax_rpa/runtime/step_runner.py`、`tax_rpa/jobs/workflow_step_runner.py` |
| `tax_rpa/workflows/result_matrix.py` | `tax_rpa/runtime/result_matrix.py` |

`docs/superpowers/plans/*` 是历史执行计划，可能包含当时的旧路径示例。判断当前架构时以本文档、`docs/learning/01-project-map.md` 和代码树为准。

## 新增代码放置检查

新增一个业务动作时按这个顺序落文件：

1. UI 文案或结果识别：先放 `pages/<page>/elements`。
2. 可复用 UI 操作：跨页面放 `pages/shared/components`，页面专属放 `pages/<page>/components`。
3. 页面能力：放 `pages/<page>/page.py`，只暴露能力，不编排完整业务流。
4. 单个业务步骤：放 `pages/<page>/steps`，返回 `StepResult`。
5. 业务顺序：放 `workflows`。
6. 生产运行、manifest、回调、状态、观测、门禁：放 `jobs`。
7. 多层共用且不属于业务页面的运行时模型或纯函数：放 `runtime`。
8. Win32/OCR/鼠标/UIA 细节：放 `drivers`。
