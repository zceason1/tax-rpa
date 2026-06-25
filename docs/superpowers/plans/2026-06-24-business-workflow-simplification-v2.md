# Business Workflow Simplification V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor workflow-layer boilerplate into small reusable support classes so concrete business workflows are easier to read, while preserving current RPA behavior, job artifacts, and safety semantics.

**Architecture:** Keep the current architecture boundary: `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`. Add `BusinessWorkflow` and `WorkflowContext` only inside `tax_rpa/workflows` to centralize lifecycle wrapping, step execution, and `WorkflowResult` construction. Do not flatten the page/component/driver layers and do not introduce a workflow DSL.

**Tech Stack:** Python `unittest`, dataclasses, existing `StepResult`, `WorkflowResult`, `WorkflowRuntimeOptions`, `StepRunner`, `DirectStepRunner`, `JobStepRunner`, fake app/page tests, Windows-only canary/manual validation after code-level regression.

---

## Executive Summary

The current business layer is not structurally wrong, but `tax_rpa/workflows` is verbose. Most concrete workflows repeat:

- constructor plumbing for `config`, `logger`, `app_factory`, `runtime_options`, `step_runner`, and `reset`
- standalone lifecycle execution through `AppLifecycleWorkflow`
- `_run_step()` wrappers for optional `StepRunner`
- manual `WorkflowResult(...)` construction
- repeated failure/evidence/side-effect propagation

The refactor should make each concrete workflow read as business order:

```text
open page
run step
branch on business result
return workflow result
```

This is a semantics-preserving refactor. Shorter code is not enough; the important part is preserving:

- `WorkflowResult` metadata
- side-effect and retry safety
- `JobStepRunner` observability
- `CombinedTaxWorkflow` single-owned lifecycle
- personnel import special cases
- CLI/debug compatibility

## Validation Boundary

This repository is currently being edited on macOS. macOS validation can only prove code-level and fake-driver semantics:

- workflow order
- result wrapping
- side-effect/retry propagation
- `JobRunner` fake app behavior
- `JobStepRunner` log path integration

macOS cannot prove real RPA execution:

- Windows UAC and administrator relaunch
- Win32 window binding
- UIA/OCR recognition against the real tax client
- mouse coordinate correctness
- real file dialog behavior
- real tax-client popup text/version drift

Completion states must be named clearly:

```text
macOS full unit suite green
  -> code semantics verified, not RPA execution verified

Windows self-check green
  -> fake-client Windows entry path verified

Windows inspect_only green
  -> real client navigation/recognition smoke verified

Windows execute_no_send canary green
  -> real no-submit workflow candidate verified

Windows submit
  -> allowed only after calibration, canary, and operator review gates
```

This refactor must not be considered production-ready without Windows validation.

## Design

### New `WorkflowContext`

File: `tax_rpa/workflows/context.py`

Responsibilities:

- run a named business step through `StepRunner` when provided
- fall back to direct execution when no runner is provided
- construct `WorkflowResult` from a `StepResult`
- allow explicit side-effect and retry overrides

It must not know about `JobRunner`, `JobManifest`, artifacts, callbacks, pages, or drivers.

`WorkflowContext.step()` is only for operations that return `StepResult`. Do not use it for open-page steps such as `OpenPersonInfoPageStep(...).run()` because those return page objects. Page-opening steps remain direct calls in concrete workflows unless a separate helper is added that does not call `StepRunner`.

### New `BusinessWorkflow`

File: `tax_rpa/workflows/base.py`

Responsibilities:

- provide shared lifecycle/result helper behavior without forcing every workflow into the same positional constructor ABI
- create `WorkflowContext`
- provide `run()` for standalone/debug execution
- call `AppLifecycleWorkflow` only in standalone `run()`
- provide `run_on_app(app)` as the already-logged-in execution entry
- delegate concrete business order to `execute(app)`

It must not encode business-specific branches such as personnel submit behavior or export readiness decisions.

