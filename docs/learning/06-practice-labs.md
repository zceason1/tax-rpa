# 练习清单

这些练习从读代码开始，逐步过渡到新增功能。每个练习都应优先在测试或 self-check 下完成。

## Lab 1：跑通当前项目

目标：

- 确认环境可运行。
- 建立测试和 self-check 的基本手感。

命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

完成标准：

- 能说明测试数量和结果。
- 能找到 self-check 输出的 summary 路径。

## Lab 2：追踪人员导入流程

目标：

- 从 workflow 追踪到底层 component。

阅读顺序：

1. `tax_rpa/workflows/import_person_info_workflow.py`
2. `tax_rpa/pages/person_info/steps/import_person_file.py`
3. `tax_rpa/pages/person_info/page.py`
4. `tax_rpa/pages/person_info/components/import_dropdown.py`
5. `tax_rpa/pages/shared/components/file_dialog.py`
6. `tax_rpa/drivers/ocr_driver.py`

完成标准：

- 能写出人员导入的步骤链路。
- 能说明哪一步开始产生副作用。

## Lab 3：理解 StepResult

目标：

- 看懂成功、失败、未知、拒绝动作的返回差异。

任务：

- 找 5 个返回 `StepResult` 的函数。
- 记录每个函数的 `status` 可能值。
- 判断哪些 `status` 会阻止 workflow 继续。

推荐文件：

- `tax_rpa/pages/person_info/steps/wait_import_result.py`
- `tax_rpa/pages/comprehensive_income/steps/import_salary_income_data.py`
- `tax_rpa/runtime/action_policy.py`

完成标准：

- 能解释 `ok=False` 和 `status="unknown"` 的区别。

## Lab 4：写一个结果分类测试

目标：

- 学会先写测试，再改识别逻辑。

参考文件：

- `tax_rpa/pages/person_info/elements/import_result.py`
- `tax_rpa/pages/comprehensive_income/elements/import_result.py`
- `tests/test_import_person_info_helpers.py`
- `tests/test_salary_income_import_result.py`

任务：

- 找一个分类函数。
- 添加一个真实 UI 可能出现的文本样例。
- 写测试证明它能分类成功或失败。

完成标准：

- 测试失败后再修改实现。
- 修改后只跑相关测试，再跑全量测试。

## Lab 5：写一个 fake page step 测试

目标：

- 不依赖真实客户端测试业务步骤。

任务：

- 选择一个 step。
- 写一个 fake page，只实现 step 需要调用的方法。
- 验证成功路径和失败路径。

参考：

- `tests/test_comprehensive_income_steps.py`
- `tests/test_special_deduction_steps.py`

完成标准：

- 测试不启动客户端。
- 测试不移动真实鼠标。

## Lab 6：新增只读 readiness step

目标：

- 新增一个低风险页面检查。

建议实现：

- 在 `elements` 定义目标文本。
- 在 `page.py` 添加读取或定位方法。
- 在 `steps` 添加 `ReadinessStep`。
- 用 fake page 写测试。

完成标准：

- `inspect_only` 下可以运行。
- 不触发文件提交或数据变更。

## Lab 7：模拟 ActionPolicy 拒绝

目标：

- 理解运行模式和安全边界。

任务：

- 创建 `ActionPolicy(run_mode="inspect_only")`。
- 调用一个数据变更动作。
- 验证返回 `ACTION_DENIED`。

参考：

- `tests/test_action_policy.py`
- `tests/test_action_policy_components.py`

完成标准：

- 能说明为什么 `inspect_only` 不能导入文件。

## Lab 8：阅读失败包

目标：

- 学会从 artifact 排障。

任务：

- 找一个失败或 self-check 产物目录。
- 打开 `summary.json`。
- 打开 `troubleshooting_index.json`。
- 找到最后一个 step、最后一个 action、最后一个 OCR 记录。

完成标准：

- 能从产物判断失败发生在哪个 workflow 和 step。

## Lab 9：设计一个新流程

目标：

- 把学习结果变成可执行设计。

输出：

- 用 [templates/new_flow_checklist.md](templates/new_flow_checklist.md) 填一份新流程设计。
- 用 [templates/new_page_step_workflow_template.md](templates/new_page_step_workflow_template.md) 起草代码结构。

完成标准：

- 设计里包含 elements、page、step、workflow、tests、safety、observability。
- 明确哪些部分必须真实客户端 calibration。
