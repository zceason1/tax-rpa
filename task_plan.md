# Task Plan: Unattended Tax RPA Implementation

## Goal

Implement the unattended tax RPA design phase by phase while recording scope, findings, progress, test results, and errors to prevent implementation drift.

## Current Phase

Architecture file map and boundary cleanup complete

## Scope Boundary

Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, and Phase 7 are complete against deterministic unit and fake-driver validation from `docs/superpowers/specs/2026-05-24-unattended-tax-rpa-design.md`.

The 2026-06-03 architecture boundary cleanup is complete against `docs/superpowers/plans/2026-06-03-architecture-boundary-cleanup.md`. The active architecture is now documented and tested as `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`.

Architecture cleanup completed scope:

- `ActionPolicy` implementation moved to `tax_rpa/runtime/action_policy.py`.
- Workflow `job_context` coupling split into `StepRunner`, `WorkflowRuntimeOptions`, and explicit `action_policy`.
- Shared UI component implementations moved under `tax_rpa/pages/shared/components`; top-level `tax_rpa/components` removed.
- `PersonInfoPage.import_person_file()` removed; personnel import orchestration now lives in workflow/debug CLI via page steps.
- Architecture boundary tests added for workflow/job, page/job, step/driver, page/step, and removed workflow job-context module boundaries.
- Architecture docs rewritten to match the current code.
- Full unit suite passes: 227 tests after removing obsolete compatibility and temporary architecture tests.

Architecture file-map cleanup completed scope:

- Root `tax_rpa/constants.py` and `tax_rpa/utils.py` removed; constants and text helpers now live in page elements or `tax_rpa/runtime`.
- `tax_rpa/jobs/action_policy.py`, `tax_rpa/pages/person_info_page.py`, and `tax_rpa/workflows/result_matrix.py` removed; current imports use runtime/page-step locations directly.
- Workflow constructor `job_context` compatibility aliases removed; new and existing code uses `step_runner` and `runtime_options`.
- UI action safety guard moved from `tax_rpa/config/person_import.py` to `tax_rpa/runtime/action_guard.py`.
- Dialog target constants moved to `tax_rpa/runtime/dialog_targets.py`, with page-level exports through `tax_rpa/pages/shared/elements/dialogs.py`.
- `docs/architecture_file_map.md` added as the current file inventory and trace-path entry point.
- Temporary architecture tests created during the cleanup were deleted after verification; no throwaway test files remain.
- Architect review follow-ups completed: workflow `job_context` aliases removed, new-flow template updated to `step_runner`, historical docs archive marked, and `jobs.__init__` no longer re-exports `ActionPolicy`.

Architecture cleanup remaining limitation:

- Commit steps in the written plan were not run because `git` is not available in the current shell PATH.

Phase 4 completed scope:

- workflow job context that carries job observability and action policy into existing workflows.
- result matrix classification for personnel import, special deduction update, and salary income import.
- step journal entries before and after migrated workflow steps.
- side-effect journal markers around file import, special deduction update, and salary import steps.
- fake-driver/self-check test proving `execute_no_send` reaches salary import success.
- negative fake-driver tests proving unknown or failed import results stop the migrated workflow.

Phase 5 completed scope:

- Prefill deduction workflow.
- Tax calculation workflow.
- Declaration submission readiness workflow.
- Export report workflow.
- Fake-driver tests covering success, failure, unknown, and blocked outcomes for the new workflows.

Phase 6 completed scope:

- Callback outbox and retention.
- Callback-safe summary payloads.
- `artifact_manifest.json`.
- Callback delivery state that does not mutate terminal business state.

Phase 7 completed scope:

- Machine config loader and optional runner preflight failure for missing or invalid machine config.
- Runtime metadata in `summary.json`: script version, git commit, tax client version, OCR engine version, Windows user, resolution, and DPI.
- Calibration gate for real-client `execute_no_send` and `submit`.
- Canary runner that writes reviewed artifacts and maintenance tickets without clicking submit.
- Production gate and submit authorization integration so submit can be denied until canary artifacts pass review.

Still out of scope after Phase 7:

- Producing real-client calibration artifacts on the deployment machine.
- Running real `inspect_only` and `execute_no_send` canaries against the tax client.
- Operator review and approval of actual canary artifacts.
- Real main-window screenshot capture and OCR region extraction beyond the generic hooks.
- Enabling real `submit` in a deployment without a reviewed `submit_enablement_checklist`.

## Phases

### Phase 1.1: Discovery and drift guard setup

- [x] Create persistent planning files.
- [x] Read current code structure and Phase 0 contracts.
- [x] Record findings and implementation boundaries.
- **Status:** complete

### Phase 1.2: Job manifest contract

- [x] Add failing tests for manifest loading and validation.
- [x] Implement `JobManifest`, file roles, run modes, and validation errors.
- [x] Preserve unknown manifest fields under `manifest_extra`.
- [x] Reject unsupported `person_action="add_person"` for Phase 1.
- **Status:** complete

### Phase 1.3: Artifact store

- [x] Add failing tests for job directory creation.
- [x] Implement job-scoped artifact paths.
- [x] Implement JSON write helper with stable relative paths.
- **Status:** complete

### Phase 1.4: State store

- [x] Add failing tests for state transitions and atomic state writes.
- [x] Implement `state.json` and `logs/state_transitions.jsonl`.
- [x] Reject invalid transitions.
- **Status:** complete

### Phase 1.5: UI lock

- [x] Add failing tests for lock metadata and busy behavior.
- [x] Implement a cross-process lock abstraction suitable for tests and Windows deployment.
- [x] Write diagnostic lock metadata.
- **Status:** complete

### Phase 1.6: Preflight validation

- [x] Add failing tests for file existence, suffix, temp suffix, stable size, and checksum.
- [x] Implement manifest file preflight.
- [x] Return structured preflight errors.
- **Status:** complete

### Phase 1.7: Fake job runner

- [x] Add failing integration test for a fake job that validates, locks, writes state, creates artifacts, and finishes without launching the client.
- [x] Implement the minimal runner path.
- [x] Ensure Phase 1 runner does not call the real tax client.
- **Status:** complete

### Phase 1.8: Regression and completion note

- [x] Run targeted Phase 1 tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Create Phase 1 completion note.
- **Status:** complete

### Phase 2.1: Run mode and authorization discovery

- [x] Re-read Phase 2 spec sections.
- [x] Inspect generic click/file/dialog components.
- [x] Record Phase 2 boundaries and technical decisions.
- **Status:** complete

### Phase 2.2: Action policy contract

- [x] Add failing tests for run mode permissions and high-risk label denial.
- [x] Implement `ActionPolicy`, `ActionDecision`, `ActionDeniedError`, and `ActionAuditLogger`.
- [x] Ensure denied high-risk attempts are audit events.
- **Status:** complete

### Phase 2.3: Submit authorization contract

- [x] Add failing tests for every submit gate.
- [x] Implement `SubmitAuthorization`, production switch loading, and fail-closed denial.
- [x] Implement one-time `SubmitPermit`.
- **Status:** complete

### Phase 2.4: Component interception

- [x] Add failing tests proving toolbar/content/file/dialog components call `ActionPolicy`.
- [x] Wire action policy into generic click/file/dialog components.
- [x] Wire default page-created components to `RpaContext.action_policy`.
- **Status:** complete

### Phase 2.5: Regression and completion note

- [x] Run Phase 2 targeted tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update status and completion docs.
- **Status:** complete

### Phase 3.1: Observability discovery and boundary update

- [x] Re-read Phase 3 spec sections.
- [x] Inspect existing logger, artifact store, action policy, and runner.
- [x] Record Phase 3 boundaries and environment limits.
- **Status:** complete

### Phase 3.2: Job observability contract

- [x] Add failing tests for JSONL logs, full-screen screenshot capture, and troubleshooting index.
- [x] Implement job-scoped observability helpers.
- [x] Ensure paths in artifacts remain job-relative and POSIX serialized.
- [x] Add OCR artifact directory and `ocr/{correlation_id}.json` writer.
- **Status:** complete

### Phase 3.3: Runner failure package