Important: existing workflow constructors do not all share the same positional optional argument order. Phase 5 workflows use `runtime_options, step_runner, app_factory`; earlier workflows use `app_factory, runtime_options, step_runner`. The refactor must not silently reinterpret positional arguments. Either each concrete workflow keeps its current `__init__` signature and delegates to a protected base initializer with keywords, or the project first performs a separate constructor API cleanup with explicit tests.

### Concrete Workflows

Concrete workflows inherit `BusinessWorkflow` and implement `execute(app)`.

Business branches stay explicit in concrete workflows. This is especially important for `ImportPersonInfoWorkflow`:

```text
wait_import_result == ready_to_submit
-> submit_import_data
-> wait_submit_result == ready_to_submit
-> UNKNOWN_RESULT/person_import_result_unknown
```

### `CombinedTaxWorkflow`

`CombinedTaxWorkflow` keeps owning the lifecycle for composed runs:

```text
CombinedTaxWorkflow.run()
  -> AppLifecycleWorkflow once
  -> child.run_on_app(app)
  -> child.run_on_app(app)
```

It must not call child `run()` because that would start lifecycle again.

After all real and test factories accept `**kwargs`, `_build_business_workflow()` can stop using signature introspection.

## Risk Controls

### Result Metadata Drift

`WorkflowResult` is a production contract. Helpers must preserve:

- `ok`
- `name`
- `status`
- `steps`
- `evidence`
- `error`
- `error_type`
- `error_code`
- `side_effect_started`
- `side_effect_committed`
- `retry_allowed`

Regression risk: job summaries, callbacks, result matrix classification, and troubleshooting packages change meaning.

### Side-Effect And Retry Safety

Do not infer side-effect fields only from the final step. A workflow can fail while waiting for a result after an earlier import/submit already changed external state.

Personnel submit-failure branch must force:

```python
side_effect_started=True
side_effect_committed=True
retry_allowed=False
```

even if `SubmitImportDataStep` returns a raw failed click result without side-effect flags.

### Job Observability

`WorkflowContext.step()` must call `step_runner.run_step(...)` when provided. This preserves:

- `logs/steps.jsonl`
- `logs/step_journal.jsonl`
- result matrix rows
- side-effect journal markers

### Lifecycle Ownership

Standalone workflow:

```text
workflow.run() -> lifecycle -> execute(app)
```

Composed workflow:

```text
CombinedTaxWorkflow.run() -> lifecycle once -> child.run_on_app(app)
```

Tests must verify no duplicated `start`, `wait_login`, or `reset` events in successful composed runs.

### Constructor Compatibility

Existing workflow optional constructor parameters are not uniform:

```python
# ImportPersonInfoWorkflow / ImportSalaryIncomeWorkflow / UpdateSpecialDeductionWorkflow
def __init__(config, logger, app_factory=None, runtime_options=None, step_runner=None, ...)

# Phase 5 workflows
def __init__(config, logger, runtime_options=None, step_runner=None, app_factory=None)
```

Do not replace all concrete constructors with one positional order in this refactor. Preserve each workflow's existing positional ABI, then delegate internally using keyword arguments:

```python
class PrefillDeductionWorkflow(BusinessWorkflow):
    name = "prefill_deduction_workflow"

    def __init__(
        self,
        config,
        logger,
        runtime_options=None,
        step_runner=None,
        app_factory=None,
    ):
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )
```

Narrowing constructors to keyword-only or normalizing all positional optional argument order is a separate API cleanup and is out of scope.

### Factory Compatibility

Before removing `CombinedTaxWorkflow` factory introspection, update all real and fake factories to accept `**kwargs`.

Real CLI files:

- `tax_rpa/cli/run_tax_workflow.py`
- `tax_rpa/cli/import_salary_income.py`
- `tax_rpa/cli/update_special_deduction.py`

Job executor factories in `tax_rpa/jobs/existing_workflow_executor.py` already accept `step_runner` and `runtime_options`; keep them compatible.

### Avoid Over-Abstraction

Do not add:

- workflow DSL
- declarative step lists
- decorators for flow control
- metaclass registration
- hidden conditional execution engine

The workflow should stay ordinary Python control flow.

