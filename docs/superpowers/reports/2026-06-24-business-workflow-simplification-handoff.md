# Business Workflow Simplification Handoff

Date: 2026-06-24

Audience: Windows validation agent or engineer reviewing the workflow simplification refactor.

## Purpose

This document summarizes the current refactor so a Windows-side agent can review the exact risk areas and run the correct validation. The macOS implementation and unit regression are complete, but real Windows RPA behavior has not been validated.

Current architecture remains:

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

The refactor is intentionally limited to workflow-layer boilerplate. It does not redesign Page, Component, Element, Driver, JobRunner, callbacks, or production gates.

## What Changed

### New workflow support files

- `tax_rpa/workflows/base.py`
  - Adds `BusinessWorkflow`.
  - Owns standalone lifecycle execution through `AppLifecycleWorkflow`.
  - Provides `run_on_app(app) -> execute(app)`.
  - Preserves lifecycle failure metadata: `error`, `error_type`, `error_code`, `evidence`, side-effect flags, and `retry_allowed`.

- `tax_rpa/workflows/context.py`
  - Adds `WorkflowContext`.
  - Centralizes `StepRunner` invocation.
  - Builds `WorkflowResult` from explicit `steps` and `evidence`.
  - Rejects non-`StepResult` operations before `JobStepRunner` can read `result.name/status/error`.

- `tax_rpa/workflows/app_factory.py`
  - Adds lazy default creation of the real `TaxClientApp`.
  - This avoids importing Windows-only drivers when fake-driver tests import workflow modules on macOS.

### Migrated workflows

The following workflows now inherit `BusinessWorkflow` and implement `execute(app)`:

- `ImportPersonInfoWorkflow`
- `ImportSalaryIncomeWorkflow`
- `UpdateSpecialDeductionWorkflow`
- `PrefillDeductionWorkflow`
- `TaxCalculationWorkflow`
- `DeclarationSubmissionWorkflow`
- `ExportReportWorkflow`

Important preserved behavior:

- Existing public constructor positional order is preserved.
- Page-opening steps still run directly, for example `OpenPersonInfoPageStep(app.shell()).run()`.
- Only `StepResult`-returning business operations run through `self.context.step(...)`.
- Workflow-specific evidence keys remain explicit:
  - personnel: `import_file`, `validation_result`, `import_result`, `submit_result`
  - salary: `open_form`, `import_file`
  - prefill: `open_form`, `prefill`
  - export: `readiness`, `export`, `export_status`

### Combined workflow factory change

`CombinedTaxWorkflow` no longer inspects factory signatures with `inspect.signature`.

It now always calls factories as:

```python
factory(
    self.config,
    self.logger,
    step_runner=self.step_runner,
    runtime_options=self.runtime_options,
)
```

Production CLI factories and test factories were updated to accept these keyword arguments.

### Import and cross-platform compatibility changes

The macOS environment surfaced import-time Windows dependency problems. To make fake-driver regression executable outside Windows, several imports were made lazy or guarded:

- workflow package exports are lazy in `tax_rpa/workflows/__init__.py`
- page package exports are lazy in:
  - `tax_rpa/pages/comprehensive_income/__init__.py`
  - `tax_rpa/pages/special_deduction/__init__.py`
- CLI admin elevation is centralized in `tax_rpa/cli/windows_admin.py`
- Windows-only driver APIs are guarded in:
  - `tax_rpa/drivers/mouse_driver.py`
  - `tax_rpa/drivers/win32_driver.py`
- `pyautogui` in message dialog closing is imported only when keyboard fallback is actually needed.

These changes should not change Windows behavior, but they are a Windows validation risk because they touch low-level import and launch paths.

### Small path fixes

- `tax_rpa/jobs/artifact_store.py`
  - Uses resolved root when returning job-relative paths, fixing `/var` vs `/private/var` path mismatch on macOS.

- `tax_rpa/app/tax_client_app.py`
  - `build_launch_decision()` now serializes configured app paths with `PureWindowsPath`.