- [x] Add failing forced-failure runner test.
- [x] Capture failure screenshot through an injectable screenshot grabber.
- [x] Write `summary.json`, `logs/failed.json`, and `troubleshooting_index.json` on failure.
- **Status:** complete

### Phase 3.4: Regression and completion note

- [x] Run Phase 3 targeted tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update current status and create Phase 3 completion note.
- **Status:** complete

### Phase 4.1: Existing workflow migration discovery

- [x] Re-read Phase 4 spec sections and maintainability rules.
- [x] Inspect existing combined/person/special-deduction/salary workflows and page steps.
- [x] Record Phase 4 boundaries and migration decisions.
- **Status:** complete

### Phase 4.2: Workflow job context and result matrix

- [x] Add failing tests for job-scoped workflow logging and result classification.
- [x] Implement workflow job context wrapper.
- [x] Implement result matrix classification for existing workflows.
- **Status:** complete

### Phase 4.3: Migrate existing workflows

- [x] Add failing tests for personnel import, special deduction update, and salary import step journals.
- [x] Wire optional job context through `CombinedTaxWorkflow` and existing business workflows.
- [x] Add side-effect journal markers for file submission/update/import steps.
- **Status:** complete

### Phase 4.4: Fake-driver integration

- [x] Add failing execute_no_send fake-driver job test that reaches salary import success.
- [x] Add negative fake-driver tests for unknown/failed import outcomes.
- [x] Ensure failures stop before subsequent business workflows.
- [x] Add `ExistingWorkflowExecutor` bridge for `JobRunner`.
- **Status:** complete

### Phase 4.5: Regression and completion note

- [x] Run Phase 4 targeted tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update current status and create Phase 4 completion note.
- **Status:** complete

### Phase 5.1: New workflow discovery and drift guard update

- [x] Re-read Phase 5 spec sections and result decision matrix.
- [x] Inspect existing combined workflow, comprehensive income page, result metadata, job context, and executor bridge.
- [x] Record Phase 5 scope, safety boundaries, and implementation decisions.
- **Status:** complete

### Phase 5.2: Result matrix and page-step contracts

- [x] Add failing tests for Phase 5 result classification.
- [x] Add failing tests for prefill deduction, tax calculation, declaration readiness, and export page steps.
- [x] Implement page-owned element constants and deterministic page-step behavior.
- **Status:** complete

### Phase 5.3: New business workflows

- [x] Add failing workflow tests for success, failure, unknown, and blocked outcomes.
- [x] Implement `PrefillDeductionWorkflow`.
- [x] Implement `TaxCalculationWorkflow`.
- [x] Implement `DeclarationSubmissionWorkflow` readiness path.
- [x] Implement `ExportReportWorkflow`.
- **Status:** complete

### Phase 5.4: Fake-driver and JobRunner integration

- [x] Add failing fake-driver integration test that runs through Phase 5 in `execute_no_send`.
- [x] Add negative fake-driver tests proving Phase 5 failures stop later workflows.
- [x] Extend the existing workflow executor behind an explicit Phase 5 flag.
- [x] Keep real default CLI behavior from enabling uncalibrated Phase 5 UI actions.
- **Status:** complete

### Phase 5.5: Regression and completion note

- [x] Run Phase 5 targeted tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update current status and create Phase 5 completion note.
- **Status:** complete

### Phase 6.1: Callback and retention discovery

- [x] Re-read Phase 6 spec sections for callback delivery, evidence package, artifact manifest, summary schema, and retention.
- [x] Inspect current runner, artifact store, observability, state store, and tests.
- [x] Record Phase 6 boundaries and implementation decisions.
- **Status:** complete

### Phase 6.2: Callback outbox contract

- [x] Add failing tests for delivered callbacks, pending outbox records, retry/dead-letter state, HMAC signatures, and secret redaction.
- [x] Implement callback payload building, delivery logging, outbox persistence, retry, and dead-letter behavior.
- [x] Ensure callback failure returns callback state `pending` without changing business result.
- **Status:** complete

### Phase 6.3: Artifact manifest and callback-safe summary

- [x] Add failing tests for `artifact_manifest.json` schema and relative paths.
- [x] Add failing tests for summary callback fields and redaction.
- [x] Implement artifact manifest writer and summary schema updates.
- **Status:** complete

