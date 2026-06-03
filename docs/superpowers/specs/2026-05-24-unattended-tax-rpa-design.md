# Unattended Tax RPA Design

## Goal

Build a Windows desktop RPA system that can run tax declaration jobs without manual intervention. The system receives job files from a middle platform, resets the tax client, logs in, executes the declared business flow, stops on any unknown or failed state, and returns logs, screenshots, exported files, and a structured final status.

The business flow must be correct before it is fast. The system must never continue after an unclear result.

## Non-Goals

- Do not support parallel UI automation on one Windows desktop.
- Do not infer the full business intent from file names alone.
- Do not automatically retry after a step with business side effects.
- Do not send a real declaration outside authorized `submit` mode.
- Do not treat button clicks as success unless the client shows an explicit success result.

## Current Repository Fit

The existing project already has these useful boundaries:

- `workflows/`: orchestration.
- `pages/*/steps/`: business steps.
- `pages/*/page.py`: page-level operations.
- `components/`: reusable UI actions.
- `drivers/`: Win32, OCR, mouse, logging.
- `runtime/result.py`: `StepResult` and `WorkflowResult`.
- `workflows/app_lifecycle_workflow.py`: reset, launch, login.
- `workflows/combined_tax_workflow.py`: workflow composition.

The design keeps this structure and adds a job layer above the current workflow layer.

## Operating Model

The production system has three layers:

```text
RPA Host
  Receives jobs, validates files, creates job folders, enqueues work, triggers execution.

Job Runner
  Runs one job at a time, resets the app, executes workflows, writes status and evidence.

Business Workflows
  Login, personnel collection, special deduction update, salary import, prefill, tax calculation,
  declaration submission, export, final evidence capture.
```

Only the Job Runner operates the tax client. The RPA Host must not click UI elements.

## Job Manifest

The middle platform must send a manifest. File naming is a validation signal, not the source of truth.

Required fields:

```json
{
  "job_id": "202605-001",
  "idempotency_key": "company-tax-period-flow-v1",
  "company_name": "深圳市xxx公司",
  "credit_code": "91440300xxxxxxxxxx",
  "tax_period": "2026-05",
  "person_action": "import_file",
  "person_type": "domestic",
  "run_mode": "execute_no_send",
  "submit_enabled": false,
  "callback_url": "https://middle-platform.example/jobs/callback",
  "files": {
    "person_info": {
      "path": "input/202605_xxx_PERSON_INFO_v1.xlsx",
      "sha256": "..."
    },
    "salary_income": {
      "path": "input/202605_xxx_SALARY_INCOME_v1.xlsx",
      "sha256": "..."
    }
  }
}
```

Manifest schema:

| Field | Type | Required | Allowed Values | Notes |
|---|---|---:|---|---|
| `job_id` | string | Yes | non-empty, unique per job | Used for artifact path and idempotency lookup. |
| `idempotency_key` | string | Yes | non-empty | Same business request must reuse the same key. |
| `company_name` | string | Yes | non-empty | Must match file naming and UI context when detectable. |
| `credit_code` | string | Yes | 18-character credit code | Used for validation and audit. |
| `tax_period` | string | Yes | `YYYY-MM` | File names may use `YYYYMM`; loader normalizes both to `YYYY-MM`. |
| `person_action` | string | Yes | `import_file`, `add_person` | Phase 1 implements only `import_file`. |
| `person_type` | string | Required for `add_person` | `domestic`, `foreign` | Ignored for `import_file`. |
| `run_mode` | string | Yes | `inspect_only`, `execute_no_send`, `submit` | Controls the `ActionPolicy`. |
| `submit_enabled` | boolean | Yes | `true`, `false` | One of the submit gates. |
| `allow_skip_personal_pension` | boolean | No | `true`, `false` | Defaults to `false`; every skip is written to the audit log. |
| `callback_url` | string | No | HTTPS URL | If absent, callback is skipped and result stays local. |
| `files.person_info` | object | Required for `import_file` | file object | Must include `path` and `sha256`. |
| `files.salary_income` | object | Yes | file object | Must include `path` and `sha256`. |

Unknown fields are allowed but must be preserved in `summary.json` under `manifest_extra`. Illegal values fail validation with `MATERIAL_INVALID`.

Phase 1 rejects `person_action="add_person"` with `UNSUPPORTED_ACTION` before queueing. It remains in the schema as a reserved future value so the middle platform contract does not need to rename it later.

Allowed `run_mode` values:

- `inspect_only`: find pages and elements, but do not perform data-changing actions.
- `execute_no_send`: run the preparation flow, including imports, special deduction update, prefill, tax calculation, and export attempts, but do not click **发送申报**.
- `submit`: allow real **发送申报** only if all high-risk authorization gates pass.

The term `debug` is not a runtime mode. If a CLI or UI exposes "debug", it must map to `inspect_only` by default. Operators must choose `execute_no_send` explicitly because it changes business data before submission.

## Run Mode Permission Matrix

| Action | `inspect_only` | `execute_no_send` | `submit` |
|---|---:|---:|---:|
| Start app and login | Yes | Yes | Yes |
| Navigate pages | Yes | Yes | Yes |
| Locate UI elements | Yes | Yes | Yes |
| Click read-only navigation buttons | Yes | Yes | Yes |
| Submit file dialogs | No | Yes | Yes |
| Import personnel file | No | Yes | Yes |
| Add personnel manually | No | No in phase 1 | No in phase 1 |
| Download/update special deduction data | No | Yes | Yes |
| Import salary income file | No | Yes | Yes |
| Prefill deduction information | No | Yes | Yes |
| Run tax calculation | No | Yes | Yes |
| Open declaration submission page | Yes | Yes | Yes |
| Click **发送申报** | No | No | Only with submit authorization |
| Export declaration report | No | Attempt if button exists | Yes |

Every component that can click, type, select a file, or press a confirmation button must receive an `ActionPolicy`. Components must not read CLI flags directly.

`inspect_only` final success is `inspection_completed`. It means required pages and UI elements were found. It does not mean files were imported, tax was calculated, reports were exported, or declaration data is ready.

High-risk sending requires all of these:

- `manifest.run_mode == "submit"`
- `manifest.submit_enabled == true`
- CLI contains `--submit`
- local production switch is enabled on the machine

If any gate is missing, the runner must not click **发送申报**.

## Submit Authorization

`SubmitAuthorization` is a central service used by the declaration submission step. No other code path may click **发送申报**.

Inputs:

- `manifest.run_mode`
- `manifest.submit_enabled`
- CLI `--submit`
- local production switch
- current job id
- current Windows user

