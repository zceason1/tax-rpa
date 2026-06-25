# Business Workflow Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce workflow-layer boilerplate so business workflows read as business sequences while preserving the current `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver` architecture.

**Architecture:** Keep `Job` as the production runtime shell and keep `Page / Component / Driver` boundaries intact. Add a small workflow support layer that centralizes runtime context, step execution, lifecycle wrapping, and `WorkflowResult` construction, then migrate existing workflows incrementally without changing observable job artifacts.

**Tech Stack:** Python `unittest`, dataclasses, existing `StepResult`, `WorkflowResult`, `WorkflowRuntimeOptions`, `StepRunner`, `DirectStepRunner`, `JobStepRunner`, fake-driver tests.

---

## Current Assessment

The business layer is maintainable but unnecessarily verbose. The main problem is not the number of page/component/driver files; those boundaries protect RPA-specific UI automation details. The main problem is that every workflow repeats the same runtime plumbing:

- constructor fields: `config`, `logger`, `runtime_options`, `step_runner`, `app_factory`
- lifecycle wrapping through `AppLifecycleWorkflow`
- optional job instrumentation through `_run_step`
- manual `WorkflowResult(...)` creation
- manual failure conversion from `StepResult`
- repeated evidence and side-effect propagation

Examples:

- `tax_rpa/workflows/import_person_info_workflow.py` contains the real personnel import decision flow, but it is surrounded by repeated `WorkflowResult` and side-effect wrapping.
- `tax_rpa/workflows/update_special_deduction_workflow.py`, `tax_rpa/workflows/tax_calculation_workflow.py`, and `tax_rpa/workflows/declaration_submission_workflow.py` are mostly one-step workflows but still repeat constructor, lifecycle, `_run_step`, and result wrapping code.
- `tax_rpa/workflows/combined_tax_workflow.py` uses signature introspection to pass optional `step_runner` and `runtime_options`; this is a smell caused by inconsistent workflow constructors.

The target is to make workflow files express only:

```text
open page
run business step
if failed, stop
run next business step
return final business result
```

and move common runtime behavior into reusable helpers.

## Target Shape

After the refactor, the business layer should read like this:

```text
CombinedTaxWorkflow
  -> lifecycle once
  -> business_workflow.run_on_app(app)

BusinessWorkflow base
  -> owns WorkflowContext
  -> provides run(), step(), failed(), result_from_step()

Concrete workflow
  -> only defines business order
```

New support files:

```text
tax_rpa/workflows/context.py
tax_rpa/workflows/base.py
```

Kept as-is:

```text
tax_rpa/pages/**/*
tax_rpa/drivers/**/*
tax_rpa/jobs/runner.py
tax_rpa/jobs/workflow_step_runner.py
tax_rpa/runtime/result.py
```

## Non-Goals

- Do not merge `Step`, `Page`, `Component`, and `Driver`.
- Do not move job observability into workflows.
- Do not introduce REST API or a service layer in this refactor.
- Do not rename `PersonImportConfig` in this pass; it is a separate compatibility cleanup.
- Do not change `summary.json`, `state.json`, `artifact_manifest.json`, callback payloads, or result matrix semantics.
- Do not turn workflows into a declarative DSL. RPA flows need ordinary Python control flow because UI state branches are operationally important.

## Risk Controls

This is a semantics-preserving refactor. Treat shorter workflow files as a secondary benefit; the primary requirement is that runtime behavior and job artifacts remain unchanged.

An independent architecture review found the original draft was not safe to execute until these corrections were added:

- personnel import submit-failure must force `side_effect_started=True`, `side_effect_committed=True`, and `retry_allowed=False`
- production CLI workflow factories must be updated before `CombinedTaxWorkflow` factory introspection is removed
- constructor compatibility must be either preserved or deliberately tested as an internal API cleanup

### Result Metadata Must Not Regress

`WorkflowResult` fields are production contracts. During migration, every helper that constructs a `WorkflowResult` must preserve:

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

Regression signal: `JobRunner` marks a failed business run as succeeded, callback summaries lose error data, or result matrix tests no longer classify failures correctly.

### Side-Effect Semantics Must Be Preserved

The final failing step is not always the step that started the business side effect. Example:

```text
personnel import file submitted successfully
-> waiting for result fails or returns unknown
```

The final result may come from a wait step, but the workflow must still report `side_effect_started=True`, `side_effect_committed=True`, and `retry_allowed=False`. Do not derive workflow side-effect fields only from the last step unless the workflow truly has no earlier side effects.

Regression signal: a workflow that already submitted/imported data becomes retryable.

### Lifecycle Must Stay Single-Owned

There are two valid execution modes:

```text
workflow.run()
  -> starts lifecycle for standalone/debug usage

CombinedTaxWorkflow.run()
  -> starts lifecycle once
  -> calls child workflow.run_on_app(app) or execute(app)
```

`CombinedTaxWorkflow` must not call child `run()`, otherwise child workflows can start or reset the client again.

Regression signal: fake-driver events show duplicated `start`, `wait_login`, or `reset` between successful child workflows.

