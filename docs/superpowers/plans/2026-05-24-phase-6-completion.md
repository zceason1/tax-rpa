# Phase 6 Completion Note

Phase 6 callback and retention is complete.

Completed scope:

- Added `CallbackOutbox` for:
  - delivered callback attempts;
  - pending callback outbox records;
  - retry attempts;
  - dead-letter state;
  - optional HMAC signature headers;
  - callback secret redaction.
- Added `ArtifactManifestWriter` for `artifact_manifest.json`.
- Added callback-safe `summary.json` fields:
  - `business_status`;
  - `callback_state`;
  - structured `error`;
  - `callback_outbox_record`;
  - artifact manifest path.
- Added `RetentionCleaner` and default `RetentionPolicy`.
- Updated `JobRunner` terminal finalization to write:
  - `summary.json`;
  - `artifact_manifest.json`;
  - `logs/callbacks.jsonl`;
  - `callback_outbox.json` when delivery is pending or dead-lettered;
  - callback outbox links in `troubleshooting_index.json`.
- Added `StateStore.update_callback_delivery_state()` so callback delivery state updates `state.json` without creating a business state transition.

Verified behavior:

- HTTP 2xx callback responses mark callback state as `delivered`.
- HTTP 5xx responses create `callback_outbox.json` with `callback_state="pending"`.
- Old pending callback records move to `dead_letter` after the configured retry window.
- Callback failure does not change terminal business state.
- `state.json` can remain `succeeded` while `callback_delivery_state` is `pending`.
- Retention deletes expired succeeded and failed jobs.
- Retention preserves jobs with callback state `pending` or `dead_letter`.
- Artifact manifest paths are job-relative and include checksums.

Commands:

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_callback_outbox tests.test_artifact_manifest_schema tests.test_phase6_job_runner_callback tests.test_retention -v`
- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_callback_outbox tests.test_artifact_manifest_schema tests.test_phase6_job_runner_callback tests.test_retention tests.test_job_runner tests.test_job_observability tests.test_artifact_store tests.test_state_store tests.test_existing_workflow_executor tests.test_phase5_executor_integration -v`
- `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v`
- `.\\.venv\\Scripts\\python.exe -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate`

Results:

- Phase 6 tests: 7 passed.
- Phase 6 targeted regression: 22 passed.
- Full unit suite: 176 passed.
- Existing CLI self-check: success.

Self-check summary:

- `C:\rpa-tax-poc\artifacts\person_import_20260524_152845\tax_workflow_summary.json`

Implementation notes:

- Callback transport is injectable for tests and controlled deployments.
- If no `callback_url` is configured, callback state is `not_configured`.
- `callback_secret` is accepted by `JobRunner` and used only for HMAC signing; it is redacted from logs and outbox records.
- Callback delivery state is intentionally separate from the job state machine.

Regression fixed during Phase 6:

- A first implementation of callback state updates accidentally stopped normal `StateStore.transition()` calls from appending to `logs/state_transitions.jsonl`.
- The fix restores transition logging for business state transitions and keeps callback updates as state-only writes.

Environment note:

- `git` is not available in the current shell PATH, so `git diff --stat` could not run.
- Development traceability for this phase is recorded in `task_plan.md`, `findings.md`, and `progress.md`.

Production readiness note:

- The full unattended tax RPA is still not production-ready.
- Phase 6 completes callback and retention foundations.
- Next phase is Phase 7: canary runner, version drift checks, calibration evidence, and production gate.