Local production switch:

- path: `config/production_submit_enabled.json`;
- default: missing file means disabled;
- expected content: `{ "enabled": true, "approved_by": "...", "approved_at": "..." }`;
- file permissions must allow write access only to the deployment administrator;
- invalid JSON, missing fields, or unreadable file means disabled;
- each authorization check writes an audit log entry.

Authorization result:

| Condition | Result |
|---|---|
| all gates pass | `allow` |
| any gate missing or invalid | `deny` with `SUBMIT_NOT_AUTHORIZED` |
| production switch missing or malformed | `deny` with `SUBMIT_NOT_AUTHORIZED` |

The authorization service must fail closed. A denied result is not a workflow failure in `execute_no_send`; it is expected behavior and returns `ready_to_submit_not_sent`.

Global high-risk click interception:

- `ActionPolicy` owns a list of high-risk labels, including **发送申报**, **报送**, and known aliases.
- All generic click APIs must call `ActionPolicy.before_click(label, context)` before clicking.
- If `label` matches a high-risk label, the click is denied unless a one-time permit from `SubmitAuthorization` is attached.
- A one-time permit contains `job_id`, `step_name`, `label`, `expires_at`, and `permit_id`.
- A permit can be consumed once. Reuse fails with `SUBMIT_NOT_AUTHORIZED`.
- Direct calls to OCR, mouse, toolbar, or content-text click code must not bypass `ActionPolicy`.
- Denied high-risk click attempts are audit events even when no mouse click occurs.

## File Naming

Recommended input file name:

```text
{tax_period}_{company_name}_{credit_code}_{file_role}_v{version}.xlsx
```

Examples:

```text
202605_深圳市xxx公司_91440300xxxxxxxxxx_PERSON_INFO_v1.xlsx
202605_深圳市xxx公司_91440300xxxxxxxxxx_SALARY_INCOME_v1.xlsx
```

Supported `file_role` values:

- `PERSON_INFO`
- `SALARY_INCOME`

The runner validates:

- file exists and is not being written;
- SHA-256 equals the manifest value;
- extension is `.xlsx`, `.xls`, or `.xlsm`;
- file name matches manifest company, tax period, and role;
- workbook has expected sheets and headers;
- workbook row count is non-zero when the job requires data;
- workbook company and tax period fields match the manifest if those fields exist in the workbook; if absent, record `workbook_context_unavailable=true`.

Incomplete file detection:

- Reject files with temporary suffixes: `.tmp`, `.part`, `.download`, `.crdownload`.
- Read file size twice, 3 seconds apart. The values must match.
- Compute SHA-256 twice before validation. The values must match.
- If any check fails, return `FILE_TRANSFER_INCOMPLETE`.

Tax period normalization:

- Manifest format is `YYYY-MM`.
- File names may use `YYYYMM`.
- Internal representation is always `YYYY-MM`.
- `202605` and `2026-05` are equal after normalization.

## Job State Machine

Each job writes a durable state file.

State transition table:

| State | Meaning | Allowed From | Allowed To | Terminal |
|---|---|---|---|---:|
| `received` | Manifest accepted by host | none | `validating`, `cancelled` | No |
| `validating` | Files and manifest are being checked | `received` | `queued`, `failed`, `cancelled` | No |
| `queued` | Job is valid and waiting for the UI lock | `validating` | `running`, `cancelled` | No |
| `running` | Runner owns the UI lock and is executing | `queued`, `running_recovered` | `succeeded`, `failed`, `blocked`, `running_recovered` | No |
| `running_recovered` | Runner resumed after crash before side effects | `running` | `running`, `failed`, `blocked` | No |
| `succeeded` | Business flow finished | `running` | none | Yes |
| `failed` | Job failed without manual decision needed | `validating`, `running`, `running_recovered` | none | Yes |
| `blocked` | Job needs manual review | `running`, `running_recovered` | `cancelled` | Quasi-terminal |
| `cancelled` | Job was cancelled before completion | `received`, `validating`, `queued`, `blocked` | none | Yes |

`succeeded` must not transition to `failed` if callback delivery later fails. Callback delivery is tracked separately.

State records include:

- `job_id`
- current state
- current workflow
- current step
- started and finished timestamps
- error type
- error code
- human-readable message
- screenshot paths
- artifact manifest path
- callback delivery state

State persistence rules:

- Write state updates atomically by writing `state.json.tmp` and renaming to `state.json`.
- Every transition appends one line to `logs/state_transitions.jsonl`.
- Every step writes `logs/step_journal.jsonl` before it performs work.
- A side-effect step must write `side_effect_started=true` before opening a file dialog, clicking an update/prefill/calculate/export/submit action, or pressing a confirmation button.
- A side-effect step writes `side_effect_committed=true` immediately after the UI action is submitted, even before the result is known.
- A crashed `running` job may be recovered only if both the last completed step and the in-progress journal entry have `retry_allowed=true` and `side_effect_committed=false`.
- A crashed `running` job with `side_effect_started=true` and no final `StepResult` becomes `blocked`.
- A crashed `running` job with committed side effects becomes `blocked`.
- `blocked` requires manual review or a new job; it is not automatically retried.

Repeated `job_id` handling:

- If a completed job is repeated, return the prior result.
- If a running job is repeated, return `already_running`.
- If the same idempotency key arrives with different files or checksums, reject it as `IDEMPOTENCY_CONFLICT`.

## Single Instance Rule

One Windows desktop can operate only one tax client job at a time. The runner must use a machine-wide lock before interacting with the client.

Lock implementation:

- Use a named Windows mutex: `Global\TaxRpaUiRunner`.
- Also write `artifacts/runner.lock.json` for diagnostics.
- Lock metadata includes `job_id`, process id, Windows user, acquired time, and heartbeat time.
- Runner updates the heartbeat every 30 seconds while running.
- If the mutex is held, the host queues the job by default.
- If queueing is disabled, return `BUSY` with the active `job_id`.
- A stale diagnostic lock file alone does not block execution if the mutex is free.

## Business Workflow

### 1. Reset, Start, Login

Steps:

1. Terminate existing tax client process.
2. Start the configured app or shortcut.
3. Complete login using the configured login method and credential store.
4. Wait for the main window.
5. Verify the logged-in company and tax period context when the UI exposes them.

Success requires:

- main window found;
- app is in foreground;
- expected company is visible in a configured UI context marker or marked `company_context_unavailable` only when that marker is not exposed by the client;
- login step has explicit success evidence.

Failure handling:

- if app cannot start, fail as `APP_LIFECYCLE_ERROR`;
- if login times out, fail as `LOGIN_TIMEOUT`;
- if company context is wrong or unclear, fail as `COMPANY_CONTEXT_MISMATCH`.

### 2. Personnel Information Collection

The manifest controls the path.

For `person_action = "import_file"`:

1. Open **人员信息采集**.
2. Click **导入**.
3. Click **导入文件**.
4. Select the `person_info` workbook.
5. Wait for an explicit success or failure result.

For `person_action = "add_person"`:

1. Open **人员信息采集**.
2. Click **添加**.
3. Choose **境内人员** or **境外人员** based on `person_type`.
4. Fill fields from structured manifest data.
5. Save and wait for explicit success.

Phase 1 implements only `import_file`. `add_person` is out of scope until a separate person-entry schema and form validation spec exists.

Success requires:

- correct page opened;
- correct action selected;
- file dialog submitted in non-inspect mode;
- import result is explicitly `success`.

Unknown result is failure. `unknown`, timeout, or missing dialog must not continue.

### 3. Special Deduction Update

Steps:

1. Open **专项附加扣除信息采集**.
2. Click **下载更新**.
3. Click **全部人员**.
4. Wait for update completion.
5. Save popup text and screenshot.

Success requires:

- page ready;
- **下载更新** and **全部人员** found;
- update result explicitly indicates success or no-update-needed.

Failure handling:

- missing element fails as `UI_ELEMENT_NOT_FOUND`;
- network or data popup fails as `BUSINESS_REJECTED` unless explicitly whitelisted;
- unknown result fails.

### 4. Salary Income Import

Steps:

1. Open **综合所得申报**.
2. Find **正常工资薪金所得**.
3. Enter the normal salary income page.
4. Click **导入**.
5. Click **导入数据**.
6. Select the `salary_income` workbook.
7. Wait for explicit import success.

Success requires:

- normal salary income page is ready;
- data import result is explicitly `success`;
- failure or unknown result stops the job.

The current code must be extended so salary import waits for a result, not just file dialog submission.

### 5. Prefill Deduction Information

Steps:

1. On the normal salary income page, click **预填扣除信息**.
2. Wait for the confirmation dialog.
3. Capture a screenshot and extract dialog text.
4. Check **我确认需要进行自动选填**.
5. Select **专项附加扣除**.
6. Select **个人养老金**.
7. Click **确认**.
8. Wait for prefill completion.

Success requires:

- expected dialog appears;
- all required checkboxes are found and selected;
- completion result is explicit.

If **个人养老金** is missing or disabled, the job fails unless the manifest contains `allow_skip_personal_pension=true`.

### 6. Tax Calculation

Steps:

1. Reopen **综合所得申报**.
2. Click **2 税款计算**.
3. If a popup appears, capture screenshot and text.
4. Click **继续算税** only if the popup text matches a configured whitelist.
5. Wait for the tax calculation page to be ready.
6. Save a page screenshot.

Success requires:

- **2 税款计算** page ready;
- popup text is logged when present;
- any clicked confirmation is whitelisted;
- page screenshot is saved.

Non-whitelisted popup behavior:

- save screenshot;
- save extracted text;
- stop as `BLOCKED_BY_UNEXPECTED_DIALOG`;
- do not click **继续算税**.

### 7. Declaration Form Submission

Steps:

1. Open **综合所得申报**.
2. Click **4 申报表报送**.
3. Wait for the declaration submission page.
4. Locate **发送申报**.
5. In `inspect_only` or `execute_no_send`, do not click it. Log that the element was found and save a screenshot.
6. In `submit`, click **发送申报** only after all high-risk gates pass.
7. Wait for explicit submission success or failure.

Success in `execute_no_send`:

- page ready;
- **发送申报** located;
- screenshot saved;
- result status must be `ready_to_submit_not_sent`, not `submitted`.

Success in `submit`:

- click is authorized;
- client returns explicit submission success;
- success text and screenshot are saved.

Button click alone is never submission success.

### 8. Export Declaration Report

Steps in `submit`:

1. Click **导出申报表**.
2. Click **标准表样**.
3. Save the file under `artifacts/jobs/{job_id}/exported/`.
4. Wait for the exported file to appear.
5. Validate that the file exists, has non-zero size, and matches the expected extension or naming pattern.
6. Capture the current page screenshot.

Success in `submit` requires:

- export action completed;
- exported file validated;
- current page screenshot saved.

Steps in `execute_no_send`:

1. Locate **导出申报表**.
2. Locate **标准表样** if the menu is available before submission.
3. If the client allows pre-submit export, export the file and label it as `pre_submit_export`.
4. If the client requires prior submission, do not fail the job. Write `export_status="not_available_before_submit"`.
5. Capture the current page screenshot.

Success in `execute_no_send` requires:

- declaration submission page ready;
- **发送申报** located and not clicked;
- export either validated as `pre_submit_export` or explicitly marked `not_available_before_submit`;
- screenshot saved.

`inspect_only` does not export. It only verifies whether the export entry point is visible when reachable without data-changing actions.

### 9. Final Evidence

On success:

1. Capture full-screen screenshot.
2. Write `summary.json`.
3. Write `artifact_manifest.json`.
4. Package artifacts if configured.
5. Send callback or persist callback outbox record.

## Result Decision Matrix

Each business step must classify the UI result by a deterministic table. OCR confidence threshold defaults to `config.ocr_score_threshold`; page-specific thresholds may override it in elements definitions.

| Step | Success Evidence | Failure Evidence | Unknown Condition | Error Type |
|---|---|---|---|---|
| Login | main window found and expected company context verified | login timeout, wrong company, app error popup | company text cannot be verified | `LOGIN_TIMEOUT` or `COMPANY_CONTEXT_MISMATCH` |
| Personnel import | result dialog or page text contains known success text | known failure text, invalid file popup, import exception | timeout before success/failure text | `IMPORT_FAILED` or `UNKNOWN_RESULT` |
| Special deduction update | known success or no-update-needed text | network/data/business error text | timeout with no recognized result | `BUSINESS_REJECTED` or `UNKNOWN_RESULT` |
| Salary income import | known success text after file submission | known failure text or invalid salary file popup | timeout before success/failure text | `IMPORT_FAILED` or `UNKNOWN_RESULT` |
| Prefill deduction | completion text or page state indicating prefill finished | required checkbox missing, disabled, or failure popup | dialog disappears with no completion evidence | `BUSINESS_REJECTED` or `UNKNOWN_RESULT` |
| Tax calculation | calculation page ready, calculation result area visible, no unhandled error popup, page screenshot saved | non-whitelisted popup or calculation failure text | page ready but result area cannot be verified | `BLOCKED_BY_UNEXPECTED_DIALOG` or `UNKNOWN_RESULT` |
| Declaration submission inspect | declaration page ready and **发送申报** located | page not ready or send button missing | OCR sees ambiguous button text | `UI_ELEMENT_NOT_FOUND` |
| Declaration submission submit | authorized click plus known submission success text | submission failure text or unauthorized action | no success/failure text before timeout | `SUBMIT_FAILED` or `UNKNOWN_RESULT` |
| Export report | in `submit`, file appears, size > 0, and name matches expected rule; in `execute_no_send`, either pre-submit file is validated or export is explicitly `not_available_before_submit` after declaration readiness is verified | save dialog failure, zero-size file, or export failure after an export action starts | export action has ambiguous UI state and no file/blocking evidence | `EXPORT_ERROR` or `UNKNOWN_RESULT` |