### Job Observability Must Continue Through StepRunner

`WorkflowContext.step()` must call `step_runner.run_step(...)` when a runner is provided. This is how job runs write:

- `logs/steps.jsonl`
- `logs/step_journal.jsonl`
- result matrix rows
- side-effect journal markers

Regression signal: `tests/test_existing_workflow_executor.py` no longer sees `salary_income_import` in the last step event, or side-effect journal markers disappear.

### Personnel Import Special Branch Must Stay Explicit

Personnel import has a special post-submit branch:

```text
wait_import_result == ready_to_submit
-> submit_import_data
-> wait_submit_result == ready_to_submit
-> UNKNOWN_RESULT/person_import_result_unknown
```

Do not hide this branch inside a generic helper. Keep it visible in `ImportPersonInfoWorkflow.execute()` or a clearly named private method.

Regression signal: `tests/test_page_step_architecture.py` or `tests/test_component_architecture.py` no longer fails the stalled submit confirmation case.

### Avoid Over-Abstraction

The intended abstraction is:

```text
WorkflowContext.step()
WorkflowContext.result_from_step()
WorkflowContext.failed_from_step()
BusinessWorkflow.run()
```

Do not introduce a declarative list of step descriptors, conditional DSL, decorators, or metaclass-based workflow registration in this refactor. That would make RPA debugging harder and exceed the current maintainability goal.

## Files

- Create: `tax_rpa/workflows/context.py`
  - Holds `WorkflowContext`, default `DirectStepRunner`, and helpers for step execution and result conversion.
- Create: `tax_rpa/workflows/base.py`
  - Holds `BusinessWorkflow`, the lifecycle wrapper, and compatibility `run_on_app` contract.
- Modify: `tax_rpa/workflows/update_special_deduction_workflow.py`
  - Migrate a simple one-step workflow first.
- Modify: `tax_rpa/workflows/tax_calculation_workflow.py`
  - Migrate a one-step workflow with side effects.
- Modify: `tax_rpa/workflows/declaration_submission_workflow.py`
  - Migrate a one-step, no-side-effect readiness workflow.
- Modify: `tax_rpa/workflows/import_salary_income_workflow.py`
  - Migrate a two-step workflow with an early failure.
- Modify: `tax_rpa/workflows/prefill_deduction_workflow.py`
  - Migrate a two-step workflow with runtime options.
- Modify: `tax_rpa/workflows/export_report_workflow.py`
  - Migrate readiness plus export flow.
- Modify: `tax_rpa/workflows/import_person_info_workflow.py`
  - Migrate the most complex workflow last.
- Modify: `tax_rpa/workflows/combined_tax_workflow.py`
  - Remove factory signature introspection only after concrete workflows share the common constructor contract.
- Modify: `tax_rpa/workflows/__init__.py`
  - Export the new workflow support classes if useful.
- Modify: `docs/architecture_file_map.md`
  - Document the workflow support layer.
- Test: `tests/test_workflow_context.py`
  - New focused tests for context and result conversion.
- Test: existing workflow tests
  - `tests/test_workflow_composition.py`
  - `tests/test_component_architecture.py`
  - `tests/test_page_step_architecture.py`
  - `tests/test_existing_workflow_executor.py`
  - `tests/test_phase5_workflows.py`
  - `tests/test_phase5_executor_integration.py`

---

### Task 1: Add WorkflowContext

**Files:**
- Create: `tests/test_workflow_context.py`
- Create: `tax_rpa/workflows/context.py`

- [ ] **Step 1: Write failing context tests**

Add `tests/test_workflow_context.py`:

```python
import unittest
from pathlib import Path

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.context import WorkflowContext


class RecordingStepRunner:
    def __init__(self):
        self.calls = []

    def run_step(
        self,
        *,
        workflow,
        step,
        operation,
        matrix_step=None,
        side_effect_step=False,
    ):
        self.calls.append(
            {
                "workflow": workflow,
                "step": step,
                "matrix_step": matrix_step,
                "side_effect_step": side_effect_step,
            }
        )
        return operation()


class WorkflowContextTests(unittest.TestCase):
    def test_step_uses_runner_with_workflow_name(self):
        runner = RecordingStepRunner()
        ctx = WorkflowContext(
            workflow="sample_workflow",
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            runtime_options=WorkflowRuntimeOptions(run_mode="execute_no_send"),
            step_runner=runner,
        )

        result = ctx.step(
            "sample.step",
            lambda: StepResult(ok=True, name="sample.step", status="done"),
            matrix_step="sample_matrix",
            side_effect_step=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            runner.calls,
            [
                {
                    "workflow": "sample_workflow",
                    "step": "sample.step",
                    "matrix_step": "sample_matrix",
                    "side_effect_step": True,
                }
            ],
        )

    def test_result_from_step_copies_error_and_side_effect_metadata(self):
        ctx = WorkflowContext(
            workflow="sample_workflow",
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            runtime_options=WorkflowRuntimeOptions(run_mode="execute_no_send"),
        )
        step = StepResult(
            ok=False,
            name="sample.step",
            status="failed",
            evidence={"raw": "value"},
            error="forced",
            error_type="SYSTEM_ERROR",
            error_code="forced_failure",
            side_effect_started=True,
            side_effect_committed=False,
            retry_allowed=False,
        )

        result = ctx.result_from_step(
            step,
            steps=[step],
            evidence={"sample": step.evidence},
        )

        self.assertEqual(
            result,
            WorkflowResult(
                ok=False,
                name="sample_workflow",
                status="failed",
                steps=[step],
                evidence={"sample": {"raw": "value"}},
                error="forced",
                error_type="SYSTEM_ERROR",
                error_code="forced_failure",
                side_effect_started=True,
                side_effect_committed=False,
                retry_allowed=False,
            ),
        )

    def test_result_from_step_does_not_infer_side_effects_from_last_step(self):
        ctx = WorkflowContext(
            workflow="sample_workflow",
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            runtime_options=WorkflowRuntimeOptions(run_mode="execute_no_send"),
        )
        import_step = StepResult(
            ok=True,
            name="import_file",
            status="submitted",
            side_effect_started=True,
            side_effect_committed=True,
        )
        wait_step = StepResult(
            ok=False,
            name="wait_result",
            status="unknown",
            error_type="UNKNOWN_RESULT",
            error_code="result_unknown",
        )

        result = ctx.result_from_step(
            wait_step,
            steps=[import_step, wait_step],
            evidence={"import_file": {}, "wait_result": {}},
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def test_failed_from_step_accepts_explicit_side_effect_overrides(self):
        ctx = WorkflowContext(
            workflow="sample_workflow",
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            runtime_options=WorkflowRuntimeOptions(run_mode="execute_no_send"),
        )
        submit_step = StepResult(
            ok=False,
            name="submit",
            status="failed",
            error="submit failed",
            retry_allowed=True,
        )

        result = ctx.failed_from_step(
            submit_step,
            steps=[submit_step],
            evidence={"submit": {}},
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
python -m unittest tests.test_workflow_context -v
```

Expected: fails because `tax_rpa.workflows.context` does not exist.

- [ ] **Step 3: Implement WorkflowContext**

Create `tax_rpa/workflows/context.py`:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.step_runner import DirectStepRunner, StepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