- `tax_rpa/drivers/win32_driver.py`
  - `.lnk` launch paths passed into `ShellExecuteW` are serialized with Windows path separators.

## Mac Validation Already Performed

Python used:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
```

Important note: the default `python` in this environment was Python 3.9 and cannot run this project because the code uses Python 3.10+ syntax such as `str | None`.

Commands run successfully:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m unittest tests.test_workflow_context -v
```

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m unittest tests.test_workflow_composition tests.test_existing_workflow_executor tests.test_phase5_executor_integration tests.test_job_runner tests.test_from_zero_import_person_info tests.test_workflow_context -v
```

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m unittest discover -s tests -v
```

Full macOS result:

```text
Ran 236 tests
OK
```

This proves code-level and fake-driver semantics only. It does not prove real Windows RPA execution.

## Key Risk Items For Windows Review

### 1. Lifecycle ownership regression

Risk:

`BusinessWorkflow.run()` now owns standalone lifecycle for all migrated workflows. `CombinedTaxWorkflow.run()` still owns lifecycle for composed runs and should call child `run_on_app(app)`, not child `run()`.

What can break:

- duplicate app start/reset/login
- child workflow starting a second client lifecycle
- action policy not attached to recovered app

Review:

- Confirm `CombinedTaxWorkflow.run()` starts lifecycle once.
- Confirm child workflows are executed through `run_on_app(lifecycle.app)`.
- Confirm recovery path still calls `_reset_and_wait_for_login()` only for retryable environment failures.

Target tests:

```powershell
python -m unittest tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_runs_lifecycle_once_then_business_workflows_in_order tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_does_not_reset_between_successful_business_workflows -v
```

### 2. StepRunner observability regression

Risk:

`WorkflowContext.step()` is now the only workflow-level path into `JobStepRunner` for business steps.

What can break:

- `logs/steps.jsonl` missing workflow step events
- `logs/step_journal.jsonl` missing side-effect markers
- result matrix rows missing or classified incorrectly
- page-opening steps accidentally passed into `JobStepRunner`

Review:

- Confirm only `StepResult` operations call `context.step()`.
- Confirm open-page calls are still direct.
- Confirm `matrix_step` values remain:
  - `personnel_import`
  - `special_deduction_update`
  - `salary_income_import`
  - `prefill_deduction`
  - `tax_calculation`
  - `declaration_submission_readiness`
  - `export_report`

Target tests:

```powershell
python -m unittest tests.test_workflow_context tests.test_workflow_job_context tests.test_existing_workflow_executor -v
```

Windows-side artifact check:

- Open the job artifact root.
- Inspect `logs/steps.jsonl`.
- Confirm key business rows have `result_matrix.matrix_step`.
- Inspect `logs/step_journal.jsonl`.
- Confirm side-effect expected/started/committed markers still appear for import/update/prefill/export actions.

### 3. Personnel import branch safety

Risk:

`ImportPersonInfoWorkflow` is the most safety-sensitive workflow. It has special submit behavior and side-effect semantics.

Must preserve:

```text
open person info page
import person file
wait import result
if ready_to_submit:
  submit import data
  if submit failed:
    side_effect_started=True
    side_effect_committed=True
    retry_allowed=False
  wait submit result
  if still ready_to_submit:
    UNKNOWN_RESULT/person_import_result_unknown
else:
  use validation result as final result
```

What can break:

- retry is incorrectly allowed after submit/import side effects
- post-submit `ready_to_submit` is treated as success
- evidence keys change and failure package becomes harder to inspect

Review:

- Confirm submit-failure branch forces `side_effect_started=True`, `side_effect_committed=True`, `retry_allowed=False`.
- Confirm post-submit `ready_to_submit` maps to `UNKNOWN_RESULT` and `person_import_result_unknown`.
- Confirm evidence keys include `submit_result` only when the submit branch ran.

Target tests:

```powershell
python -m unittest tests.test_component_architecture tests.test_page_step_architecture tests.test_existing_workflow_executor tests.test_from_zero_import_person_info -v
```