### Phase 6.4: Runner callback integration

- [x] Add failing job-runner tests proving callback failure keeps `succeeded` business state.
- [x] Wire artifact manifest, callback dispatch/outbox, state callback field, and troubleshooting index callback link into terminal runner paths.
- [x] Keep automated tests independent of real network calls through injectable transport.
- **Status:** complete

### Phase 6.5: Retention cleanup

- [x] Add failing retention tests for succeeded, failed, recent, pending, and dead-letter jobs.
- [x] Implement retention policy and cleanup service.
- **Status:** complete

### Phase 6.6: Regression and completion note

- [x] Run Phase 6 targeted tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update current status and create Phase 6 completion note.
- **Status:** complete

### Phase 7.1: Canary and production gate discovery

- [x] Re-read Phase 7 spec sections for machine config, runtime metadata, calibration, canary, version drift, and submit enablement.
- [x] Inspect current job runner, submit authorization, preflight, and artifact patterns.
- [x] Record Phase 7 boundaries and compatibility decisions.
- **Status:** complete

### Phase 7.2: Machine config and runtime metadata

- [x] Add failing tests for machine config validation and runner preflight failure.
- [x] Add failing tests for `summary.json` runtime metadata.
- [x] Implement `MachineConfigValidator`, `RuntimeMetadata`, and runner integration.
- **Status:** complete

### Phase 7.3: Calibration gate

- [x] Add failing tests for fake-driver skip, real `execute_no_send` calibration blocking, and real `submit` result-text calibration.
- [x] Implement `CalibrationGate` and required coverage constants.
- **Status:** complete

### Phase 7.4: Canary runner and production gate

- [x] Add failing tests for canary records, failed-canary maintenance tickets, production gate denial, and submit authorization gate integration.
- [x] Implement `CanaryRunner`, `ProductionGate`, and optional `SubmitAuthorization` integration.
- **Status:** complete

### Phase 7.5: Regression and completion note

- [x] Run Phase 7 targeted tests.
- [x] Run Phase 7 plus job-layer regression tests.
- [x] Run full unit test suite.
- [x] Run existing CLI self-check.
- [x] Update current status and create Phase 7 completion note.
- **Status:** complete

### Architecture Cleanup 2026-06-03: Boundary clarification

- [x] Move action policy primitives from `jobs` to `runtime`.
- [x] Split workflow job context into explicit runtime inputs.
- [x] Move shared component implementations to `pages/shared/components` and remove top-level `tax_rpa/components`.
- [x] Remove page-level personnel import orchestration.
- [x] Add architecture boundary tests.
- [x] Update architecture docs.
- [x] Run focused architecture tests.
- [x] Run full unit suite.
- [ ] Commit changes. `git` is not available in the current shell PATH.
- **Status:** complete except commit

### Architecture File Map 2026-06-03: Full project organization

- [x] Audit current `tax_rpa` file tree and import paths.
- [x] Remove remaining top-level utility/constant compatibility paths.
- [x] Move generic runtime helpers to `tax_rpa/runtime`.
- [x] Keep component directories only under `pages/shared/components` and `pages/<page>/components`.
- [x] Add complete current file map and trace-path documentation.
- [x] Run focused regression tests after each structural change.
- [x] Run final full unit suite after documentation/record updates.
- [x] Apply architect review follow-ups.
- **Status:** complete

### Chinese Docstring Coverage 2026-06-03: Code readability pass

- [x] Scan production Python files under `tax_rpa/` for classes, functions, and methods.
- [x] Add Chinese docstrings explaining the responsibility of each class/function/method.
- [x] Verify by AST scan that all 117 classes and 585 functions/methods have Chinese docstrings.
- [x] Delete the temporary helper script used for the bulk rewrite.
- [x] Run full unit suite.
- **Status:** complete

### Transitional File Cleanup 2026-06-03: Self-check and old-wrapper cleanup