@dataclass(frozen=True)
class WorkflowContext:
    """Runtime context shared by business workflows."""

    workflow: str
    config: PersonImportConfig
    logger: Any
    runtime_options: WorkflowRuntimeOptions
    step_runner: StepRunner | None = None

    def step(
        self,
        step: str,
        operation: Callable[[], StepResult],
        *,
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        runner = self.step_runner or DirectStepRunner()
        return runner.run_step(
            workflow=self.workflow,
            step=step,
            operation=operation,
            matrix_step=matrix_step,
            side_effect_step=side_effect_step,
        )

    def result_from_step(
        self,
        result: StepResult,
        *,
        steps: list[StepResult],
        evidence: dict[str, Any] | None = None,
        side_effect_started: bool | None = None,
        side_effect_committed: bool | None = None,
        retry_allowed: bool | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            ok=result.ok,
            name=self.workflow,
            status=result.status,
            steps=steps,
            evidence=evidence or {},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=(
                result.side_effect_started
                if side_effect_started is None
                else side_effect_started
            ),
            side_effect_committed=(
                result.side_effect_committed
                if side_effect_committed is None
                else side_effect_committed
            ),
            retry_allowed=result.retry_allowed if retry_allowed is None else retry_allowed,
        )

    def failed_from_step(
        self,
        result: StepResult,
        *,
        steps: list[StepResult],
        evidence: dict[str, Any] | None = None,
        side_effect_started: bool | None = None,
        side_effect_committed: bool | None = None,
        retry_allowed: bool | None = None,
    ) -> WorkflowResult:
        return WorkflowResult(
            ok=False,
            name=self.workflow,
            status=result.status,
            steps=steps,
            evidence=evidence or {},
            error=result.error,
            error_type=result.error_type,
            error_code=result.error_code,
            side_effect_started=(
                result.side_effect_started
                if side_effect_started is None
                else side_effect_started
            ),
            side_effect_committed=(
                result.side_effect_committed
                if side_effect_committed is None
                else side_effect_committed
            ),
            retry_allowed=result.retry_allowed if retry_allowed is None else retry_allowed,
        )
```

- [ ] **Step 4: Run test and confirm GREEN**

Run:

```bash
python -m unittest tests.test_workflow_context -v
```

Expected: pass.

---

### Task 2: Add BusinessWorkflow Base

**Files:**
- Modify: `tests/test_workflow_context.py`
- Create: `tax_rpa/workflows/base.py`

- [ ] **Step 1: Add failing lifecycle wrapper tests**

Append to `tests/test_workflow_context.py`:

```python
from tax_rpa.workflows.base import BusinessWorkflow


class FakeApp:
    def __init__(self, events):
        self.events = events

    def start_if_needed(self):
        self.events.append("start")
        return StepResult(ok=True, name="start", status="started")

    def wait_for_login(self):
        self.events.append("wait_login")
        return StepResult(ok=True, name="wait_login", status="logged_in")


class SampleBusinessWorkflow(BusinessWorkflow):
    name = "sample_business_workflow"

    def execute(self, app):
        app.events.append("execute")
        step = StepResult(ok=True, name="sample.step", status="done")
        return self.context.result_from_step(
            step,
            steps=[step],
            evidence={"step": step.evidence},
        )


class BusinessWorkflowTests(unittest.TestCase):
    def test_run_wraps_lifecycle_and_business_execution(self):
        events = []
        workflow = SampleBusinessWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(events, ["start", "wait_login", "execute"])
        self.assertEqual(result.name, "sample_business_workflow")
        self.assertEqual([step.status for step in result.steps], ["started", "logged_in", "done"])
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
python -m unittest tests.test_workflow_context -v
```

Expected: fails because `tax_rpa.workflows.base` does not exist.

- [ ] **Step 3: Implement BusinessWorkflow**

Create `tax_rpa/workflows/base.py`:

```python
from collections.abc import Callable
from typing import Any

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.runtime.step_runner import StepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow
from tax_rpa.workflows.context import WorkflowContext


class BusinessWorkflow:
    """Base class for business workflows that execute on the tax client."""

    name = ""

    def __init__(
        self,
        config: PersonImportConfig,
        logger: Any,
        app_factory: Callable[[PersonImportConfig, Any], Any] | None = None,
        runtime_options: WorkflowRuntimeOptions | None = None,
        step_runner: StepRunner | None = None,
        reset: bool = False,
    ) -> None:
        if not self.name:
            raise ValueError("BusinessWorkflow subclasses must define name")
        self.config = config
        self.logger = logger
        self.app_factory = app_factory or (lambda config, logger: TaxClientApp(config, logger))
        self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
        self.step_runner = step_runner
        self.reset = reset
        self.context = WorkflowContext(
            workflow=self.name,
            config=config,
            logger=logger,
            runtime_options=self.runtime_options,
            step_runner=step_runner,
        )

    def run(self) -> WorkflowResult:
        lifecycle = AppLifecycleWorkflow(
            self.config,
            self.logger,
            reset=self.reset,
            app_factory=self.app_factory,
        )
        lifecycle_result = lifecycle.run()
        if not lifecycle_result.ok:
            return WorkflowResult(
                ok=False,
                name=self.name,
                status=lifecycle_result.status,
                steps=lifecycle_result.steps,
                evidence={"lifecycle": lifecycle_result.evidence},
                error=lifecycle_result.error,
                error_type=lifecycle_result.error_type,
                error_code=lifecycle_result.error_code,
                side_effect_started=lifecycle_result.side_effect_started,
                side_effect_committed=lifecycle_result.side_effect_committed,
                retry_allowed=lifecycle_result.retry_allowed,
            )

        business_result = self.run_on_app(lifecycle.app)
        return WorkflowResult(
            ok=business_result.ok,
            name=self.name,
            status=business_result.status,
            steps=[*lifecycle_result.steps, *business_result.steps],
            evidence=business_result.evidence,
            error=business_result.error,
            error_type=business_result.error_type,
            error_code=business_result.error_code,
            side_effect_started=business_result.side_effect_started,
            side_effect_committed=business_result.side_effect_committed,
            retry_allowed=business_result.retry_allowed,
        )

    def run_on_app(self, app: Any) -> WorkflowResult:
        return self.execute(app)

    def execute(self, app: Any) -> WorkflowResult:
        raise NotImplementedError
```

Keep `app_factory`, `runtime_options`, `step_runner`, and `reset` positional-compatible during this refactor. Several existing workflow constructors accepted those arguments positionally; narrowing them to keyword-only would be a separate API cleanup and is not part of this plan.

- [ ] **Step 4: Run test and confirm GREEN**

Run:

```bash
python -m unittest tests.test_workflow_context -v
```

Expected: pass.

---

### Task 3: Migrate One-Step Workflows

**Files:**
- Modify: `tax_rpa/workflows/update_special_deduction_workflow.py`
- Modify: `tax_rpa/workflows/tax_calculation_workflow.py`
- Modify: `tax_rpa/workflows/declaration_submission_workflow.py`

- [ ] **Step 1: Run current workflow tests as baseline**

Run:

```bash
python -m unittest tests.test_special_deduction_steps tests.test_phase5_workflows tests.test_workflow_composition -v
```

Expected: pass before refactor.

- [ ] **Step 2: Migrate `UpdateSpecialDeductionWorkflow`**

Replace the class with this structure:

```python
from typing import Any

from tax_rpa.pages.special_deduction.steps.download_update_all_persons import (
    DownloadUpdateAllPersonsStep,
)
from tax_rpa.pages.special_deduction.steps.open_page import OpenSpecialDeductionPageStep
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class UpdateSpecialDeductionWorkflow(BusinessWorkflow):
    """Update special deduction information for all persons."""

    name = "update_special_deduction_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        page = OpenSpecialDeductionPageStep(app.shell()).run()
        update_result = self.context.step(
            "special_deduction.download_update_all_persons",
            lambda: DownloadUpdateAllPersonsStep(page).run(),
            matrix_step="special_deduction_update",
            side_effect_step=True,
        )
        return self.context.result_from_step(
            update_result,
            steps=[update_result],
            evidence={"download_update": update_result.evidence},
        )
```

- [ ] **Step 3: Migrate `TaxCalculationWorkflow`**

Replace the class with this structure:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.tax_calculation import TaxCalculationStep
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class TaxCalculationWorkflow(BusinessWorkflow):
    """Calculate tax in the comprehensive income page."""

    name = "tax_calculation_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        calculation = self.context.step(
            "comprehensive_income.calculate_tax",
            lambda: TaxCalculationStep(page).run(),
            matrix_step="tax_calculation",
            side_effect_step=True,
        )
        return self.context.result_from_step(
            calculation,
            steps=[calculation],
            evidence={"calculation": calculation.evidence},
        )
```

- [ ] **Step 4: Migrate `DeclarationSubmissionWorkflow`**

Replace the class with this structure:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class DeclarationSubmissionWorkflow(BusinessWorkflow):
    """Verify declaration submission readiness without sending in safe modes."""

    name = "declaration_submission_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        readiness = self.context.step(
            "comprehensive_income.declaration_submission_readiness",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self.context.runtime_options.run_mode,
            ).run(),
            matrix_step="declaration_submission_readiness",
            side_effect_step=False,
        )
        return self.context.result_from_step(
            readiness,
            steps=[readiness],
            evidence={"readiness": readiness.evidence},
        )
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m unittest tests.test_special_deduction_steps tests.test_phase5_workflows tests.test_phase5_executor_integration -v
```

Expected: pass.

---

### Task 4: Migrate Multi-Step Workflows Except Personnel Import

**Files:**
- Modify: `tax_rpa/workflows/import_salary_income_workflow.py`
- Modify: `tax_rpa/workflows/prefill_deduction_workflow.py`
- Modify: `tax_rpa/workflows/export_report_workflow.py`

- [ ] **Step 1: Migrate `ImportSalaryIncomeWorkflow`**

Keep the current business order and replace duplicated plumbing:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.steps.import_salary_income_data import (
    ImportSalaryIncomeDataStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_salary_income_form import (
    OpenSalaryIncomeFormStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class ImportSalaryIncomeWorkflow(BusinessWorkflow):
    """Import salary income data."""

    name = "import_salary_income_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        steps = []
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        open_form = self.context.step(
            "comprehensive_income.open_salary_income_form",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self.context.failed_from_step(open_form, steps=steps)

        import_file = self.context.step(
            "comprehensive_income.import_salary_income_data",
            lambda: ImportSalaryIncomeDataStep(page).run(
                self.context.config.import_file("salary_income")
            ),
            matrix_step="salary_income_import",
            side_effect_step=True,
        )
        steps.append(import_file)
        return self.context.result_from_step(
            import_file,
            steps=steps,
            evidence={
                "open_form": open_form.evidence,
                "import_file": import_file.evidence,
            },
        )
```