Known success and failure texts must live in page-owned `elements/` modules, not inside workflows.

Tax calculation completion requires more than page readiness. The implementation must detect a result area or stable calculation content after **继续算税**.

If `execute_no_send` cannot export because the client requires prior submission, the job must still succeed with `export_status="not_available_before_submit"` only when declaration page readiness was verified. This condition must be visible in `summary.json`.

## Error Classification

Required error types:

- `MATERIAL_INVALID`
- `FILE_TRANSFER_INCOMPLETE`
- `IDEMPOTENCY_CONFLICT`
- `BUSY`
- `APP_LIFECYCLE_ERROR`
- `LOGIN_TIMEOUT`
- `COMPANY_CONTEXT_MISMATCH`
- `UI_ELEMENT_NOT_FOUND`
- `FILE_DIALOG_MISSING`
- `IMPORT_FAILED`
- `UNKNOWN_RESULT`
- `UNSUPPORTED_ACTION`
- `BUSINESS_REJECTED`
- `BLOCKED_BY_UNEXPECTED_DIALOG`
- `SUBMIT_NOT_AUTHORIZED`
- `SUBMIT_FAILED`
- `EXPORT_ERROR`
- `CALLBACK_PENDING`
- `SYSTEM_ENVIRONMENT_ERROR`

`CALLBACK_PENDING` is not a business failure. If the business flow succeeds but callback delivery fails, the job state remains `succeeded`, and `callback_state` becomes `pending`. The outbox retries delivery.

Every failure writes:

- current state;
- workflow and step;
- error type and code;
- exception traceback if an exception exists; otherwise write `traceback=null`;
- full-screen screenshot, or `screenshot_capture_failed` evidence if the screen is unavailable;
- current window screenshot, or `window_screenshot_capture_failed` evidence if the window is unavailable;
- OCR rows or popup texts, or `ui_text_unavailable` evidence if extraction fails.

## Observability And Troubleshooting

Logs must let an operator answer five questions for any failed job:

1. Which input files and manifest fields were used?
2. Which workflow and step was running when it stopped?
3. What did the RPA see on screen?
4. What action did it attempt or refuse?
5. Which rule decided success, failure, block, retry, or stop?

Every log event is JSON Lines encoded as UTF-8. Every event must include:

| Field | Required | Description |
|---|---:|---|
| `time` | Yes | ISO 8601 timestamp with local offset. |
| `job_id` | Yes | Job id from the manifest. |
| `idempotency_key` | Yes | Stable business idempotency key. |
| `run_mode` | Yes | `inspect_only`, `execute_no_send`, or `submit`. |
| `workflow` | Yes | Current workflow name. |
| `step` | Yes | Current step name. |
| `event` | Yes | Event type, such as `step_start`, `ocr_scan`, `click_denied`, `step_result`. |
| `status` | Yes | Stable status string. |
| `attempt` | Yes | Step attempt number, starting at `1`. |
| `correlation_id` | Yes | Unique id that links logs, screenshots, OCR files, and artifacts for one step attempt. |

Sensitive values must be redacted before writing logs. Passwords, tokens, and callback secrets must never appear in `steps.jsonl`, screenshots metadata, callback payloads, or exception strings.

Required log files:

| File | Purpose |
|---|---|
| `logs/job_events.jsonl` | High-level job lifecycle: received, validated, queued, started, completed. |
| `logs/state_transitions.jsonl` | Durable state transitions. |
| `logs/step_journal.jsonl` | Step start, in-progress side-effect markers, committed markers, and crash recovery input. |
| `logs/steps.jsonl` | Step-level start/result/error events. |
| `logs/actions.jsonl` | Clicks, denied clicks, file dialog submissions, key presses, and confirmation buttons. |
| `logs/ocr.jsonl` | OCR scans, target text, threshold, candidate matches, chosen match, screenshot path. |
| `logs/dialogs.jsonl` | Popup title, class name, extracted text, matched rule, chosen action. |
| `logs/windows.jsonl` | Main window, active window, top-level windows, relevant child controls at key failures. |
| `logs/callbacks.jsonl` | Callback attempts, HTTP status, timeout, retry schedule, dead-letter state. |
| `logs/preflight.jsonl` | Environment checks and failure codes. |

Failure package requirements:

- `summary.json` contains the final error object and points to the primary failure screenshot.
- `failed.json` contains traceback, state snapshot, current step journal entry, latest action event, latest OCR event, latest dialog event, and latest window snapshot.
- A full-screen screenshot is captured first.
- A main-window screenshot is captured second if a main window exists.
- OCR rows from the failure region are saved under `ocr/{correlation_id}.json`.
- Top-level windows and child controls are saved under `logs/windows.jsonl`.
- If screenshot or OCR capture fails, the failure itself is logged with an explicit `*_capture_failed` event.

Action logging rules:

| Action | Required Log Data |
|---|---|
| OCR target search | target text, aliases, region, threshold, all candidates above threshold, chosen candidate, screenshot path. |
| Click allowed | label, coordinates, source component, permit id when applicable, screenshot before click. |
| Click denied | label, source component, denial reason, matched high-risk label, screenshot before refusal. |
| File dialog submit | file role, relative path, sha256, dialog hwnd, edit control hwnd, submit method. |
| Popup decision | popup title, class, text, matched whitelist/blacklist rule, chosen action. |
| Result classification | step result matrix row, matched success/failure text, status, error type. |

Troubleshooting index:

The runner must write `troubleshooting_index.json` at the end of each job. It contains direct relative paths to:

- final `summary.json`;
- final state file;
- primary failure screenshot;
- last full-screen screenshot;
- last main-window screenshot;
- last OCR JSON;
- last popup text;
- last action event;
- current or last step journal entry;
- exported files;
- callback outbox record.

If a job fails, an operator must be able to inspect `troubleshooting_index.json` first and reach every relevant artifact without searching the folder manually.

## Recovery Policy

The system must track whether a step has created business side effects.

The runtime result contract must be extended before production:

```python
@dataclass(frozen=True)
class StepResult:
    ok: bool
    name: str
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    side_effect_started: bool = False
    side_effect_committed: bool = False
    retry_allowed: bool = False
    evidence_paths: list[str] = field(default_factory=list)
    ui_text: list[str] = field(default_factory=list)
```

Workflow recovery must use `retry_allowed`, `side_effect_started`, and `side_effect_committed`. It must not infer retry safety from only `status` or exception text.

No-side-effect steps:

- file validation;
- app launch before login;
- page navigation before any data mutation;
- finding UI elements in inspect mode.

Side-effect steps:

- selecting and submitting an input file;
- importing data;
- downloading/updating special deduction data;
- prefill deduction information;
- tax calculation;
- sending declaration;
- exporting declaration report.

Automatic reset-and-retry is allowed only before a side-effect step. After a side effect, the runner must fail or block and wait for a new job or manual decision.

The next trigger for a new job must reset the app and start from the beginning.

Default retry rules:

| Condition | Automatic Retry |
|---|---:|
| app failed before login and no side effect started | Yes, once |
| page navigation failed before data mutation | Yes, once |
| file dialog was submitted | No |
| import result is unknown after file submission | No |
| special deduction update clicked | No |
| prefill confirmed | No |
| tax calculation started | No |
| declaration submission clicked | No |
| export started | No |

## Evidence Package

Each job folder:

```text
artifacts/jobs/{job_id}/
  input/
  exported/
  screenshots/
    {step_name}_{attempt}_{timestamp}.png
  logs/
    actions.jsonl
    callbacks.jsonl
    dialogs.jsonl
    job_events.jsonl
    ocr.jsonl
    preflight.jsonl
    state_transitions.jsonl
    step_journal.jsonl
    steps.jsonl
    windows.jsonl
    failed.json
  ocr/
  summary.json
  artifact_manifest.json
  troubleshooting_index.json
```

`artifact_manifest.json` lists:

- all input files and checksums;
- exported files;
- screenshots;
- OCR JSON files;
- log files;
- troubleshooting index;
- final status;
- callback status.

Paths inside `summary.json` and `artifact_manifest.json` must be relative to the job folder. Timestamps use ISO 8601 with local offset.

`artifact_manifest.json` minimum schema:

```json
{
  "job_id": "202605-001",
  "created_at": "2026-05-24T10:12:00+08:00",
  "artifacts": [
    {
      "type": "input",
      "path": "input/202605_xxx_PERSON_INFO_v1.xlsx",
      "sha256": "...",
      "created_at": "2026-05-24T10:00:00+08:00",
      "produced_by_step": "job_intake",
      "required": true
    },
    {
      "type": "screenshot",
      "path": "screenshots/tax_calculation_1_20260524T100900.png",
      "sha256": "...",
      "created_at": "2026-05-24T10:09:00+08:00",
      "produced_by_step": "tax_calculation.capture_page",
      "required": true
    }
  ]
}
```

`summary.json` minimum schema:

```json
{
  "job_id": "202605-001",
  "state": "succeeded",
  "business_status": "ready_to_submit_not_sent",
  "run_mode": "execute_no_send",
  "company_name": "...",
  "credit_code": "...",
  "tax_period": "2026-05",
  "started_at": "2026-05-24T10:00:00+08:00",
  "finished_at": "2026-05-24T10:12:00+08:00",
  "current_workflow": "declaration_submission",
  "current_step": "locate_send_button",
  "error": null,
  "export_status": "exported",
  "callback_state": "delivered",
  "artifacts": {
    "manifest": "artifact_manifest.json",
    "steps": "logs/steps.jsonl",
    "troubleshooting_index": "troubleshooting_index.json",
    "screenshots": []
  }
}
```

Error object schema:

```json
{
  "type": "UI_ELEMENT_NOT_FOUND",
  "code": "send_button_missing",
  "message": "发送申报 button was not found",
  "workflow": "declaration_submission",
  "step": "locate_send_button",
  "retry_allowed": false,
  "side_effect_committed": false
}
```

Callback payload must include `job_id`, `idempotency_key`, `state`, `business_status`, `error`, `summary_path`, and `artifact_manifest_path`.

Callback delivery rules:

- HTTP `200` to `299` means delivered.
- Any other HTTP status, network error, or timeout means pending retry.
- Timeout is 10 seconds per attempt.
- Retries use exponential backoff for 24 hours, then move to dead letter while keeping the job state unchanged.
- Every retry sends the same `job_id` and `idempotency_key`.
- Production callbacks must include an HMAC signature header when `callback_secret` is configured.
- Duplicate callback delivery must be safe for the receiver because the idempotency key is stable.

## Runtime Environment Requirements

The machine must:

- stay interactively logged in;
- not lock the screen;
- keep display awake;
- use fixed resolution and DPI;
- avoid RDP disconnects that destroy the desktop surface;
- run under the intended Windows user;
- have stable network access;
- have enough disk space for screenshots and exports;
- have OCR dependencies installed;
- have watchdog monitoring for hung jobs.

If these checks fail before a job starts, the job must fail as `SYSTEM_ENVIRONMENT_ERROR`.

Preflight checks:

| Check | Implementation Signal | Failure Code |
|---|---|---|
| interactive user session | current process has visible desktop and foreground window access | `no_interactive_desktop` |
| screen not locked | screenshot succeeds and image is not blank/lock screen pattern | `screen_locked_or_unavailable` |
| fixed resolution | current resolution equals configured resolution | `resolution_mismatch` |
| DPI | current DPI equals configured DPI | `dpi_mismatch` |
| disk space | artifact drive free space above configured threshold | `low_disk_space` |
| OCR available | OCR engine can load and run on a sample image | `ocr_unavailable` |
| app path | configured app path exists | `missing_app_path` |
| network | callback host and tax client network probe pass when configured | `network_unavailable` |

## Data Security

Production credentials must not be stored in plain JSON.

Required controls:

- store declaration password in Windows Credential Manager or DPAPI-protected storage;
- redact passwords and tokens from logs;
- restrict artifact folder permissions;
- configure retention for screenshots, Excel files, and logs;
- include sensitive-data warning in callback payloads;
- avoid sending raw screenshots unless required by the middle platform.