## File Plan

Create:

- `tax_rpa/workflows/context.py`
- `tax_rpa/workflows/base.py`
- `tests/test_workflow_context.py`

Modify:

- `tax_rpa/workflows/update_special_deduction_workflow.py`
- `tax_rpa/workflows/tax_calculation_workflow.py`
- `tax_rpa/workflows/declaration_submission_workflow.py`
- `tax_rpa/workflows/import_salary_income_workflow.py`
- `tax_rpa/workflows/prefill_deduction_workflow.py`
- `tax_rpa/workflows/export_report_workflow.py`
- `tax_rpa/workflows/import_person_info_workflow.py`
- `tax_rpa/workflows/combined_tax_workflow.py`
- `tax_rpa/workflows/__init__.py`
- `tax_rpa/cli/run_tax_workflow.py`
- `tax_rpa/cli/import_salary_income.py`
- `tax_rpa/cli/update_special_deduction.py`
- `docs/architecture_file_map.md`
- `docs/learning/templates/new_page_step_workflow_template.md`

Do not modify:

- `tax_rpa/pages/**`
- `tax_rpa/drivers/**`
- `tax_rpa/jobs/runner.py`
- `tax_rpa/jobs/workflow_step_runner.py`
- `tax_rpa/runtime/result.py`

## Implementation Tasks

### Task 1: Add WorkflowContext

**Files:**
- Create: `tests/test_workflow_context.py`
- Create: `tax_rpa/workflows/context.py`

- [ ] **Step 1: Write failing tests for step execution and result wrapping**

Add tests for:

- `WorkflowContext.step()` calls `step_runner.run_step(...)` with workflow, step, matrix step, and side-effect flag
- `WorkflowContext.step()` rejects operations that do not return `StepResult` without or before `JobStepRunner` accesses result fields
- `WorkflowContext.step()` rejects non-`StepResult` operations in all paths: no runner, fake runner, and real `JobStepRunner`
- `result_from_step()` copies all `WorkflowResult`-compatible fields from the selected `StepResult`
- `result_from_step()` requires explicit `steps` and `evidence`, preserving workflow-specific evidence shape
- `result_from_step()` accepts explicit side-effect and retry overrides
- `failed_from_step()` accepts explicit side-effect and retry overrides

Minimum test cases:

```python
def test_failed_from_step_accepts_explicit_side_effect_overrides(self):
    submit = StepResult(
        ok=False,
        name="submit",
        status="failed",
        retry_allowed=True,
    )

    result = ctx.failed_from_step(
        submit,
        steps=[submit],
        evidence={"submit": {}},
        side_effect_started=True,
        side_effect_committed=True,
        retry_allowed=False,
    )

    self.assertFalse(result.ok)
    self.assertTrue(result.side_effect_started)
    self.assertTrue(result.side_effect_committed)
    self.assertFalse(result.retry_allowed)
```

- [ ] **Step 2: Implement `WorkflowContext`**

Required API:

```python
@dataclass(frozen=True)
class WorkflowContext:
    workflow: str
    config: PersonImportConfig
    logger: Any
    runtime_options: WorkflowRuntimeOptions
    step_runner: StepRunner | None = None

    def step(...): ...
    def result_from_step(...): ...
    def failed_from_step(...): ...
```

`step()` must validate the operation result before `JobStepRunner` can access `result.name`, `result.status`, or other `StepResult` fields. Wrap the operation with a checked callable before passing it into `runner.run_step(...)`:

```python
def checked_operation() -> StepResult:
    result = operation()
    if not isinstance(result, StepResult):
        raise TypeError("WorkflowContext.step operations must return StepResult")
    return result

if self.step_runner:
    return self.step_runner.run_step(
        workflow=self.workflow,
        step=step,
        operation=checked_operation,
        matrix_step=matrix_step,
        side_effect_step=side_effect_step,
    )

return checked_operation()
```

This protects against accidentally wrapping `Open*PageStep(...).run()` calls, which return page objects and cannot be logged by `JobStepRunner`.

`result_from_step()` and `failed_from_step()` must support:

```python
side_effect_started: bool | None = None
side_effect_committed: bool | None = None
retry_allowed: bool | None = None
```

- [ ] **Step 3: Run tests**

```bash
python -m unittest tests.test_workflow_context -v
```

Expected: pass.

### Task 2: Add BusinessWorkflow Base

**Files:**
- Modify: `tests/test_workflow_context.py`
- Create: `tax_rpa/workflows/base.py`

- [ ] **Step 1: Write lifecycle wrapper tests**

Test that:

- `run()` starts lifecycle once for standalone usage
- `run()` merges lifecycle steps and business steps
- lifecycle failure preserves `error_type`, `error_code`, side-effect flags, retry flag, and evidence
- existing concrete workflow constructors remain positional-compatible for their current signatures

Preserving full lifecycle failure metadata is an intentional compatibility fix. Existing workflow implementations may drop some fields when lifecycle startup fails; the refactor should normalize this instead of reproducing the truncation. Represent lifecycle failure evidence directly as `lifecycle_result.evidence` in the returned `WorkflowResult.evidence`, not under a new generic wrapper key, unless an existing workflow already uses a more specific key.

- [ ] **Step 2: Implement `BusinessWorkflow` support methods**

Do not force a single public positional constructor onto all workflows. Implement a protected initializer and keep public constructors in concrete workflows:

```python
class BusinessWorkflow:
    name = ""

    def _init_workflow(
        self,
        *,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: StepRunner | None = None,
        reset: bool = False,
    ) -> None:
        ...
```

Keep:

```python
def run(self) -> WorkflowResult: ...
def run_on_app(self, app: Any) -> WorkflowResult:
    return self.execute(app)
def execute(self, app: Any) -> WorkflowResult:
    raise NotImplementedError
```

Concrete workflows call `_init_workflow(...)` from their existing `__init__` signature.

- [ ] **Step 3: Run tests**

```bash
python -m unittest tests.test_workflow_context tests.test_app_lifecycle_workflow -v
```

Expected: pass.

### Task 3: Migrate Simple Workflows First

**Files:**
- Modify: `tax_rpa/workflows/update_special_deduction_workflow.py`
- Modify: `tax_rpa/workflows/tax_calculation_workflow.py`
- Modify: `tax_rpa/workflows/declaration_submission_workflow.py`

- [ ] **Step 1: Run baseline tests**

```bash
python -m unittest tests.test_special_deduction_steps tests.test_phase5_workflows tests.test_workflow_composition -v
```

Expected: pass before changes.

- [ ] **Step 2: Migrate one workflow at a time**

Each migrated workflow should:

- inherit `BusinessWorkflow`
- define `name`
- implement `execute(app)`
- use `self.context.step(...)` only for operations returning `StepResult`
- call `Open*PageStep(...).run()` directly because those return page objects
- return via `self.context.result_from_step(...)` or `failed_from_step(...)`
- preserve existing evidence keys in returned `WorkflowResult`

Do not change page steps or page objects.

- [ ] **Step 3: Run tests after each workflow**

```bash
python -m unittest tests.test_special_deduction_steps tests.test_phase5_workflows -v
```

Expected: pass after each individual migration.

### Task 4: Migrate Multi-Step Workflows

**Files:**
- Modify: `tax_rpa/workflows/import_salary_income_workflow.py`
- Modify: `tax_rpa/workflows/prefill_deduction_workflow.py`
- Modify: `tax_rpa/workflows/export_report_workflow.py`

- [ ] **Step 1: Migrate `ImportSalaryIncomeWorkflow`**

Preserve:

- open salary form before import
- salary file path from `config.import_file("salary_income")`
- `matrix_step="salary_income_import"`
- `side_effect_step=True`
- side-effect and retry metadata from final import step
- existing evidence keys: `open_form`, `import_file`

- [ ] **Step 2: Migrate `PrefillDeductionWorkflow`**

Preserve:

- salary form open before prefill
- `allow_skip_personal_pension` from `runtime_options`
- `matrix_step="prefill_deduction"`
- side-effect behavior
- existing evidence keys: `open_form`, `prefill`

