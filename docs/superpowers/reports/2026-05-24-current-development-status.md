# 当前开发状态说明

日期：2026-05-24

## 结论

当前可以确认 Phase 0、Phase 1、Phase 2、Phase 3、Phase 4、Phase 5、Phase 6、Phase 7 已开发完成，并通过自动化验证。

当前状态应定义为：

> 基础安全加固、Job 层基础能力、运行模式与高风险提交授权、可观测性与失败排障包、现有 workflow 的 job context 迁移、预填扣除/税款计算/申报表报送 readiness/申报表导出 workflow、callback outbox、artifact manifest、retention cleanup，以及 canary/production gate 代码能力均已完成；真实生产启用仍需要在目标部署机器上生成并审核 calibration/canary artifacts。

Phase 7 已补齐代码侧生产门禁：真实 `submit` 可通过 `ProductionGate` 接入 `SubmitAuthorization`，在 canary artifacts、版本检查、校准门禁和提交启用 checklist 通过审核前拒绝发放一次性 submit permit。

## 已完成范围

### Phase 0：基础安全加固

- `StepResult` 和 `WorkflowResult` 已补齐运行元数据字段。
- 人员、专项附加扣除、工资薪金导入失败或未知时会停止流程。
- 自动重试必须满足 `retry_allowed=true`。
- 自动重试不会跨越已经开始或提交的业务副作用。

### Phase 1：Job Layer Foundation

- `tax_rpa/jobs/manifest.py`：中台任务 manifest 加载与校验。
- `tax_rpa/jobs/artifact_store.py`：job 级 artifact 目录和 JSON 输出。
- `tax_rpa/jobs/state_store.py`：`state.json` 和 `logs/state_transitions.jsonl`。
- `tax_rpa/jobs/lock.py`：UI runner 单实例锁和 `runner.lock.json`。
- `tax_rpa/jobs/preflight.py`：输入文件存在性、临时后缀、Excel 后缀、大小稳定性和 SHA-256 校验。
- `tax_rpa/jobs/runner.py`：从 manifest 到 artifact、state、lock、preflight、summary 的 job 闭环。

### Phase 2：Run Mode and Authorization

- `ActionPolicy` 已接入通用点击、文件、弹窗组件。
- `SubmitAuthorization` 已实现提交授权门禁和 fail-closed 生产开关。
- `inspect_only` 会拦截文件提交和数据变更。
- `execute_no_send` 会允许准备动作，但拒绝 **发送申报** 等高风险动作。
- `submit` 需要 manifest、CLI、生产开关、一次性 permit；Phase 7 路径还可接入 production gate。

### Phase 3：Observability Foundation

- `JobObservability` 提供 job-scoped JSONL 日志、OCR JSON、全屏截图接口、`logs/failed.json` 和 `troubleshooting_index.json`。
- `JobRunner` 在 executor 失败时会写失败排障包。
- 成功和失败 job 均会生成 troubleshooting index。

### Phase 4：Existing Workflow Migration

- `WorkflowJobContext` 已接入既有人员导入、专项附加扣除更新、工资薪金导入 workflow。
- `result_matrix.py` 已覆盖 `personnel_import`、`special_deduction_update`、`salary_income_import`。
- 既有业务步骤已写入 step journal 和 side-effect marker。
- `ExistingWorkflowExecutor` 已把 `JobRunner` 接入既有三段 workflow。

### Phase 5：New Business Workflows

- 新增 result matrix 覆盖 `prefill_deduction`、`tax_calculation`、`declaration_submission_readiness`、`export_report` 和 blocked outcome。
- 新增页面元素与页面步骤：预填扣除、税款计算、申报表报送 readiness、申报表导出。
- 新增 workflow：`PrefillDeductionWorkflow`、`TaxCalculationWorkflow`、`DeclarationSubmissionWorkflow`、`ExportReportWorkflow`。
- `ExistingWorkflowExecutor(include_phase5=True)` 可在 fake-driver 下跑到导出尝试。
- 默认 `include_phase5=False`，避免未校准真实客户端路径提前执行 Phase 5 UI 动作。

### Phase 6：Callback and Retention

- `CallbackOutbox` 支持 delivered、pending、retry、dead-letter、HMAC signature、callback secret redaction。
- `ArtifactManifestWriter` 写入 `artifact_manifest.json`。
- `RetentionCleaner` 实现默认 retention 策略。
- `JobRunner` 终态收口写入 `summary.json`、`artifact_manifest.json`、`logs/callbacks.jsonl`、`callback_outbox.json` 和 troubleshooting callback 链接。
- callback 失败不会改变业务终态。
- retention 会保留 callback state 为 `pending` 或 `dead_letter` 的 job。

### Phase 7：Canary and Production Gate

- 新增 `tax_rpa/jobs/machine_config.py`：
  - `machine_config.json` 加载与校验；
  - secret credential name 在 summary copy 中脱敏；
  - `JobRunner(machine_config_path=...)` 下缺失或无效机器配置会以 `SYSTEM_ENVIRONMENT_ERROR` preflight 失败。
- 新增 `tax_rpa/jobs/runtime_metadata.py`：
  - `summary.json` 记录 script version、git commit、tax client version、OCR engine version、Windows user、resolution、DPI；
  - 读取失败时写 `"unknown"` 或 `None`，不阻断 job。