## Version Drift Controls

Before allowing real `submit` mode after a client update or script update:

1. Run self-check.
2. Run `inspect_only` canary.
3. Run `execute_no_send` canary.
4. Enable `submit` only after expected pages, elements, and popups are confirmed.

The system must attempt to record the tax client version. If it cannot be read, write `tax_client_version="unknown"`.

Canary records are written under `artifacts/canary/{timestamp}/`. A canary passes only when all configured page markers, buttons, and known popup patterns are found without clicking **发送申报**.

## Implementation Module Boundaries

Recommended new modules:

```text
tax_rpa/jobs/
  manifest.py          # JobManifest schema, normalization, validation
  state_store.py       # atomic state.json and state_transitions.jsonl writes
  artifact_store.py    # job folder paths and artifact_manifest.json
  lock.py              # Windows mutex and diagnostic lock file
  authorization.py     # ActionPolicy and SubmitAuthorization
  runner.py            # one-job execution boundary
  callback_outbox.py   # callback persistence and retry
  preflight.py         # environment checks
```

`workflows/` must not parse raw manifest JSON. Workflows receive typed config and action policy from `jobs/runner.py`.

## Maintainability Requirements

The implementation must keep future tax client UI changes localized. A common page text, button label, popup text, or OCR alias change must not require workflow rewrites.

Change ownership matrix:

| Change Type | Primary Edit Location | Required Tests |
|---|---|---|
| Button text, OCR alias, popup wording, page marker | page-owned `elements/` module | element matching unit test |
| Page-specific click sequence | page-owned `steps/` module | step unit test with fake page/component |
| Cross-page reusable UI behavior | `components/` or `pages/shared/` | component boundary unit test |
| Low-level Win32/OCR/mouse behavior | `drivers/` | driver unit test or fake-driver contract test |
| New business phase | new workflow under `workflows/` and page steps under `pages/*/steps/` | workflow composition test |
| Job intake, state, lock, callback, artifacts | `tax_rpa/jobs/` | job-layer unit test |
| High-risk action policy | `tax_rpa/jobs/authorization.py` | authorization and bypass tests |

Import direction rules:

```text
jobs -> workflows -> page steps -> pages/components -> elements -> drivers
```

Rules:

- `drivers/` must not import `pages`, `workflows`, or `jobs`.
- `elements/` must not perform clicks, sleeps, file IO, or workflow decisions.
- `workflows/` must not contain OCR text constants, coordinates, Win32 class names, or file dialog details.
- `jobs/` owns manifest parsing, run mode, action policy, state, artifacts, callback, and locking.
- Page steps return structured results and do not decide job-level retry or callback behavior.

Extension rules:

- Add a new page by creating `pages/{page_name}/elements`, `page.py`, and `steps/`.
- Add a new business phase by composing existing or new page steps in a workflow.
- Add a new popup decision by updating page-owned element rules and result matrix tests.
- Add a new high-risk action by updating `ActionPolicy` high-risk labels and authorization tests.
- Add a new manifest field by updating `JobManifest`, schema tests, `summary.json`, and callback payload compatibility notes.

Stable contract rules:

- `JobManifest`, `StepResult`, `WorkflowResult`, `summary.json`, `artifact_manifest.json`, and callback payloads are versioned contracts.
- Contract-breaking changes require a version bump in the schema and backward-compatible readers for one release cycle.
- Unknown manifest fields are preserved in `manifest_extra`; unknown required behavior is rejected during validation.
- Status strings and error types are stable enums. Do not rename them without a migration note.

Maintainability tests:

- Workflow composition tests must verify business order without real UI.
- Component tests must verify `ActionPolicy` is called before every click/type/file-submit action.
- Element tests must verify known labels and aliases for each page.
- Artifact schema tests must run without launching the tax client.
- Recovery tests must simulate crashes before, during, and after side-effect steps.

Operational maintenance:

- Every production run records script version, git commit or `"unknown"`, tax client version or `"unknown"`, OCR engine version, Windows user, resolution, and DPI in `summary.json`.
- Each tax client update requires a canary run before `submit` mode is enabled.
- Each failed canary creates a maintenance ticket with the failed page marker, screenshot, OCR rows, and suggested element module to inspect.
- Artifact retention defaults to 90 days for failed jobs and 30 days for succeeded jobs unless deployment policy overrides it.
- Retention cleanup must never delete jobs with callback state `pending` or `dead_letter` until an operator exports or acknowledges them.

Developer review checklist:

- Does the change keep business ordering in workflows and UI details in page steps/components/elements?
- Does every new side-effect action write step journal entries before and after the UI action?
- Does every new click path go through `ActionPolicy`?
- Does every new result state have success, failure, unknown, screenshot, and OCR evidence rules?
- Does every new error type appear in tests and callback payload examples?
- Can a maintainer identify the first file to edit from the change ownership matrix?

## Implementation Roadmap

Implementation must proceed in phases. A later phase must not start until the earlier phase meets its done criteria.

| Phase | Scope | Depends On | Done Criteria |
|---|---|---|---|
| 0. Baseline hardening | Fix existing unsafe behavior: unknown import result fails, page open result is checked, salary import waits for result, workflow retry does not cross side effects. | Current codebase | Existing tests pass; new tests cover each fixed regression. |
| 1. Job layer foundation | Add `tax_rpa/jobs/manifest.py`, `state_store.py`, `artifact_store.py`, `lock.py`, `preflight.py`. | Phase 0 | A fake job can validate, acquire lock, write state, create artifacts, and finish without launching the tax client. |
| 2. Run mode and authorization | Add `ActionPolicy`, `SubmitAuthorization`, production switch, high-risk click interception, and audit logs. | Phase 1 | Generic click components cannot bypass policy; all submit gates are tested. |
| 3. Observability foundation | Add job-scoped logger, full-screen screenshots, action/OCR/dialog/window logs, troubleshooting index. | Phase 1 | A forced failure produces a complete troubleshooting package. |
| 4. Existing workflow migration | Migrate personnel import, special deduction update, and salary import to job context, action policy, side-effect journal, and result matrix. | Phases 1-3 | `execute_no_send` fake-driver workflow reaches salary import success; unknown/failed imports stop. |
| 5. New business workflows | Add prefill deduction, tax calculation, declaration submission readiness, and export workflow. | Phase 4 and real client calibration | Fake-driver tests cover success, failure, unknown, and blocked outcomes for every new workflow. |
| 6. Callback and retention | Add callback outbox, dead letter, retention cleanup, callback-safe summaries. | Phases 1 and 3 | Callback retry and retention tests pass; callback failure does not change business state. |
| 7. Canary and production gate | Add canary runner, version drift checks, submit enablement checklist. | Phases 1-6 | `submit` mode remains disabled until canary artifacts pass review. |