- [ ] **Step 3: Migrate `ExportReportWorkflow`**

Preserve:

- declaration readiness before export
- `run_mode` passed into readiness and export steps
- readiness failure stops export
- `matrix_step="export_report"`
- existing evidence keys: `readiness`, `export`, `export_status`

- [ ] **Step 4: Run tests**

```bash
python -m unittest tests.test_comprehensive_income_steps tests.test_phase5_workflows tests.test_phase5_executor_integration -v
```

Expected: pass.

### Task 5: Migrate ImportPersonInfoWorkflow Last

**Files:**
- Modify: `tax_rpa/workflows/import_person_info_workflow.py`
- Modify: personnel workflow tests if needed

- [ ] **Step 1: Add focused submit-failure side-effect test before migration**

Create or update a test so that:

- import file succeeds
- first wait returns `ready_to_submit`
- submit returns `StepResult(ok=False, status="failed", retry_allowed=True)` without side-effect flags
- workflow result has `side_effect_started=True`
- workflow result has `side_effect_committed=True`
- workflow result has `retry_allowed=False`

- [ ] **Step 2: Migrate personnel workflow**

Preserve this exact business sequence:

```text
open person info page
import person file
wait import result
if ready_to_submit:
  submit import data
  if submit failed:
    return failed with side_effect_started=True, side_effect_committed=True, retry_allowed=False
  wait submit result
  if still ready_to_submit:
    return UNKNOWN_RESULT/person_import_result_unknown
else:
  use validation result as final result
```

The final result must explicitly aggregate side effects from earlier steps:

```python
side_effect_started = (
    import_file.ok
    or import_file.side_effect_started
    or validation_result.side_effect_started
    or import_result.side_effect_started
)
```

Do not hide the `ready_to_submit` post-submit branch in a generic helper.

- [ ] **Step 3: Preserve personnel evidence shape**

Personnel workflow results must keep the existing evidence keys:

- `import_file`
- `validation_result`
- `import_result`
- `submit_result` when the `ready_to_submit` branch executes

Do not replace these keys with generic step names or with only the final step evidence.

- [ ] **Step 4: Run personnel workflow tests**

```bash
python -m unittest tests.test_component_architecture tests.test_page_step_architecture tests.test_existing_workflow_executor tests.test_from_zero_import_person_info -v
```

Expected: pass.

### Task 6: Remove CombinedTaxWorkflow Factory Introspection

**Files:**
- Modify: `tax_rpa/workflows/combined_tax_workflow.py`
- Modify: `tax_rpa/cli/run_tax_workflow.py`
- Modify: `tax_rpa/cli/import_salary_income.py`
- Modify: `tax_rpa/cli/update_special_deduction.py`
- Modify: tests with fake workflow factories

- [ ] **Step 1: Update all fake workflow factories to accept `**kwargs`**

First build a full search checklist:

```bash
rg -n "workflow_factories=|lambda config, logger|def _workflow_factories" tax_rpa tests
```

Update every factory that can be passed into `CombinedTaxWorkflow`, not just examples in `tests/test_workflow_composition.py`.

Example:

```python
lambda config, logger, **_kwargs: FakeBusinessWorkflow("person_info", events)
```

- [ ] **Step 2: Update production CLI workflow factories**

Example:

```python
lambda config, logger, **kwargs: ImportPersonInfoWorkflow(config, logger, **kwargs)
```

Apply to:

- `tax_rpa/cli/run_tax_workflow.py`
- `tax_rpa/cli/import_salary_income.py`
- `tax_rpa/cli/update_special_deduction.py`

- [ ] **Step 3: Remove signature introspection**

In `CombinedTaxWorkflow._build_business_workflow()`:

```python
return factory(
    self.config,
    self.logger,
    step_runner=self.step_runner,
    runtime_options=self.runtime_options,
)
```

Remove `inspect` import and `_accepts_parameter()`.

- [ ] **Step 4: Run factory and CLI tests**