- 新增 `tax_rpa/jobs/calibration.py`：
  - fake-driver 路径跳过真实校准；
  - 真实 `execute_no_send` 要求必需业务步骤具备 calibration；
  - 真实 `submit` 额外要求申报提交成功/失败文本 calibration。
- 新增 `tax_rpa/jobs/canary.py`：
  - 写入 `artifacts/canary/{timestamp}/canary_record.json`；
  - 不点击 submit；
  - canary 失败时写 `maintenance_ticket.json`，包含失败 target 和建议维护模块。
- 新增 `tax_rpa/jobs/production_gate.py`：
  - 校验 self-check、inspect_only canary、execute_no_send canary、calibration gate、税局客户端版本、checklist review 和 canary review；
  - 未通过时返回 `SUBMIT_NOT_AUTHORIZED`。
- `SubmitAuthorization` 已支持可选 `ProductionGate`，生产部署可在发放一次性 submit permit 前强制检查 Phase 7 门禁。

## 当前可支持的业务与运行能力

- 启动或复用客户端。
- 等待登录完成。
- 导入人员信息文件。
- 更新专项附加扣除全部人员。
- 导入工资薪金所得数据。
- 预填扣除信息。
- 税款计算。
- 申报表报送页面 readiness 检查。
- `execute_no_send` 下尝试导出申报表，或记录 `not_available_before_submit`。
- 生成 callback-safe summary。
- callback 失败时创建 outbox，等待后续重试。
- 生成 artifact manifest。
- 按 retention 策略清理已过期 job，并保留未交付 callback 的 job。
- 生成 canary record 和失败维护 ticket。
- 用 production gate 阻止未审核 canary/calibration 路径发放 submit permit。

Phase 5 新业务段和 Phase 7 门禁目前通过 fake-driver/fixture 验证；真实客户端上线仍需要目标机器上的 calibration 与 canary artifacts。

## 日志与排查能力状态

当前已经具备：

- `state.json`
- `logs/state_transitions.jsonl`
- `logs/job_events.jsonl`
- `logs/step_journal.jsonl`
- `logs/steps.jsonl`
- `logs/actions.jsonl`
- `logs/ocr.jsonl`
- `logs/dialogs.jsonl`
- `logs/windows.jsonl`
- `logs/preflight.jsonl`
- `logs/callbacks.jsonl`
- `ocr/{correlation_id}.json`
- `logs/failed.json`
- `callback_outbox.json`
- `artifact_manifest.json`
- `troubleshooting_index.json`
- `artifacts/canary/{timestamp}/canary_record.json`
- `artifacts/canary/{timestamp}/maintenance_ticket.json`
- workflow result matrix
- side-effect journal marker
- runtime metadata in `summary.json`
- production gate evidence

仍需在部署阶段补齐：

- 真实主窗口截图与失败区域 OCR。
- 真实弹窗文本、窗口树和控件树采集。
- 真实 calibration artifacts。
- 真实 inspect_only 与 execute_no_send canary 记录。
- operator review 后的 submit enablement checklist。

## 验证结果

Phase 7 新测试：

```powershell
.\\.venv\\Scripts\\python.exe -m unittest tests.test_phase7_machine_config tests.test_phase7_runtime_metadata tests.test_phase7_calibration_gate tests.test_phase7_canary_production_gate -v
```

结果：13 tests passed。

Phase 7 定向回归：

```powershell
.\\.venv\\Scripts\\python.exe -m unittest tests.test_phase7_machine_config tests.test_phase7_runtime_metadata tests.test_phase7_calibration_gate tests.test_phase7_canary_production_gate tests.test_job_runner tests.test_submit_authorization tests.test_phase6_job_runner_callback tests.test_callback_outbox tests.test_artifact_manifest_schema tests.test_retention -v
```

结果：28 tests passed。

完整单元测试：

```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
```

结果：189 tests passed。

现有组合流程 self-check：

```powershell
.\\.venv\\Scripts\\python.exe -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

结果：

```text
done: success
C:\rpa-tax-poc\artifacts\person_import_20260524_181422\tax_workflow_summary.json
```

环境限制：

- 当前 shell 中 `git` 不可用，无法执行 `git status --short` 或 `git diff --stat`。
- 本轮以 `task_plan.md`、`findings.md`、`progress.md` 和测试结果作为开发过程审计记录。

## 过程记录

- `task_plan.md`
- `findings.md`
- `progress.md`
- `docs/superpowers/plans/2026-05-24-phase-0-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-1-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-2-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-3-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-4-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-5-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-6-completion.md`
- `docs/superpowers/plans/2026-05-24-phase-7-completion.md`

## 下一阶段建议

代码实现已完成到 Phase 7。下一步不是继续新增核心代码，而是在目标部署环境执行生产启用流程：

- 创建真实 `config/machine_config.json`。
- 采集真实 tax client calibration artifacts。
- 跑真实 `inspect_only` canary。
- 跑真实 `execute_no_send` canary。
- 审核 canary artifacts 并生成 `submit_enablement_checklist.json`。
- 仅在上述材料通过后，将 `ProductionGate` 接入真实 submit 授权路径并启用生产开关。