- [x] Scan current project for duplicated self-check classes, historical wrapper functions, and stale current-doc references.
- [x] Move reusable fake app/shell/page objects to `tax_rpa/testing/self_check_app.py`.
- [x] Remove duplicated `SelfCheck*` classes from CLI modules.
- [x] Remove unused historical Win32 wrapper helpers from `from_zero_import_person_info.py`.
- [x] Update CLI/tests/docs to use the unified self-check adapter.
- [x] Run focused regression, compile check, full test suite, and CLI self-checks.
- **Status:** complete

## Key Questions

1. What is the smallest Phase 1 fake job contract that proves the job layer works without UI automation?
2. How should validation failures be represented so later callback and troubleshooting code can reuse them?
3. Which status strings and error codes must remain stable from the start?
4. What is the smallest Phase 2 policy API that can be used by current and future UI components?
5. How can high-risk submit be denied by default without breaking existing non-submit workflows?
6. What is the smallest Phase 3 evidence package that lets an operator inspect a forced failure without searching the job folder?
7. How can screenshots be tested deterministically without requiring an active Windows desktop?
8. What is the smallest workflow job-context API that can wrap existing workflows without pulling UI details into `jobs/`?
9. Which side-effect markers must exist before Phase 5 adds prefill, calculation, submit, and export?
10. How should Phase 5 reuse the workflow job context for prefill, tax calculation, declaration readiness, and export?
11. How should Phase 6 callback outbox and retention consume the Phase 5 summaries and result matrix without changing business state?
12. What calibration and canary evidence should Phase 7 require before enabling any real `submit` path?

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Keep Phase 1 separate from UI workflow implementation | Prevents new job orchestration from accidentally changing tax-client behavior. |
| Use TDD for each Phase 1 module | The job layer is contract-heavy and must not drift from the spec. |
| Keep planning files at repo root | They are persistent session memory and should survive context resets. |
| Continue with Phase 2 in the same planning files | Preserves the project history and makes phase-to-phase drift visible. |
| Implement Phase 3 as a job-layer observability service first | Gives the runner and later workflows a stable artifact contract before migrating UI workflows. |
| Inject screenshot capture in tests | Unit tests must not depend on a live Windows desktop, screen state, or PIL ImageGrab availability. |
| Migrate Phase 4 with optional job context | Existing CLI/self-check paths keep working while job-runner paths gain observability and side-effect journals. |
| Keep result matrix logic outside page components | Workflows classify business outcomes, while page components stay responsible for UI sensing and low-level evidence. |
| Do not export `ExistingWorkflowExecutor` from `tax_rpa.jobs.__init__` | Exporting it at package import time creates a circular dependency through workflows, app, components, and jobs. |
| Keep Phase 5 fake-driver first and behind an explicit executor flag | The spec requires real-client calibration before enabling real `execute_no_send` through uncalibrated prefill, calculate, and export actions. |
| Track callback delivery separately from business state | The spec forbids changing `succeeded` or `failed` business states when callback delivery fails. |
| Keep callback transport injectable | Tests and unattended runs must not depend on live middle-platform network availability. |
| Keep Phase 7 gates deterministic and injectable | Unit tests must not require the real tax client, live desktop, OCR engine, or `git` command. |
| Make machine config preflight opt-in at the runner boundary | Existing fake-driver and legacy tests stay compatible while production job-runner paths can require `machine_config.json`. |
| Wire production gate into submit authorization as an optional service | Deployments can enforce canary-reviewed submit enablement without breaking older authorization unit tests. |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Artifact JSON path used Windows backslashes | 1 | Serialize `Path` values with `as_posix()` in `artifact_store.py`. |
| Locked diagnostic file was unreadable | 1 | Use a separate `.mutex` file for the OS lock and keep `runner.lock.json` readable. |
| `git diff --stat` unavailable because `git` is not installed in shell PATH | 1 | Record the environment limit and rely on persistent planning files plus test output for this session. |
| Package-level export of `ExistingWorkflowExecutor` created a circular import | 1 | Keep the executor importable via `tax_rpa.jobs.existing_workflow_executor` only. |

## Notes

- Re-read this plan before each new phase.
- After every meaningful discovery, update `findings.md`.
- After each implementation or test run, update `progress.md`.
- Phase 7 code support is complete; real production enablement still requires deployment-machine calibration artifacts, canary runs, and operator-reviewed submit checklist files.