- [ ] **Step 2: Migrate `PrefillDeductionWorkflow`**

Use the same shape and read options from context:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_salary_income_form import (
    OpenSalaryIncomeFormStep,
)
from tax_rpa.pages.comprehensive_income.steps.prefill_deduction import (
    PrefillDeductionStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class PrefillDeductionWorkflow(BusinessWorkflow):
    """Prefill deductions."""

    name = "prefill_deduction_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        steps = []
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        open_form = self.context.step(
            "comprehensive_income.open_salary_income_form_for_prefill",
            lambda: OpenSalaryIncomeFormStep(page).run(),
        )
        steps.append(open_form)
        if not open_form.ok:
            return self.context.failed_from_step(open_form, steps=steps)

        prefill = self.context.step(
            "comprehensive_income.prefill_deduction",
            lambda: PrefillDeductionStep(
                page,
                allow_skip_personal_pension=(
                    self.context.runtime_options.allow_skip_personal_pension
                ),
            ).run(),
            matrix_step="prefill_deduction",
            side_effect_step=True,
        )
        steps.append(prefill)
        return self.context.result_from_step(
            prefill,
            steps=steps,
            evidence={"open_form": open_form.evidence, "prefill": prefill.evidence},
        )
```

- [ ] **Step 3: Migrate `ExportReportWorkflow`**

Keep readiness before export:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.steps.declaration_submission_readiness import (
    DeclarationSubmissionReadinessStep,
)
from tax_rpa.pages.comprehensive_income.steps.export_declaration_report import (
    ExportDeclarationReportStep,
)
from tax_rpa.pages.comprehensive_income.steps.open_page import (
    OpenComprehensiveIncomePageStep,
)
from tax_rpa.runtime.result import WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class ExportReportWorkflow(BusinessWorkflow):
    """Export declaration report."""

    name = "export_report_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        page = OpenComprehensiveIncomePageStep(app.shell()).run()
        readiness = self.context.step(
            "comprehensive_income.declaration_submission_readiness_for_export",
            lambda: DeclarationSubmissionReadinessStep(
                page,
                run_mode=self.context.runtime_options.run_mode,
            ).run(),
        )
        steps = [readiness]
        if not readiness.ok:
            return self.context.failed_from_step(readiness, steps=steps)

        export = self.context.step(
            "comprehensive_income.export_report",
            lambda: ExportDeclarationReportStep(
                page,
                run_mode=self.context.runtime_options.run_mode,
            ).run(),
            matrix_step="export_report",
            side_effect_step=True,
        )
        steps.append(export)
        return self.context.result_from_step(
            export,
            steps=steps,
            evidence={
                "readiness": readiness.evidence,
                "export": export.evidence,
                "export_status": export.evidence.get("export_status"),
            },
        )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m unittest tests.test_comprehensive_income_steps tests.test_phase5_workflows tests.test_phase5_executor_integration -v
```

Expected: pass.

---

### Task 5: Migrate Personnel Import Workflow

**Files:**
- Modify: `tax_rpa/workflows/import_person_info_workflow.py`

- [ ] **Step 1: Run personnel workflow baseline tests**

Run:

```bash
python -m unittest tests.test_component_architecture tests.test_page_step_architecture tests.test_existing_workflow_executor -v
```

Expected: pass before refactor.

- [ ] **Step 2: Replace runtime plumbing while preserving business decisions**

Rewrite the workflow with the base class but keep the existing `ready_to_submit` and post-submit unknown behavior:

```python
from typing import Any

from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.steps.open_page import OpenPersonInfoPageStep
from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.base import BusinessWorkflow


class ImportPersonInfoWorkflow(BusinessWorkflow):
    """Import personnel information."""

    name = "import_person_info_workflow"

    def execute(self, app: Any) -> WorkflowResult:
        steps = []
        page = OpenPersonInfoPageStep(app.shell()).run()

        import_file = self.context.step(
            "person_info.import_person_file",
            lambda: ImportPersonFileStep(page).run(self.context.config.person_info_file),
            side_effect_step=True,
        )
        steps.append(import_file)
        if not import_file.ok:
            return self.context.failed_from_step(
                import_file,
                steps=steps,
                evidence={"import_file": import_file.evidence},
            )

        validation_result = self.context.step(
            "person_info.wait_import_result",
            lambda: WaitImportResultStep(page).run(),
            matrix_step="personnel_import",
        )
        steps.append(validation_result)

        if validation_result.status == "ready_to_submit":
            submit_result = self.context.step(
                "person_info.submit_import_data",
                lambda: SubmitImportDataStep(page).run(),
                side_effect_step=True,
            )
            steps.append(submit_result)
            if not submit_result.ok:
                return self.context.failed_from_step(
                    submit_result,
                    steps=steps,
                    evidence={
                        "import_file": import_file.evidence,
                        "validation_result": validation_result.evidence,
                        "submit_result": submit_result.evidence,
                    },
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            import_result = self.context.step(
                "person_info.wait_submit_result",
                lambda: WaitImportResultStep(page).run(),
                matrix_step="personnel_import",
            )
            if import_result.status == "ready_to_submit":
                import_result = StepResult(
                    ok=False,
                    name=import_result.name,
                    status="unknown",
                    evidence={
                        **import_result.evidence,
                        "post_submit_status": "ready_to_submit",
                    },
                    error="Personnel import remained at submit-data confirmation after submit",
                    error_type="UNKNOWN_RESULT",
                    error_code="person_import_result_unknown",
                    side_effect_started=True,
                    side_effect_committed=True,
                    retry_allowed=False,
                )
            steps.append(import_result)
        else:
            import_result = validation_result

        evidence = {
            "import_file": import_file.evidence,
            "validation_result": validation_result.evidence,
            "import_result": import_result.evidence,
        }
        if validation_result.status == "ready_to_submit":
            evidence["submit_result"] = steps[-2].evidence

        result = self.context.result_from_step(
            import_result,
            steps=steps,
            evidence=evidence,
            side_effect_started=(
                import_file.ok
                or import_file.side_effect_started
                or validation_result.side_effect_started
                or import_result.side_effect_started
            ),
            side_effect_committed=(
                import_file.ok
                or import_file.side_effect_committed
                or validation_result.side_effect_committed
                or import_result.side_effect_committed
            ),
            retry_allowed=False
            if (
                import_file.ok
                or import_file.side_effect_started
                or validation_result.side_effect_started
                or import_result.side_effect_started
            )
            else import_result.retry_allowed,
        )
        return result
```

- [ ] **Step 3: Run personnel workflow tests**

Run:

```bash
python -m unittest tests.test_component_architecture tests.test_page_step_architecture tests.test_existing_workflow_executor -v
```

Expected: pass.

- [ ] **Step 4: Verify stalled submit semantics remain unchanged**

Run:

```bash
python -m unittest tests.test_page_step_architecture.PageStepArchitectureTests.test_workflow_stops_when_submit_data_does_not_finalize_import tests.test_component_architecture.SubmitDataStallTests.test_person_import_workflow_stops_when_submit_data_does_not_finalize_import -v
```

Expected:

- both tests pass
- final status remains `unknown`
- `error_type` remains `UNKNOWN_RESULT`
- `error_code` remains `person_import_result_unknown`

- [ ] **Step 5: Verify side-effect failure still fails the job safely**

Run:

```bash
python -m unittest tests.test_existing_workflow_executor.ExistingWorkflowExecutorTests.test_job_runner_marks_unknown_import_result_as_failed_business_job -v
```

Expected:

- summary state remains `failed`
- summary error type remains `UNKNOWN_RESULT`
- executor workflow status remains `unknown`
- failed package is still written

- [ ] **Step 6: Add a focused submit-failure side-effect test**

Add or update a personnel workflow test so that:

- first `WaitImportResultStep` returns `ready_to_submit`
- `SubmitImportDataStep` returns `StepResult(ok=False, status="failed", retry_allowed=True)` without side-effect flags
- workflow result still has `side_effect_started=True`
- workflow result still has `side_effect_committed=True`
- workflow result has `retry_allowed=False`

Run the focused test:

```bash
python -m unittest tests.test_page_step_architecture -v
```

Expected: pass.

---

### Task 6: Remove CombinedTaxWorkflow Factory Introspection

**Files:**
- Modify: `tax_rpa/workflows/combined_tax_workflow.py`
- Modify: `tax_rpa/cli/run_tax_workflow.py`
- Modify: `tax_rpa/cli/import_salary_income.py`
- Modify: `tax_rpa/cli/update_special_deduction.py`
- Modify: tests that use fake workflow factories

- [ ] **Step 1: Update tests to use common workflow factory signature**

In `tests/test_workflow_composition.py`, update fake workflow factories from:

```python
lambda config, logger: FakeBusinessWorkflow("person_info", events)
```

to:

```python
lambda config, logger, **_kwargs: FakeBusinessWorkflow("person_info", events)
```

Apply the same pattern to all fake workflow factory lambdas in the file.

- [ ] **Step 2: Update production CLI workflow factories**

Update `tax_rpa/cli/run_tax_workflow.py` from:

```python
workflow_factories=[
    lambda config, logger: ImportPersonInfoWorkflow(config, logger),
    lambda config, logger: UpdateSpecialDeductionWorkflow(config, logger),
    lambda config, logger: ImportSalaryIncomeWorkflow(config, logger),
]
```

to:

```python
workflow_factories=[
    lambda config, logger, **kwargs: ImportPersonInfoWorkflow(config, logger, **kwargs),
    lambda config, logger, **kwargs: UpdateSpecialDeductionWorkflow(config, logger, **kwargs),
    lambda config, logger, **kwargs: ImportSalaryIncomeWorkflow(config, logger, **kwargs),
]
```

Update `tax_rpa/cli/import_salary_income.py` from:

```python
workflow_factories=[lambda config, logger: ImportSalaryIncomeWorkflow(config, logger)]
```

to:

```python
workflow_factories=[
    lambda config, logger, **kwargs: ImportSalaryIncomeWorkflow(config, logger, **kwargs)
]
```

Update `tax_rpa/cli/update_special_deduction.py` from:

```python
workflow_factories=[lambda config, logger: UpdateSpecialDeductionWorkflow(config, logger)]
```

to:

```python
workflow_factories=[
    lambda config, logger, **kwargs: UpdateSpecialDeductionWorkflow(config, logger, **kwargs)
]
```

- [ ] **Step 3: Simplify factory building**

In `tax_rpa/workflows/combined_tax_workflow.py`, replace `_build_business_workflow` and remove `_accepts_parameter`.

Use:

```python
    def _build_business_workflow(self, factory: BusinessWorkflowFactory) -> Any:
        return factory(
            self.config,
            self.logger,
            step_runner=self.step_runner,
            runtime_options=self.runtime_options,
        )
```

Remove:

```python
import inspect
```

and delete the `_accepts_parameter` function.

- [ ] **Step 4: Run composition and CLI factory tests**

Run:

```bash
python -m unittest tests.test_workflow_composition tests.test_combined_cli tests.test_new_workflow_cli tests.test_salary_income_import_result tests.test_special_deduction_steps -v
```

Expected: pass.

---

### Task 7: Update Workflow Exports and Architecture Docs

**Files:**
- Modify: `tax_rpa/workflows/__init__.py`
- Modify: `docs/architecture_file_map.md`
- Modify: `docs/learning/02-architecture-walkthrough.md`
- Modify: `docs/learning/templates/new_page_step_workflow_template.md`

- [ ] **Step 1: Export workflow support classes**

Update `tax_rpa/workflows/__init__.py`:

```python
from tax_rpa.workflows.base import BusinessWorkflow
from tax_rpa.workflows.context import WorkflowContext
```

and add them to `__all__`:

```python
    "BusinessWorkflow",
    "WorkflowContext",
```

- [ ] **Step 2: Update architecture file map**

In `docs/architecture_file_map.md`, keep the main chain unchanged:

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

Add this note under the workflow section:

```markdown
`tax_rpa/workflows/base.py` and `tax_rpa/workflows/context.py` are workflow support code. They centralize lifecycle wrapping, runtime options, step execution, and `WorkflowResult` construction so concrete workflows only express business order.
```

- [ ] **Step 3: Update new workflow template**

Update `docs/learning/templates/new_page_step_workflow_template.md` so new workflows inherit `BusinessWorkflow` and implement `execute(self, app)` rather than copying constructor, `run`, `_run_step`, and `_failed` boilerplate.

- [ ] **Step 4: Run docs-adjacent tests**

Run:

```bash
python -m unittest tests.test_page_step_architecture tests.test_component_architecture -v
```

Expected: pass.

---

### Task 8: Full Regression

**Files:**
- No new files.

- [ ] **Step 1: Run workflow and job regression**

Run:

```bash
python -m unittest tests.test_workflow_composition tests.test_existing_workflow_executor tests.test_phase5_executor_integration tests.test_job_runner -v
```

Expected: pass.

- [ ] **Step 2: Verify job step observability still flows through `StepRunner`**

Run:

```bash
python -m unittest tests.test_existing_workflow_executor.ExistingWorkflowExecutorTests.test_job_runner_execute_no_send_self_check_reaches_salary_import_success -v
```

Expected:

- job state is `succeeded`
- executor business status is `existing_workflows_completed`
- the last `logs/steps.jsonl` event still has result matrix step `salary_income_import`
- the last result matrix outcome is `success`

- [ ] **Step 3: Verify lifecycle is not duplicated in combined workflow**

Run:

```bash
python -m unittest tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_runs_lifecycle_once_then_business_workflows_in_order tests.test_workflow_composition.WorkflowCompositionTests.test_combined_workflow_does_not_reset_between_successful_business_workflows -v
```

Expected:

- lifecycle events remain `start`, `wait_login` once for successful combined workflows
- no child workflow starts its own lifecycle inside `CombinedTaxWorkflow`

- [ ] **Step 4: Run full unit suite**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 5: Run CLI self-check if available in the environment**

Run:

```bash
python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

Expected: command completes and prints a summary path.

If this shell does not provide Windows `ctypes.windll` or the project virtualenv, record the environment limitation and rely on the unit suite.

---

## Expected Benefits

- Concrete workflow files become shorter and easier to scan.
- Business order is visible without reading repeated result wrapping.
- `CombinedTaxWorkflow` no longer needs signature introspection.
- Job observability still flows through `StepRunner`; workflows remain independent from concrete `jobs` modules.
- Existing step/page/component/driver boundaries remain stable.

## Compatibility Risks

- **Result metadata drift:** `WorkflowResult` fields must remain identical enough for `JobRunner`, `ExistingWorkflowExecutor`, result matrix tests, and callback summaries. Missing `error_type`, `error_code`, side-effect flags, or retry flags can change production behavior.
- **Side-effect under-reporting:** workflows must not derive side-effect fields only from the last step. Earlier import/submit/update steps may already have changed external state.
- **Retry safety regression:** any workflow that has started a business side effect must remain non-retryable unless a test explicitly proves the retry is safe.
- **Lifecycle duplication:** `CombinedTaxWorkflow` must keep starting lifecycle once and must call child `run_on_app(app)` or `execute(app)`, not child `run()`.
- **Job observability loss:** `WorkflowContext.step()` must preserve the `StepRunner` path so job logs, step journals, result matrix, and side-effect markers are still written.
- **Personnel import special branch:** `ImportPersonInfoWorkflow` has special post-submit unknown semantics; migrate it last and keep the branch visible.
- **Factory compatibility:** fake workflow factories in tests must accept `**kwargs` before removing introspection.
- **Production CLI factory compatibility:** `run_tax_workflow.py`, `import_salary_income.py`, and `update_special_deduction.py` must update their real workflow factories before introspection is removed.
- **Direct CLI/debug compatibility:** the old `run()` method should stay through this refactor for direct CLI/debug compatibility.
- **Constructor compatibility:** keep existing workflow constructor positional compatibility unless a separate, explicitly tested API cleanup is approved.
- **Over-abstraction:** do not introduce a workflow DSL or step descriptor registry in this pass.

## Success Criteria

- Full unit suite passes.
- Existing CLI self-check still succeeds where the environment supports it.
- `ExistingWorkflowExecutor` still reaches salary import success in fake-driver mode.
- Unknown personnel import still fails the job with `UNKNOWN_RESULT/person_import_result_unknown`.
- Personnel import that submitted/imported data still reports side effects and remains non-retryable.
- `logs/steps.jsonl` and `logs/step_journal.jsonl` still contain workflow step events in job-runner paths.
- Combined workflow lifecycle events remain single-owned and are not duplicated by child workflows.
- The architecture remains `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`.