### 4. Constructor compatibility

Risk:

Existing workflow constructors had different optional positional argument orders. The refactor preserved them intentionally.

Current orders:

```python
# earlier workflows
ImportPersonInfoWorkflow(config, logger, app_factory=None, runtime_options=None, step_runner=None, reset=False)
ImportSalaryIncomeWorkflow(config, logger, app_factory=None, runtime_options=None, step_runner=None)
UpdateSpecialDeductionWorkflow(config, logger, app_factory=None, runtime_options=None, step_runner=None)

# phase 5 workflows
PrefillDeductionWorkflow(config, logger, runtime_options=None, step_runner=None, app_factory=None)
TaxCalculationWorkflow(config, logger, runtime_options=None, step_runner=None, app_factory=None)
DeclarationSubmissionWorkflow(config, logger, runtime_options=None, step_runner=None, app_factory=None)
ExportReportWorkflow(config, logger, runtime_options=None, step_runner=None, app_factory=None)
```

What can break:

- positional third arg interpreted as the wrong dependency
- CLI/test factories passing kwargs into constructors that do not accept them

Target test:

```powershell
python -m unittest tests.test_workflow_context.WorkflowContextTests tests.test_workflow_context.BusinessWorkflowTests -v
```

### 5. Factory invocation change

Risk:

`CombinedTaxWorkflow` now unconditionally passes `step_runner` and `runtime_options` into workflow factories.

What can break:

- any unupdated factory with signature `lambda config, logger: ...`
- external code that injects custom factories without accepting `**kwargs`

Review:

Search:

```powershell
rg -n "workflow_factories=|lambda config, logger|def _workflow_factories|_accepts_parameter|inspect.signature" tax_rpa tests
```

Expected:

- no `_accepts_parameter`
- no `inspect.signature` in `combined_tax_workflow.py`
- any factory passed into `CombinedTaxWorkflow` accepts `step_runner/runtime_options` or `**kwargs`

Target tests:

```powershell
python -m unittest tests.test_workflow_composition tests.test_combined_cli tests.test_new_workflow_cli -v
```

### 6. Windows import and launch path behavior

Risk:

Several modules now guard or delay Windows-only imports. This fixed macOS fake-driver tests but must be checked on Windows.

Review:

- `ctypes.windll` and `ctypes.WinDLL` paths should still bind on Windows.
- `Win32Driver.launch_client()` should still call `ShellExecuteW` correctly for `.lnk`.
- CLI admin relaunch should still show UAC through `tax_rpa/cli/windows_admin.py`.
- `TaxClientApp` should still create real `Win32Driver()` when no fake is injected.

Target tests:

```powershell
python -m unittest tests.test_driver_boundaries tests.test_reset_app tests.test_auto_login_app tests.test_win32_driver_process_termination -v
```

Manual checks:

- Run CLI with `--self-check --no-self-elevate`.
- Run CLI without `--no-self-elevate` from a non-admin shell and confirm UAC relaunch still works.
- Run a configured `.lnk` client launch path and confirm shortcut launch still works.

### 7. Real file dialog and message dialog behavior

Risk:

Message dialog fallback imports `pyautogui` only when a keyboard fallback is needed. File dialog still imports `pyautogui` in fallback paths.

What can break:

- keyboard fallback for dialogs if `pyautogui` is missing on Windows
- cancel/confirm dialog close behavior
- file dialog typing/submission

Review:

- Confirm Windows environment has `pyautogui` installed if dialog keyboard fallback is expected.
- Confirm injected mouse/Win32 paths still work.
- Confirm `ActionPolicy` still blocks submit in inspect/no-send modes.

Target tests:

```powershell
python -m unittest tests.test_driver_boundaries tests.test_action_policy_components -v
```

### 8. Artifact path behavior

Risk:

`ArtifactStore.write_json()` now returns paths relative to `self.root.resolve()`. This fixed macOS symlink path behavior.

What can break:

