# 税务 RPA 项目学习目录

这个目录用于把当前项目拆成可学习、可练习、可扩展的路径。目标不是只看懂代码，而是让你能独立新增一个税务客户端 RPA 流程。

## 学习顺序

1. 先读 [../architecture_file_map.md](../architecture_file_map.md)，建立当前文件归类和调用路径地图。
2. 再读 [learning_plan.md](learning_plan.md)，了解阶段目标。
3. 再读 [01-project-map.md](01-project-map.md)，建立项目全局地图。
4. 读 [02-architecture-walkthrough.md](02-architecture-walkthrough.md)，理解分层和代码放置规则。
4. 读 [03-windows-rpa-drivers.md](03-windows-rpa-drivers.md)，掌握 Windows 自动化、OCR、坐标和点击。
5. 读 [04-job-safety-observability.md](04-job-safety-observability.md)，理解任务运行、安全门禁和排障产物。
6. 按 [05-extension-playbook.md](05-extension-playbook.md) 学习如何新增功能。
7. 用 [06-practice-labs.md](06-practice-labs.md) 做练习。

## 你最终要掌握什么

- 能从 CLI 入口追踪到具体业务步骤。
- 能判断某段代码应该放在 `drivers`、`components`、`pages`、`steps`、`workflows` 还是 `jobs`。
- 能读懂 `StepResult` 和 `WorkflowResult`，并用它们判断流程是否可以继续。
- 能用 fake page / fake driver 写测试，不依赖真实税务客户端验证业务编排。
- 能新增页面、步骤、流程、结果识别、运行门禁和排障日志。
- 能识别高风险动作，不绕过 `ActionPolicy` 和生产门禁。

## 常用验证命令

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.debug_person_info_page inspect --config .\config\person_import.json --timeout 20
```

## 学习时的核心规则

- 先看测试，再看实现。
- 先理解返回值，再理解内部细节。
- 先用 fake-driver 验证，再碰真实客户端。
- UI 文本变化优先改 `elements`。
- 操作方式变化优先改 `components` 或 `drivers`。
- 业务顺序变化才改 `workflows`。
- 生产运行、安全授权、回调、产物归档相关逻辑放在 `jobs`。
