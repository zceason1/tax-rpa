# Job、安全与可观测性

这个项目不只是本地脚本。它已经有生产任务运行层，用来保证输入可校验、动作可审计、失败可排查、高风险提交可拦截。

## JobManifest

文件：`tax_rpa/jobs/manifest.py`

作用：

- 描述一次任务。
- 校验公司、税期、运行模式、输入文件。
- 记录文件 SHA-256，避免处理错文件或半传输文件。

核心字段：

- `job_id`
- `idempotency_key`
- `company_name`
- `credit_code`
- `tax_period`
- `run_mode`
- `submit_enabled`
- `files.person_info`
- `files.salary_income`

## JobRunner

文件：`tax_rpa/jobs/runner.py`

作用：

```text
加载 manifest
  -> 初始化 artifact 目录
  -> 写 state
  -> preflight 校验
  -> 获取 UI runner 锁
  -> 执行 workflow executor
  -> 写 summary
  -> 写 troubleshooting index
  -> 尝试 callback
  -> 写 artifact manifest
```

新增生产流程时，不能只接 CLI。需要考虑是否也要接入 `JobRunner`。

## 运行模式

| 模式 | 含义 |
|------|------|
| `inspect_only` | 只检查，不允许数据变更和文件提交。 |
| `execute_no_send` | 允许准备动作和导入动作，但禁止高风险发送申报。 |
| `submit` | 允许真实提交，但必须通过生产门禁和一次性 permit。 |

## ActionPolicy

文件：`tax_rpa/jobs/action_policy.py`

作用：

- 在点击、文件提交、弹窗确认前判断动作是否允许。
- 根据运行模式拒绝危险动作。
- 对高风险提交动作要求一次性 permit。
- 写入审计日志。

新增 component 时，如果它会点击、提交文件、确认弹窗，必须接入 `ActionPolicy`。

## SubmitAuthorization 和 ProductionGate

相关文件：

- `tax_rpa/jobs/submit_authorization.py`
- `tax_rpa/jobs/production_gate.py`

作用：

- `SubmitAuthorization` 发放一次性提交许可。
- `ProductionGate` 检查 canary、calibration、版本、审核清单。

真实提交动作不能通过“改一个布尔值”放开。它必须有独立的审核和产物证据。

## Observability

文件：`tax_rpa/jobs/observability.py`

它会写入：

- `logs/job_events.jsonl`
- `logs/step_journal.jsonl`
- `logs/steps.jsonl`
- `logs/actions.jsonl`
- `logs/ocr.jsonl`
- `logs/dialogs.jsonl`
- `logs/windows.jsonl`
- `logs/preflight.jsonl`
- `logs/failed.json`
- `troubleshooting_index.json`

排查失败时优先打开：

1. `summary.json`
2. `troubleshooting_index.json`
3. `logs/failed.json`
4. 最近截图
5. 最近 OCR JSON
6. `logs/actions.jsonl`
7. `logs/step_journal.jsonl`

## 生产扩展检查

新增流程前，回答这些问题：

- 是否会改数据？
- 是否会上传文件？
- 是否会点击提交、发送、申报、缴款等高风险按钮？
- `inspect_only` 下是否应该拒绝？
- `execute_no_send` 下是否应该允许？
- `submit` 下是否需要 permit？
- 失败时能否生成足够证据？
- 是否需要 callback 通知中台？
- 是否需要进入 artifact manifest？

如果这些问题没有答案，不要直接接入真实客户端。