- path relation handling if Windows paths are mixed across drives
- artifact manifest path serialization

Target tests:

```powershell
python -m unittest tests.test_artifact_store tests.test_job_observability tests.test_artifact_manifest_schema -v
```

### 9. Real Windows RPA validation remains mandatory

macOS unit tests cannot validate:

- UAC elevation
- Win32 process lookup and launch
- real window foreground behavior
- UIA/OCR recognition
- mouse coordinates
- real file dialogs
- tax-client popup text/version drift

Windows validation must include at least:

```powershell
python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

Then run the project-documented job-runner inspect/dry-run path with target manifest and machine config.

Then run execute-no-send canary through the current production gate/canary process.

Do not claim submit compatibility until Windows canary, calibration, and operator checklist gates pass.

## Recommended Windows Review Sequence

1. Confirm environment:

```powershell
python --version
python -m unittest tests.test_workflow_context -v
```

Python must be 3.10+.

2. Run workflow-level regression:

```powershell
python -m unittest tests.test_workflow_composition tests.test_existing_workflow_executor tests.test_phase5_executor_integration tests.test_job_runner tests.test_from_zero_import_person_info tests.test_workflow_context -v
```

3. Run full unit suite:

```powershell
python -m unittest discover -s tests -v
```

4. Run CLI self-check:

```powershell
python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

5. Run elevated path smoke:

```powershell
python -m tax_rpa.cli.run_tax_workflow --self-check
```

Expected: if not already admin, Windows UAC relaunch is requested.

6. Run real-client inspect/no-send path using the deployment manifest and machine config.

Expected:

- client starts or binds
- login wait completes
- pages can be opened
- no real submit/import side effects occur in inspect-only mode
- job artifacts are written

7. Run execute-no-send canary through the current production gate/canary entrypoint.

Expected:

- no submit action
- job artifacts and logs are written
- operator can inspect canary record

## Files To Review First

Core refactor:

- `tax_rpa/workflows/base.py`
- `tax_rpa/workflows/context.py`
- `tax_rpa/workflows/app_factory.py`
- `tax_rpa/workflows/combined_tax_workflow.py`
- `tax_rpa/workflows/import_person_info_workflow.py`
- `tax_rpa/workflows/import_salary_income_workflow.py`
- `tax_rpa/workflows/update_special_deduction_workflow.py`
- `tax_rpa/workflows/prefill_deduction_workflow.py`
- `tax_rpa/workflows/tax_calculation_workflow.py`
- `tax_rpa/workflows/declaration_submission_workflow.py`
- `tax_rpa/workflows/export_report_workflow.py`

Windows-sensitive support changes:

- `tax_rpa/cli/windows_admin.py`
- `tax_rpa/cli/run_tax_workflow.py`
- `tax_rpa/cli/import_salary_income.py`
- `tax_rpa/cli/update_special_deduction.py`
- `tax_rpa/cli/from_zero_import_person_info.py`
- `tax_rpa/cli/debug_person_info_page.py`
- `tax_rpa/drivers/mouse_driver.py`
- `tax_rpa/drivers/win32_driver.py`
- `tax_rpa/pages/shared/components/message_dialog.py`
- `tax_rpa/app/tax_client_app.py`
- `tax_rpa/jobs/artifact_store.py`

Tests:

- `tests/test_workflow_context.py`
- `tests/test_workflow_composition.py`
- `tests/test_existing_workflow_executor.py`
- `tests/test_phase5_executor_integration.py`
- `tests/test_from_zero_import_person_info.py`
- `tests/test_driver_boundaries.py`

## Expected Review Outcome

The Windows agent should report:

- unit test result
- CLI self-check result
- elevated relaunch result
- inspect/no-send real-client result
- execute-no-send canary result
- any differences in artifacts/logs, especially `logs/steps.jsonl`, `logs/step_journal.jsonl`, `summary.json`, and `artifact_manifest.json`

Until the Windows checks pass, the implementation status should remain:

```text
macOS semantic regression passed; real Windows RPA execution not yet verified
```
