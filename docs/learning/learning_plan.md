# 学习计划

这个计划按“能读懂 -> 能调试 -> 能扩展 -> 能上线治理”的顺序设计。每个阶段都绑定当前项目中的真实代码。

## 阶段 1：Python 与项目入口

目标：

- 理解 Python 包结构、模块导入、类型标注、`dataclass`。
- 能找到命令行入口和配置加载路径。
- 能运行 self-check。

重点文件：

- `tax_rpa/cli/run_tax_workflow.py`
- `tax_rpa/cli/from_zero_import_person_info.py`
- `tax_rpa/config/person_import.py`
- `tax_rpa/runtime/result.py`

完成标准：

- 能说明 `--submit`、`--reset`、`--self-check` 的作用。
- 能解释 `PersonImportConfig` 的主要字段。
- 能解释 `StepResult.ok/status/error_type/error_code` 的意义。

## 阶段 2：客户端生命周期与页面入口

目标：

- 理解税务客户端如何启动、复用、等待登录。
- 理解 `TaxClientApp -> MainShell -> Page` 的关系。

重点文件：

- `tax_rpa/app/tax_client_app.py`
- `tax_rpa/app/main_shell.py`
- `tax_rpa/pages/person_info/page.py`
- `tax_rpa/pages/comprehensive_income/page.py`

完成标准：

- 能画出“启动客户端 -> 等待登录 -> 打开页面 -> 执行业务步骤”的链路。
- 能说明 `RpaContext` 为什么保存 `main_window` 和 `action_policy`。

## 阶段 3：Windows RPA 驱动层

目标：

- 理解窗口句柄、窗口矩形、控件枚举、OCR、鼠标坐标转换。
- 理解为什么不能在业务流程里直接写坐标。

重点文件：

- `tax_rpa/drivers/win32_driver.py`
- `tax_rpa/drivers/ocr_driver.py`
- `tax_rpa/drivers/mouse_driver.py`
- `tax_rpa/drivers/uia_driver.py`
- `tax_rpa/drivers/region_driver.py`
- `tax_rpa/drivers/wait_driver.py`

完成标准：

- 能解释 `OcrDriver.click_text()` 的完整链路。
- 能解释 OCR 图片坐标和鼠标屏幕坐标为什么需要转换。
- 能说明什么时候优先用 UIA，什么时候回退 OCR。

## 阶段 4：Page、Component、Step、Workflow 分层

目标：

- 理解项目的 RPA 业务架构。
- 能判断代码应该放在哪一层。
- 能独立阅读人员导入和工资薪金导入流程。

重点文件：

- `tax_rpa/pages/person_info/elements/*`
- `tax_rpa/pages/person_info/components/*`
- `tax_rpa/pages/person_info/steps/*`
- `tax_rpa/workflows/import_person_info_workflow.py`
- `tax_rpa/workflows/import_salary_income_workflow.py`

完成标准：

- 能说明 `elements`、`components`、`page`、`steps`、`workflows` 的边界。
- 能解释人员导入流程每一步为什么返回 `StepResult`。
- 能用 fake page 测试一个 step。

## 阶段 5：Job、安全和可观测性

目标：

- 理解中台任务如何变成 RPA 执行。
- 理解运行模式、安全策略、失败包、回调、产物归档。

重点文件：

- `tax_rpa/jobs/manifest.py`
- `tax_rpa/jobs/runner.py`
- `tax_rpa/jobs/existing_workflow_executor.py`
- `tax_rpa/jobs/action_policy.py`
- `tax_rpa/jobs/observability.py`
- `tax_rpa/jobs/production_gate.py`

完成标准：

- 能说明 `inspect_only`、`execute_no_send`、`submit` 的区别。
- 能解释为什么高风险提交需要一次性 permit。
- 能从 `artifacts/jobs/<job_id>/summary.json` 和 `troubleshooting_index.json` 定位失败。

## 阶段 6：新增一个业务流程

目标：

- 选择一个小功能，从 elements 到 tests 完成闭环。
- 不绕过分层、不绕过安全、不依赖真实客户端做第一轮验证。

推荐练习：

- 新增一个页面结果识别分类器。
- 新增一个只读 readiness 检查 step。
- 新增一个 fake-driver 下可运行的新 workflow。

完成标准：

- 新增测试覆盖成功、失败、未知结果。
- self-check 或 fake-driver 流程能通过。
- 真实客户端相关动作有 calibration/canary 计划。