Phase 0 is mandatory before adding new pages. It removes current behavior that can continue after an unknown result or wrong page.

Implementation checkpoints:

- Each phase ends with unit tests and fake-driver integration tests.
- A phase cannot depend on real tax client access for its automated tests.
- Real client validation is added only after fake-driver tests pass.
- Every production-risk behavior must have a negative test: denied submit, missing element, unknown OCR result, blocked popup, side-effect crash.

## Real Client Calibration

Before implementing or enabling a business step against the real tax client, create a calibration record for that step.

Calibration artifacts are stored under:

```text
artifacts/calibration/{tax_client_version}/{page_name}/
```

Each calibrated page writes:

- full-screen screenshot;
- page-region screenshot;
- OCR rows JSON;
- top-level window and child control snapshot;
- popup samples when applicable;
- element calibration table.

Element calibration table schema:

| Field | Required | Description |
|---|---:|---|
| `page_name` | Yes | Page module name, such as `comprehensive_income`. |
| `tax_client_version` | Yes | Client version or `"unknown"`. |
| `element_id` | Yes | Stable id used by elements module. |
| `ui_text` | Yes | Main UI text seen in the client. |
| `aliases` | Yes | OCR aliases and alternate wording. Empty list is allowed. |
| `element_type` | Yes | `page_marker`, `button`, `menu_item`, `checkbox`, `dialog_text`, `result_text`. |
| `region_hint` | Yes | `left_nav`, `toolbar`, `content`, `dialog`, or `full_window`. |
| `success_texts` | No | Texts that prove success for result elements. |
| `failure_texts` | No | Texts that prove failure for result elements. |
| `unknown_behavior` | Yes | Stop behavior when text is not recognized. |
| `sample_screenshot` | Yes | Relative path to screenshot sample. |
| `sample_ocr_json` | Yes | Relative path to OCR rows. |
| `min_score` | Yes | OCR threshold for this element. |
| `owner_module` | Yes | Target `elements/` file. |

Required calibration coverage:

| Business Step | Required Calibration |
|---|---|
| Login | login method, main window marker, company context marker. |
| Personnel import | page marker, **导入**, **导入文件**, success text, failure text. |
| Special deduction update | page marker, **下载更新**, **全部人员**, success/no-update/failure texts. |
| Salary income import | **综合所得申报**, **正常工资薪金所得**, **导入**, **导入数据**, import result texts. |
| Prefill deduction | **预填扣除信息**, confirmation text, **我确认需要进行自动选填**, **专项附加扣除**, **个人养老金**, completion/failure texts. |
| Tax calculation | **2 税款计算**, expected popup text, **继续算税**, calculation result area marker, error texts. |
| Declaration submission | **4 申报表报送**, **发送申报**, submission success/failure texts. |
| Export report | **导出申报表**, **标准表样**, save dialog behavior, exported file naming pattern. |

Calibration gate:

- Fake-driver tests may use synthetic fixtures.
- `execute_no_send` against a real client requires calibration for every step up to export.
- `submit` requires calibration for declaration submission success and failure texts.
- A tax client update invalidates calibration until a canary confirms all required markers still match.

## Blocked Job Handling

`blocked` means the runner reached a state where automatic retry may duplicate business effects or make an unsafe decision.

Blocked reasons:

| Reason | Example | Required Operator Action |
|---|---|---|
| `side_effect_crash` | Process crashed after file dialog submit. | Inspect troubleshooting package and decide whether to create a new job. |
| `unexpected_dialog` | Tax calculation popup does not match whitelist. | Review popup text and update whitelist or reject materials. |
| `unknown_result_after_side_effect` | Import submitted but no success/failure text found. | Verify client state manually before new trigger. |
| `company_context_unclear` | Company marker unavailable or mismatched. | Confirm account/company in client. |
| `manual_review_required` | Business rule intentionally stops for review. | Approve cancellation or create corrected job. |

Blocked protocol:

1. Runner writes final state `blocked`.
2. Runner captures full-screen and main-window screenshots.
3. Runner writes `troubleshooting_index.json`.
4. Runner sends callback with `state="blocked"` when callback is configured.
5. Operator reviews artifacts and chooses one action:
   - `cancel`: mark job `cancelled`;
   - `acknowledge`: leave job `blocked` but mark review complete;
   - `new_job`: create a new job id and rerun from a clean app state;
   - `manual_complete`: mark external completion only if business owner confirms the client state.

Rules:

- A blocked job is never resumed in place.
- A blocked job id is never reused for a new run.
- A new run must use a new `job_id`; it may reuse the same `idempotency_key` only if the middle platform explicitly supersedes the blocked job.
- The operator action is written to `logs/operator_actions.jsonl`.

Operator action schema:

```json
{
  "time": "2026-05-24T10:30:00+08:00",
  "job_id": "202605-001",
  "operator": "DOMAIN\\user",
  "action": "new_job",
  "reason": "Import result unknown after side effect",
  "superseding_job_id": "202605-001-rerun-1"
}
```

## Machine Configuration

Machine-specific deployment settings live outside job manifests.

Recommended path:

```text
config/machine_config.json
```

Minimum schema:

```json
{
  "schema_version": 1,
  "app": {
    "app_path": "C:/path/to/client.lnk",
    "process_name": "EPPortalITS.exe",
    "launch_timeout_seconds": 60,
    "login_timeout_seconds": 300,
    "window_timeout_seconds": 90
  },
  "screen": {
    "required_width": 1920,
    "required_height": 1080,
    "required_dpi": 96
  },
  "ocr": {
    "engine": "rapidocr",
    "default_score_threshold": 0.35
  },
  "artifacts": {
    "root": "artifacts/jobs",
    "min_free_gb": 10,
    "retention_success_days": 30,
    "retention_failed_days": 90
  },
  "callback": {
    "timeout_seconds": 10,
    "retry_window_hours": 24,
    "secret_credential_name": "tax-rpa-callback-secret"
  },
  "submit": {
    "production_switch_path": "config/production_submit_enabled.json"
  }
}
```

Rules:

- Job manifests describe business intent.
- `machine_config.json` describes local runtime behavior.
- Secrets are referenced by credential name, not stored in this file.
- Missing required machine config fails preflight with `SYSTEM_ENVIRONMENT_ERROR`.
- Machine config values are copied into `summary.json` after redaction.

