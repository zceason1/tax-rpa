# Findings & Decisions

## Requirements

- Continue development from the current documentation.
- Record the development process to avoid implementation drift.
- Current completed baseline is Phase 0, Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, and Phase 7.
- The 2026-06-03 architecture boundary cleanup is complete. Current architecture is `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`.
- Phase 7 code support is complete: machine config, runtime metadata, calibration gate, canary runner, version drift checks, and production gate.
- Do not claim a deployment is ready for real unattended `submit` until real calibration artifacts, canary records, and operator-reviewed submit checklist files exist on the target machine.

## Research Findings

- `docs/superpowers/specs/2026-05-24-unattended-tax-rpa-design.md` defines the full target architecture and phase roadmap.
- `docs/superpowers/plans/2026-05-24-phase-0-completion.md` confirms Phase 0 completion and verification.
- `docs/superpowers/reports/2026-05-24-current-development-status.md` now states that Phase 7 code support is complete and real deployment still needs target-machine calibration/canary artifacts.
- Current package has no `tax_rpa/jobs/` module, so Phase 1 can be added without refactoring an existing job layer.
- `RunLogger` currently writes run artifacts under timestamped `artifacts/person_import_*`; Phase 1 should add a job-scoped artifact store instead of changing this logger immediately.
- `StepResult` and `WorkflowResult` already include Phase 0 metadata: `error_type`, `error_code`, side-effect flags, `retry_allowed`, evidence paths, and UI text.
- Existing tests are pure `unittest`; Phase 1 tests should follow that convention.
- Manifest contract requires `job_id`, `idempotency_key`, `company_name`, `credit_code`, `tax_period`, `person_action`, `run_mode`, `submit_enabled`, and file entries for `person_info` and `salary_income`.
- Phase 1 must reject `person_action="add_person"` with `UNSUPPORTED_ACTION` before queueing.
- Tax period must normalize to `YYYY-MM`; file names may use `YYYYMM`.
- State store must write `state.json` atomically and append transitions to `logs/state_transitions.jsonl`.
- Phase 1 done criterion is a fake job that validates, acquires lock, writes state, creates artifacts, and finishes without launching the tax client.
- Phase 2 requires `ActionPolicy`, `SubmitAuthorization`, production switch handling, high-risk click interception, one-time submit permits, and audit logs.
- High-risk sending requires all gates: `manifest.run_mode == "submit"`, `manifest.submit_enabled == true`, CLI `--submit`, and local production switch enabled.
- Missing or malformed production switch must deny submit with `SUBMIT_NOT_AUTHORIZED`.
- Generic click APIs must call `ActionPolicy.before_click(label, context)` before mouse/OCR/file/dialog actions.
- Current generic action components are `ToolbarComponent`, `ContentTextComponent`, `FileDialogComponent`, `MessageDialogComponent`, `LeftNavComponent`, and `ImportDropdownComponent`.
- Phase 3 requires UTF-8 JSONL logs for `job_events`, `step_journal`, `steps`, `actions`, `ocr`, `dialogs`, `windows`, and `preflight`.
- Every log event must carry job and step context, including `job_id`, `idempotency_key`, `run_mode`, `workflow`, `step`, `event`, `status`, `attempt`, and `correlation_id`.
- Failure packages must include `summary.json`, `logs/failed.json`, first full-screen screenshot, latest action/OCR/dialog/window/step events, and `troubleshooting_index.json`.
- `troubleshooting_index.json` must be the operator's first entry point and contain relative links to relevant artifacts.
- The current `RunLogger` writes timestamped non-job-scoped artifacts, so Phase 3 should add a new job-scoped service before migrating legacy UI workflows.
- The current `JobRunner` can fail an injected fake executor, which is a deterministic place to prove forced-failure troubleshooting package generation.
- `JobObservability` now writes job-scoped UTF-8 JSONL logs for job events, steps, step journal, actions, OCR, dialogs, windows, and preflight.
- `JobObservability.write_ocr_json()` writes OCR row details under `ocr/{correlation_id}.json`.
- `JobObservability.capture_full_screen()` supports an injected screenshot grabber for deterministic tests and logs `screenshot_capture_failed` if capture fails.
- `JobRunner` now writes `logs/failed.json` and `troubleshooting_index.json` for executor failures.
- `troubleshooting_index.json` now links `summary.json`, `state.json`, `logs/failed.json`, primary failure screenshot, latest action/OCR/dialog/window events, latest step journal entry, exported files, and callback outbox placeholder.
- Phase 4 requires personnel import, special deduction update, and salary import to run with job context, action policy, side-effect journal, and result matrix classification.
- Phase 4 done criterion is an `execute_no_send` fake-driver workflow that reaches salary import success.
- Unknown or failed personnel/salary import results must stop before later business workflows continue.
- Existing workflows already compose page steps, but do not yet receive job context or write job-scoped step journal events.
- `TaxClientApp` owns `RpaContext`; action policy can be attached to `app.context.action_policy` when a job context is present.
- Existing self-check pages return deterministic `StepResult` objects and can serve as Phase 4 fake-driver fixtures.
- `WorkflowJobContext` now writes job-scoped `logs/step_journal.jsonl` and `logs/steps.jsonl` entries around migrated workflow steps.
- `result_matrix.py` now classifies `personnel_import`, `special_deduction_update`, and `salary_income_import` as success, failure, or unknown.
- `CombinedTaxWorkflow` previously accepted optional `job_context`; that compatibility alias has now been removed in favor of explicit `step_runner`.
- Existing person, special deduction, salary, and Phase 5 workflows now accept explicit `step_runner` without `job_context`.
- `ExistingWorkflowExecutor` bridges `JobRunner` to the migrated existing workflows using manifest files, `ActionPolicy`, and `WorkflowJobContext`.
- `JobRunner` now treats executor results with `ok=false` as business failures and writes failed artifacts instead of marking the job succeeded.
- Phase 5 adds four workflows: prefill deduction, tax calculation, declaration submission readiness, and export report.
- Prefill deduction must fail if the personal pension option is unavailable unless `manifest.allow_skip_personal_pension=true`.
- Tax calculation must block on non-whitelisted popups as `BLOCKED_BY_UNEXPECTED_DIALOG` and must not click the popup confirmation in that case.
- Declaration readiness in `execute_no_send` must prove the submission page and send button are present without clicking **发送申报**.
- Export in `execute_no_send` may succeed with `export_status="not_available_before_submit"` only after declaration readiness is verified.
- Phase 5 automated tests must stay fake-driver based; real-client `execute_no_send` through new uncalibrated actions should not become the default CLI path yet.
- Phase 5 added page-owned element modules for prefill deduction, tax calculation, declaration submission readiness, and export report.
- Phase 5 added page-step modules for the same four business actions.
- Phase 5 added workflow modules for prefill deduction, tax calculation, declaration submission readiness, and export report.
- `ExistingWorkflowExecutor(include_phase5=True)` runs the full fake-driver chain through export attempt; default `include_phase5=False` preserves the existing calibrated CLI path.
- `execute_no_send` export can finish with `not_available_before_submit` in the fake-driver path, and this is classified as result-matrix success for `export_report`.
- A blocked tax calculation popup stops before declaration submission readiness and export workflows.
- Phase 6 must add callback outbox, retry/dead-letter state, retention cleanup, callback-safe summaries, and `artifact_manifest.json`.
- Callback delivery failure is not a business failure; terminal job state must remain `succeeded`, `failed`, or `blocked` while callback state becomes `pending`.
- Callback payload must include `job_id`, `idempotency_key`, `state`, `business_status`, `error`, `summary_path`, and `artifact_manifest_path`.
- Callback attempts must write `logs/callbacks.jsonl`.
- Retention defaults are 30 days for succeeded jobs and 90 days for failed jobs.
- Retention cleanup must preserve jobs whose callback delivery state is `pending` or `dead_letter`.
- Phase 6 added `CallbackOutbox` for delivered, pending, retry, and dead-letter callback states.
- Phase 6 added HMAC callback signatures when a callback secret is configured.
- Phase 6 added `ArtifactManifestWriter` for `artifact_manifest.json` with relative paths and checksums.
- Phase 6 added callback-safe `summary.json` fields, including `business_status`, `callback_state`, `error`, `summary_path`, and `artifact_manifest_path` in callback payloads.
- Phase 6 added `RetentionCleaner` and default retention policy.
- `JobRunner` now writes `artifact_manifest.json`, `logs/callbacks.jsonl` when callback is attempted or skipped, callback outbox records, and callback links in `troubleshooting_index.json`.
- Phase 7 requires `machine_config.json` support, runtime metadata in `summary.json`, calibration gates, canary records, version drift checks, and submit enablement checklist review.
- Phase 7 added `MachineConfigValidator`; when `JobRunner(machine_config_path=...)` is used, missing or invalid machine config fails preflight with `SYSTEM_ENVIRONMENT_ERROR`.
- Phase 7 added `RuntimeMetadata`; `summary.json` now includes script version, git commit or `"unknown"`, tax client version or `"unknown"`, OCR engine version, Windows user, resolution, and DPI.
- Phase 7 added `CalibrationGate`; fake-driver runs skip real-client calibration, real `execute_no_send` requires required step calibration, and real `submit` also requires declaration submission success/failure text calibration.
- Phase 7 added `CanaryRunner`; it writes `artifacts/canary/{timestamp}/canary_record.json`, never records submit clicks, and writes `maintenance_ticket.json` for missing page markers/buttons/popup patterns.
- Phase 7 added `ProductionGate`; it denies submit until self-check, inspected canary, execute-no-send canary, calibration gate, tax-client version match, and checklist/canary review gates pass.
- `SubmitAuthorization` can now consume an optional `ProductionGate`; when supplied, `production_gate` becomes a deny gate before a one-time submit permit is issued.
- `ActionPolicy` now lives in `tax_rpa/runtime/action_policy.py`; `tax_rpa/jobs/action_policy.py` is a compatibility re-export for job-layer callers.
- Workflow step instrumentation now lives in `tax_rpa/jobs/workflow_step_runner.py` as `JobStepRunner`; `tax_rpa/workflows/job_context.py` has been removed.
- Workflows receive `step_runner`, `runtime_options`, and explicit `action_policy` instead of reading job-specific context.
- `WorkflowRuntimeOptions` carries manifest-derived business flags such as `run_mode` and `allow_skip_personal_pension`.
- Shared UI component implementations now live under `tax_rpa/pages/shared/components`; top-level `tax_rpa/components` has been removed.
- `PersonInfoPage.import_person_file()` has been removed. Production workflow and debug CLI compose `ImportPersonFileStep`, `WaitImportResultStep`, and `SubmitImportDataStep` directly.
- Architecture boundaries are enforced by `tests/test_architecture_boundaries.py` and page-step boundary tests.
- Current file map source of truth is `docs/architecture_file_map.md`; historical files under `docs/superpowers/plans` may mention old paths as migration notes.
- `tax_rpa/constants.py` has been removed. UI target strings now live in page-owned elements or `tax_rpa/runtime/dialog_targets.py`.
- `tax_rpa/utils.py` has been removed. Text normalization and matching now live in `tax_rpa/runtime/text.py`.
- UI action label safety checks now live in `tax_rpa/runtime/action_guard.py`, not config, because drivers/components consume them at runtime.
- Step result matrix classification now lives in `tax_rpa/runtime/result_matrix.py`, not workflows, because job instrumentation and tests consume it as a runtime result contract.
- The only component directories under `tax_rpa` are `tax_rpa/pages/shared/components`, `tax_rpa/pages/person_info/components`, and `tax_rpa/pages/comprehensive_income/components`.
- Workflow constructors no longer expose `job_context`; job integration uses explicit `step_runner`, `runtime_options`, and `action_policy`.
- `tax_rpa.jobs.__init__` no longer re-exports runtime `ActionPolicy`; import it from `tax_rpa.runtime.action_policy`.
- `docs/learning/templates/new_page_step_workflow_template.md` now demonstrates `step_runner` and `WorkflowRuntimeOptions`, not job-context plumbing.
- `docs/superpowers/README.md` marks superpowers plans/specs/reports as historical archive; current architecture source of truth is `docs/architecture_file_map.md`.

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Implement Phase 1 before additional UI workflows | The job layer controls manifest validation, artifacts, state, and locking, which later workflow phases depend on. |
| Treat manifest, state, artifacts, and lock as stable contracts | These outputs will later feed callbacks, troubleshooting packages, and operational audits. |
| Use deterministic unit tests and fake job tests | Phase 1 must not depend on the real tax client or Windows desktop state. |
| Keep Phase 1 preflight to deterministic file checks first | Workbook schema validation is in the full spec, but Phase 1 can establish file existence, suffix, stability, and checksum before later workbook-specific validation. |
| Serialize artifact JSON paths with POSIX separators | Stable artifact contracts should not depend on the Windows path separator. |
| Split UI lock and diagnostic files | Windows locks can make the locked file unreadable; an internal `.mutex` file keeps `runner.lock.json` readable and stale diagnostics non-blocking. |
| Implement Phase 2 policy as a job-layer service | Keeps authorization decisions above pages/components while still allowing components to enforce the contract. |
| Deny high-risk labels by default even in legacy paths | This protects against accidental real submission before declaration workflow code exists. |
| Use optional component `action_policy` parameters during migration | Existing tests and Phase 0 flows can keep running while new policy-aware paths are introduced. |
| Implement Phase 3 as a job-layer observability service first | It gives runner failures and later workflow migrations one stable artifact/log contract. |
| Keep screenshot capture injectable | Tests must not require a live Windows desktop or real image capture. |
| Write `troubleshooting_index.json` for both success and failure when the runner reaches artifact creation | The spec requires an index at the end of each job, and failed jobs must be inspectable first from that file. |
| Add `ocr/` as a first-class job artifact directory | The troubleshooting index must be able to link OCR row JSON files, not only aggregate OCR JSONL events. |
| Migrate Phase 4 with optional job context | Keeps legacy CLI workflows compatible while allowing job-runner paths to record structured observability. |
| Classify migrated workflow results in workflow-level code | UI components report sensed outcomes; workflows decide the result-matrix row and stop/continue behavior. |
| Keep `ExistingWorkflowExecutor` module-level only | Importing it from `tax_rpa.jobs.__init__` creates a circular import through workflows and app components. |
| Gate Phase 5 executor wiring with an explicit flag | Fake-driver integration can cover the new workflows while the default real-client path waits for calibration and canary gates. |
| Keep Phase 6 network I/O injectable | Unit tests and fake-driver runs must not depend on real middle-platform availability. |
| Store callback state outside business transition logic | Callback retry must not convert a terminal business result into a failed job. |
| Preserve pending and dead-letter jobs during retention cleanup | Operators must be able to inspect or acknowledge undelivered results before artifacts are removed. |
| Keep Phase 7 runner machine config validation opt-in | Existing fake-driver and legacy tests should not require deployment-specific config, while production job-runner paths can require it explicitly. |
| Use injectable readers/probes for runtime metadata and canary | Deterministic tests cannot depend on the real tax client, OCR engine, live desktop, or `git` availability. |
| Put canary review in a checklist file rather than a code flag | Submit enablement should be auditable as an artifact, not only a runtime option. |
| Treat `Job` as a production runtime shell, not a page automation layer | Jobs adapt manifests, artifacts, callbacks, and observability to workflows; workflows must not import concrete job modules. |
| Keep Page objects below Steps | Pages expose capabilities; workflows and debug tooling compose steps for business order. |
| Keep shared UI components under `pages/shared/components` | This removes the confusing split between page-local components and the old top-level shared component package, which has now been deleted. |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| `git diff --stat` failed because `git` is not installed in shell PATH | Recorded the limitation; this session uses planning files and test output as the change audit trail. |
| Exporting `ExistingWorkflowExecutor` from `tax_rpa.jobs.__init__` created a circular import | Removed the package-level export; callers should import `tax_rpa.jobs.existing_workflow_executor.ExistingWorkflowExecutor`. |
| Phase 7 calibration test initially recreated an existing fixture directory without `exist_ok=True` | Fixed the test fixture; production code was unchanged. |
| `git status --short` failed during architecture cleanup because `git` is not installed in shell PATH | Recorded the limitation and completed verification with focused tests plus the full unittest suite. |

## Resources

- Main spec: `docs/superpowers/specs/2026-05-24-unattended-tax-rpa-design.md`
- Phase 0 plan: `docs/superpowers/plans/2026-05-24-phase-0-baseline-hardening.md`
- Phase 0 completion: `docs/superpowers/plans/2026-05-24-phase-0-completion.md`
- Current status report: `docs/superpowers/reports/2026-05-24-current-development-status.md`

## Visual/Browser Findings

- No browser or visual findings in this session.