```bash
python -m unittest tests.test_workflow_composition tests.test_combined_cli tests.test_new_workflow_cli -v
```

Expected: pass.

### Task 7: Update Docs And Templates

**Files:**
- Modify: `tax_rpa/workflows/__init__.py`
- Modify: `docs/architecture_file_map.md`
- Modify: `docs/learning/templates/new_page_step_workflow_template.md`

- [ ] **Step 1: Export support classes if useful**

Export:

```python
BusinessWorkflow
WorkflowContext
```

- [ ] **Step 2: Update architecture docs**

Document that `base.py` and `context.py` are workflow support code, not new business layers.

- [ ] **Step 3: Update new workflow template**

Show new workflows inheriting `BusinessWorkflow` and implementing `execute(app)`.

### Task 8: macOS Semantic Regression

**Files:**
- No production changes.

- [ ] **Step 1: Run workflow and job regression**

```bash
python -m unittest tests.test_workflow_composition tests.test_existing_workflow_executor tests.test_phase5_executor_integration tests.test_job_runner tests.test_from_zero_import_person_info -v
```

Expected: pass.

- [ ] **Step 2: Verify job observability**

```bash
python -m unittest tests.test_existing_workflow_executor.ExistingWorkflowExecutorTests.test_job_runner_execute_no_send_self_check_reaches_salary_import_success -v
```

Expected:

- job state remains `succeeded`
- key result matrix rows are still emitted in job paths:
  - `personnel_import`
  - `special_deduction_update`
  - `salary_income_import`
  - when Phase 5 is enabled: `prefill_deduction`, `tax_calculation`, `declaration_submission_readiness`, `export_report`
- the final step event still has result matrix step `salary_income_import` for the existing no-send self-check path
- the final result matrix outcome remains `success`

- [ ] **Step 3: Verify lifecycle single ownership**

```bash
python -m unittest tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_runs_lifecycle_once_then_business_workflows_in_order tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_does_not_reset_between_successful_business_workflows -v
```

Expected: lifecycle events are not duplicated.

- [ ] **Step 4: Run full unit suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

### Task 9: Windows Validation Gate

**Files:**
- No code changes required by this task.

This task must run on a Windows machine with the tax client environment.

- [ ] **Step 1: Windows self-check**

```powershell
python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

Expected: success summary path printed.

- [ ] **Step 2: Windows inspect_only**

Run the configured job-runner inspect/dry-run path against the real client using the deployment manifest and machine config from the target Windows environment. Use the same entrypoint documented for the current production gate/canary process; do not substitute a standalone debug CLI path unless that is the documented deployment path for the machine.

Expected:

- client starts or binds
- login wait completes
- target pages can be opened
- no real submit/import side effects occur

- [ ] **Step 3: Windows execute_no_send canary**

Run the configured no-send canary through the existing canary/production-gate entrypoint with the target manifest, machine config, and calibration artifacts.

Expected:

- no submit action
- required artifacts and logs written
- operator can inspect result

Until this task passes, the refactor status is:

```text
code semantics verified only; real RPA execution not verified
```

## Rollout Recommendation

Execute the plan in this order:

1. add support classes and tests
2. migrate simple workflows one at a time
3. migrate multi-step workflows
4. migrate personnel import last
5. remove factory introspection only after all real/fake factories accept `**kwargs`
6. run macOS semantic regression
7. run Windows validation before production use

Do not enable real `submit` based on macOS tests alone.

## Success Criteria

- full macOS unit suite passes
- job fake-driver path still reaches salary import success
- workflow evidence keys remain stable for personnel, salary, prefill, and export workflows
- `WorkflowContext.step()` accepts only `StepResult` operations and does not wrap page-opening steps that return page objects
- personnel import unknown and submit-failure branches preserve side-effect and retry semantics
- `logs/steps.jsonl` and `logs/step_journal.jsonl` still contain workflow step events in job paths
- job result matrix rows are preserved for every migrated business workflow, not only the last workflow
- combined workflow lifecycle remains single-owned
- Windows self-check and at least inspect-only validation pass before claiming RPA execution compatibility
- architecture remains `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`