## Test Fixtures

The implementation must include deterministic fixtures before production.

Required fixture groups:

| Fixture Group | Purpose |
|---|---|
| valid manifest | Happy-path `execute_no_send` and `submit` schema validation. |
| invalid manifest | Missing fields, illegal enum, bad tax period, unsupported `add_person`. |
| file transfer | half-written file, changed checksum, temp suffix, missing file. |
| authorization | every denied submit gate, all gates pass, permit reuse. |
| state recovery | crash before side effect, crash during side effect, crash after commit. |
| OCR | target found, target missing, low score, ambiguous candidates. |
| dialogs | whitelisted continue-tax popup, non-whitelisted popup, failure popup. |
| business results | import success, import failure, import unknown, prefill missing personal pension, tax calculation unknown. |
| callback | 2xx delivered, 4xx retry, 5xx retry, timeout, dead letter. |
| artifacts | summary schema, artifact manifest schema, troubleshooting index schema. |

Fixture storage:

```text
tests/fixtures/jobs/
tests/fixtures/ocr/
tests/fixtures/dialogs/
tests/fixtures/artifacts/
```

Every acceptance criterion must reference at least one fixture or fake-driver scenario. Real client screenshots may be added as calibration fixtures, but unit tests must not require the real client.

## Required Code Changes Before Production

- Add `JobManifest` and job config loader.
- Add job-level artifact directory support to `RunLogger`.
- Add full-screen screenshot support.
- Add durable job state writer.
- Add machine-wide lock.
- Add callback outbox.
- Split general UI execution mode from high-risk submit authorization.
- Add structured troubleshooting logs and `troubleshooting_index.json`.
- Make toolbar, content-text, file-dialog, and OCR click components consistently honor the selected execution mode.
- Make unknown import results fail.
- Make page open methods return checked results and stop on failure.
- Prevent automatic retry after side-effect steps.
- Add salary import result waiting.
- Add workflows for prefill deduction, tax calculation, declaration submission, and export.
- Add popup whitelist handling for **继续算税**.
- Add success detection for real declaration submission.
- Add export file validation.
- Add unit tests for run mode permissions and submit authorization.
- Add unit tests for state transitions and crash recovery rules.
- Add fake-driver workflow tests for each business result decision matrix row.
- Add artifact schema tests for `summary.json` and `artifact_manifest.json`.
- Add troubleshooting package tests for failure cases.
- Add maintainability boundary tests for import direction and workflow/component responsibilities.
- Add real client calibration record templates and validation.
- Add blocked job operator action recording.
- Add `machine_config.json` loader and preflight validation.
- Add required test fixtures for manifest, files, authorization, recovery, OCR, dialogs, callbacks, and artifacts.

## Acceptance Criteria

The system is acceptable for production only when all criteria pass:

| Criterion | Required Test Type |
|---|---|
| A valid `execute_no_send` job runs through personnel import, special deduction update, salary import, prefill, tax calculation, declaration page readiness, export attempt, and final screenshot. | fake-driver integration test |
| `inspect_only` never submits file dialogs, imports files, updates deductions, prefills, calculates tax, exports, or clicks **发送申报**. | unit test for `ActionPolicy` plus fake-driver test |
| `execute_no_send` never clicks **发送申报**. | unit test for `SubmitAuthorization` plus fake-driver test |
| A real `submit` job cannot click **发送申报** unless all authorization gates pass. | unit test for every denied gate |
| Any missing element stops the job and saves a screenshot. | fake OCR/driver test |
| Any import timeout or unknown result stops the job. | workflow unit test |
| Any unexpected tax calculation popup stops the job and logs the popup text. | workflow unit test |
| The runner never auto-retries after import, prefill, tax calculation, submission, or export side effects. | recovery policy unit test |
| Repeated `job_id` is idempotent. | job state store test |
| Half-written input files are rejected. | file validation unit test |
| Each job produces `summary.json`, `steps.jsonl`, screenshots, exported files when applicable, and `artifact_manifest.json`. | artifact schema test |
| Callback failure does not lose the result; it creates an outbox item for retry while job state remains unchanged. | callback outbox unit test |
| All submit authorization gates passing allows exactly one **发送申报** click permit. | authorization unit test |
| Generic click components cannot click high-risk labels without a one-time permit. | component boundary unit test |
| Crash during an in-progress side-effect step moves the job to `blocked`. | state recovery unit test |
| `execute_no_send` succeeds with `export_status="not_available_before_submit"` when pre-submit export is unavailable but declaration readiness is verified. | fake-driver integration test |
| `allow_skip_personal_pension=true` allows missing **个人养老金** only with an audit entry. | workflow unit test |
| `person_action="add_person"` is rejected in phase 1 with `UNSUPPORTED_ACTION`. | manifest validation unit test |
| A failed job produces `troubleshooting_index.json` that links to final state, primary screenshot, latest OCR, latest dialog, latest action, and current step journal entry. | troubleshooting artifact test |
| Logs redact passwords, tokens, and callback secrets. | log redaction unit test |
| OCR target failures include candidates, threshold, screenshot path, and region. | OCR logging unit test |
| High-risk click denials appear in `logs/actions.jsonl` with denial reason and no click coordinates submitted to the mouse driver. | component boundary unit test |
| Workflows do not import drivers or page element modules directly. | architecture boundary test |
| Button text or popup wording changes can be handled by editing page-owned `elements/` without changing workflow code. | element contract test |
| Every UI action component calls `ActionPolicy` before clicking, typing, selecting a file, or confirming a dialog. | component boundary unit test |
| `summary.json` records script version, tax client version or `"unknown"`, OCR engine version, Windows user, resolution, and DPI. | artifact schema test |
| Retention cleanup preserves callback `pending` and `dead_letter` jobs. | retention policy unit test |
| Implementation phases are completed in order and Phase 0 hardening passes before new workflows are enabled. | release checklist |
| Real `execute_no_send` runs are blocked until calibration records exist for every required page and step. | calibration gate test |
| Real `submit` runs are blocked until declaration submission success/failure calibration exists. | calibration gate test |
| Blocked jobs write `logs/operator_actions.jsonl` when an operator cancels, acknowledges, supersedes, or manually completes review. | blocked workflow test |
| Blocked jobs are never resumed in place and a new run uses a new `job_id`. | state store test |
| Missing or invalid `machine_config.json` fails preflight with `SYSTEM_ENVIRONMENT_ERROR`. | machine config unit test |
| Every acceptance criterion maps to a deterministic fixture or fake-driver scenario. | test coverage review |
