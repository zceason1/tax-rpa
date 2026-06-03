# Architecture Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the RPA architecture easier to understand by clarifying component ownership, removing page/workflow double orchestration, and preventing job concerns from leaking into UI/page code.

**Architecture:** Preserve the existing RPA layering: `CLI / Job -> Workflow -> Step -> Page -> Component -> Element / Driver`. This plan uses incremental compatibility shims, import-boundary tests, and small migrations instead of a broad rewrite. Job remains a production execution shell, while workflow owns business order and page/step code owns UI semantics.

**Tech Stack:** Python, `unittest`, Win32/OCR RPA abstractions, existing `StepResult` / `WorkflowResult` models.

---

## Target Boundaries

```text
tax_rpa/
  cli/                         # command-line entry points
  config/                      # configuration and static validation
  runtime/
    action_policy.py           # action decision model used by pages/components/jobs
    context.py                 # RPA runtime context
    result.py                  # StepResult / WorkflowResult
    step_runner.py             # workflow step instrumentation interface
  drivers/                     # Win32, OCR, mouse, UIA, wait, logging
  pages/
    shared/
      components/              # cross-page UI components
      elements/
    person_info/
      page.py                  # page object and page-level capabilities
      elements/
      components/              # page-owned UI components
      steps/                   # business steps
    comprehensive_income/
      ...
    special_deduction/
      ...
  workflows/                   # business process orchestration
  jobs/                        # production job shell, manifest, state, artifacts, callback
```

### Boundary Rules

- `workflows` may import `app`, `config`, `runtime`, and `pages.<page>.steps`.
- `workflows` must not import concrete `jobs` modules.
- `pages` and `components` may use `runtime.action_policy`, but must not import `tax_rpa.jobs`.
- `steps` call page methods and return `StepResult`; they do not call drivers directly.
- `Page` exposes page capabilities and creates components; it does not orchestrate full business workflows.
- `JobRunner` and `ExistingWorkflowExecutor` adapt manifests, artifacts, job logging, and callbacks to workflows.

## Migration Strategy

Use compatibility modules to avoid breaking existing imports during the migration. Each task should keep the full test suite green before continuing.

Recommended order:

1. Move action-policy primitives to `runtime`.
2. Replace workflow `job_context` coupling with a generic step runner.
3. Move shared UI components under `pages/shared/components`.
4. Remove `PersonInfoPage.import_person_file()` as a primary orchestration path.
5. Add import-boundary tests and update architecture docs.

---

### Task 1: Move Action Policy Out Of Jobs

**Files:**
- Create: `tax_rpa/runtime/action_policy.py`
- Modify: `tax_rpa/jobs/action_policy.py`
- Modify imports in:
  - `tax_rpa/components/content_text.py`
  - `tax_rpa/components/file_dialog.py`
  - `tax_rpa/components/left_nav.py`
  - `tax_rpa/components/message_dialog.py`
  - `tax_rpa/components/toolbar.py`
  - `tax_rpa/pages/person_info/components/import_dropdown.py`
  - `tax_rpa/workflows/job_context.py`
  - `tests/test_action_policy.py`
  - `tests/test_action_policy_components.py`
  - any other files found by `rg "tax_rpa.jobs.action_policy"`
- Test: `tests/test_action_policy.py`
- Test: `tests/test_action_policy_components.py`

- [ ] **Step 1: Write the compatibility test**

Add this test to `tests/test_action_policy.py`:

```python
def test_jobs_action_policy_reexports_runtime_action_policy(self):
    from tax_rpa.jobs import action_policy as jobs_action_policy
    from tax_rpa.runtime import action_policy as runtime_action_policy

    self.assertIs(jobs_action_policy.ActionPolicy, runtime_action_policy.ActionPolicy)
    self.assertIs(jobs_action_policy.ActionDecision, runtime_action_policy.ActionDecision)
    self.assertIs(jobs_action_policy.ActionDeniedError, runtime_action_policy.ActionDeniedError)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_policy -v
```

Expected: fail because `tax_rpa.runtime.action_policy` does not exist yet.

- [ ] **Step 3: Create runtime action policy implementation**

Create `tax_rpa/runtime/action_policy.py` by moving the full implementation currently in `tax_rpa/jobs/action_policy.py` into the runtime module without behavioral changes. The module must expose:

```python
RUN_MODES
READ_ONLY_ACTION_TYPES
SIDE_EFFECT_ACTION_TYPES
HIGH_RISK_LABELS
ActionDecision
ActionDeniedError
ActionAuditLogger
ActionPolicy
```

Keep `ActionAuditLogger` here for the first migration pass. It still writes to a path, but it is generic enough to be used outside `jobs`.

- [ ] **Step 4: Replace jobs module with a re-export shim**

Replace `tax_rpa/jobs/action_policy.py` with:

```python
from tax_rpa.runtime.action_policy import (
    HIGH_RISK_LABELS,
    READ_ONLY_ACTION_TYPES,
    RUN_MODES,
    SIDE_EFFECT_ACTION_TYPES,
    ActionAuditLogger,
    ActionDecision,
    ActionDeniedError,
    ActionPolicy,
)


__all__ = [
    "RUN_MODES",
    "READ_ONLY_ACTION_TYPES",
    "SIDE_EFFECT_ACTION_TYPES",
    "HIGH_RISK_LABELS",
    "ActionDecision",
    "ActionDeniedError",
    "ActionAuditLogger",
    "ActionPolicy",
]
```

- [ ] **Step 5: Move component/page imports to runtime**

For UI and page code, replace:

```python
from tax_rpa.jobs.action_policy import ActionPolicy
```

with:

```python
from tax_rpa.runtime.action_policy import ActionPolicy
```

Apply this to:

```text
tax_rpa/components/content_text.py
tax_rpa/components/file_dialog.py
tax_rpa/components/left_nav.py
tax_rpa/components/message_dialog.py
tax_rpa/components/toolbar.py
tax_rpa/pages/person_info/components/import_dropdown.py
tax_rpa/workflows/job_context.py
tests/test_action_policy.py
tests/test_action_policy_components.py
tests/test_special_deduction_steps.py
```

Leave `tax_rpa/jobs/existing_workflow_executor.py` importing from `tax_rpa.jobs.action_policy` for now, because it is job-layer code and the shim keeps it stable.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_policy tests.test_action_policy_components tests.test_special_deduction_steps -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add tax_rpa/runtime/action_policy.py tax_rpa/jobs/action_policy.py tax_rpa/components tax_rpa/pages tests
git commit -m "refactor: move action policy to runtime"
```

---

### Task 2: Split Job Context Into Runtime Inputs

**Files:**
- Create: `tax_rpa/runtime/step_runner.py`
- Create: `tax_rpa/runtime/workflow_options.py`
- Create: `tax_rpa/jobs/workflow_step_runner.py`
- Delete: `tax_rpa/workflows/job_context.py`
- Modify: `tax_rpa/jobs/existing_workflow_executor.py`
- Modify workflow constructor parameters in:
  - `tax_rpa/workflows/import_person_info_workflow.py`
  - `tax_rpa/workflows/import_salary_income_workflow.py`
  - `tax_rpa/workflows/update_special_deduction_workflow.py`
  - `tax_rpa/workflows/prefill_deduction_workflow.py`
  - `tax_rpa/workflows/tax_calculation_workflow.py`
  - `tax_rpa/workflows/declaration_submission_workflow.py`
  - `tax_rpa/workflows/export_report_workflow.py`
  - `tax_rpa/workflows/combined_tax_workflow.py`
- Test: `tests/test_workflow_job_context.py`
- Test: `tests/test_phase4_workflow_migration.py`
- Test: `tests/test_existing_workflow_executor.py`
- Test: `tests/test_phase5_workflows.py`

- [ ] **Step 1: Add runtime step runner and workflow options tests**

Create `tests/test_runtime_step_runner.py`:

```python
import unittest
from types import SimpleNamespace

from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.step_runner import DirectStepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


class DirectStepRunnerTests(unittest.TestCase):
    def test_run_step_executes_operation_without_job_dependencies(self):
        calls = []
        runner = DirectStepRunner()

        result = runner.run_step(
            workflow="sample_workflow",
            step="sample.step",
            operation=lambda: calls.append("ran")
            or StepResult(ok=True, name="sample.step", status="ok"),
            matrix_step="sample_matrix",
            side_effect_step=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ok")
        self.assertEqual(calls, ["ran"])

    def test_workflow_options_default_from_dry_run_config(self):
        dry_run_options = WorkflowRuntimeOptions.from_config(SimpleNamespace(dry_run=True))
        execute_options = WorkflowRuntimeOptions.from_config(SimpleNamespace(dry_run=False))

        self.assertEqual(dry_run_options.run_mode, "inspect_only")
        self.assertEqual(execute_options.run_mode, "execute_no_send")
        self.assertFalse(execute_options.allow_skip_personal_pension)

    def test_workflow_options_can_carry_manifest_derived_business_flags(self):
        options = WorkflowRuntimeOptions(
            run_mode="execute_no_send",
            allow_skip_personal_pension=True,
        )

        self.assertEqual(options.run_mode, "execute_no_send")
        self.assertTrue(options.allow_skip_personal_pension)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runtime_step_runner -v
```

Expected: fail because `tax_rpa.runtime.step_runner` and `tax_rpa.runtime.workflow_options` do not exist.

- [ ] **Step 3: Create runtime step runner module**

Create `tax_rpa/runtime/step_runner.py`:

```python
from collections.abc import Callable
from typing import Protocol

from tax_rpa.runtime.result import StepResult


class StepRunner(Protocol):
    def run_step(
        self,
        *,
        workflow: str,
        step: str,
        operation: Callable[[], StepResult],
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        ...


class DirectStepRunner:
    def run_step(
        self,
        *,
        workflow: str,
        step: str,
        operation: Callable[[], StepResult],
        matrix_step: str | None = None,
        side_effect_step: bool = False,
    ) -> StepResult:
        return operation()
```

- [ ] **Step 4: Create workflow runtime options**

Create `tax_rpa/runtime/workflow_options.py`:

```python
from dataclasses import dataclass
from typing import Any

from tax_rpa.runtime.action_policy import RUN_MODES


@dataclass(frozen=True)
class WorkflowRuntimeOptions:
    run_mode: str
    allow_skip_personal_pension: bool = False

    def __post_init__(self) -> None:
        if self.run_mode not in RUN_MODES:
            raise ValueError(f"Unsupported run_mode: {self.run_mode}")

    @classmethod
    def from_config(cls, config: Any) -> "WorkflowRuntimeOptions":
        return cls(
            run_mode="inspect_only" if getattr(config, "dry_run", False) else "execute_no_send",
        )
```

- [ ] **Step 5: Move concrete job step instrumentation to jobs**

Create `tax_rpa/jobs/workflow_step_runner.py` with the current `WorkflowJobContext` implementation moved from `tax_rpa/workflows/job_context.py`. Rename the class to `JobStepRunner`.

The constructor fields are:

```python
manifest: JobManifest
artifacts: JobArtifacts
observability: JobObservability
attempt: int = 1
```

The method remains:

```python
def run_step(
    self,
    *,
    workflow: str,
    step: str,
    operation: Callable[[], StepResult],
    matrix_step: str | None = None,
    side_effect_step: bool = False,
) -> StepResult:
```

Do not add `action_policy` to `JobStepRunner`. `StepRunner` only instruments step execution; it is not the source of click permissions.

- [ ] **Step 6: Remove workflow job context module**

Delete `tax_rpa/workflows/job_context.py`.

Do not replace it with a re-export shim. A shim from `workflows` to `jobs` preserves the exact dependency direction this migration is trying to remove.

- [ ] **Step 7: Update tests that imported WorkflowJobContext**

Replace:

```python
from tax_rpa.workflows.job_context import WorkflowJobContext
```

with:

```python
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
```

Then replace `WorkflowJobContext(` with `JobStepRunner(` in:

```text
tests/test_workflow_job_context.py
tests/test_phase4_workflow_migration.py
```

Rename `WorkflowJobContextTests` to `JobStepRunnerTests` in `tests/test_workflow_job_context.py`.

- [ ] **Step 8: Update ExistingWorkflowExecutor**

In `tax_rpa/jobs/existing_workflow_executor.py`, replace:

```python
from tax_rpa.workflows.job_context import WorkflowJobContext
```

with:

```python
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
```

Then replace:

```python
job_context = WorkflowJobContext(
```

with:

```python
step_runner = JobStepRunner(
```

Create explicit workflow runtime inputs:

```python
runtime_options = WorkflowRuntimeOptions(
    run_mode=manifest.run_mode,
    allow_skip_personal_pension=manifest.allow_skip_personal_pension,
)
```

Pass it into `CombinedTaxWorkflow` as:

```python
step_runner=step_runner,
runtime_options=runtime_options,
action_policy=action_policy,
```

- [ ] **Step 9: Add explicit runtime inputs to business workflows**

For each workflow constructor, replace:

```python
job_context: Any | None = None,
```

with:

```python
runtime_options: WorkflowRuntimeOptions | None = None,
step_runner: Any | None = None,
job_context: Any | None = None,
```

Import:

```python
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
```

Set:

```python
self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
self.step_runner = step_runner or job_context
```

Keep `job_context` accepted only as a short-term constructor alias for older callers. Do not read `.manifest`, `.action_policy`, or any other job-specific attribute from it.

Update `_run_step` from:

```python
if self.job_context is None:
    return operation()
return self.job_context.run_step(...)
```

to:

```python
if self.step_runner is None:
    return operation()
return self.step_runner.run_step(...)
```

Update manifest-derived logic:

In `tax_rpa/workflows/prefill_deduction_workflow.py`, replace:

```python
def _allow_skip_personal_pension(self) -> bool:
    manifest = getattr(self.job_context, "manifest", None)
    return bool(getattr(manifest, "allow_skip_personal_pension", False))
```

with:

```python
def _allow_skip_personal_pension(self) -> bool:
    return self.runtime_options.allow_skip_personal_pension
```

In `tax_rpa/workflows/declaration_submission_workflow.py` and `tax_rpa/workflows/export_report_workflow.py`, replace `_run_mode()` with:

```python
def _run_mode(self) -> str:
    return self.runtime_options.run_mode
```

- [ ] **Step 10: Update CombinedTaxWorkflow factory plumbing**

In `tax_rpa/workflows/combined_tax_workflow.py`, add explicit runtime inputs:

```python
runtime_options: WorkflowRuntimeOptions | None = None,
step_runner: Any | None = None,
action_policy: Any | None = None,
job_context: Any | None = None,
```

Set:

```python
self.runtime_options = runtime_options or WorkflowRuntimeOptions.from_config(config)
self.step_runner = step_runner or job_context
self.action_policy = action_policy
```

Replace `_attach_job_context()` with `_attach_action_policy()`:

```python
def _attach_action_policy(self, app: Any) -> None:
    if self.action_policy is None:
        return
    app_context = getattr(app, "context", None)
    if app_context is None:
        return
    if hasattr(app_context, "action_policy"):
        app_context.action_policy = self.action_policy
```

Call `_attach_action_policy(lifecycle.app)` after lifecycle startup and after reset recovery. Do not read `action_policy` from `step_runner` or `job_context`.

Replace positional third-argument probing with keyword-based construction:

```python
def _build_business_workflow(self, factory: BusinessWorkflowFactory) -> Any:
    kwargs: dict[str, Any] = {}
    if self.step_runner is not None and _accepts_parameter(factory, "step_runner"):
        kwargs["step_runner"] = self.step_runner
    elif self.step_runner is not None and _accepts_parameter(factory, "job_context"):
        kwargs["job_context"] = self.step_runner
    if _accepts_parameter(factory, "runtime_options"):
        kwargs["runtime_options"] = self.runtime_options
    return factory(self.config, self.logger, **kwargs)
```

Add helper:

```python
def _accepts_parameter(factory: BusinessWorkflowFactory, name: str) -> bool:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return False
    parameters = signature.parameters
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return True
    return name in parameters
```

Delete `_accepts_job_context`.

- [ ] **Step 11: Update ExistingWorkflowExecutor factories**

Change factory lambdas from:

```python
lambda config, logger, job_context=None: ImportPersonInfoWorkflow(
    config,
    logger,
    job_context=job_context,
)
```

to:

```python
lambda config, logger, step_runner=None, runtime_options=None: ImportPersonInfoWorkflow(
    config,
    logger,
    step_runner=step_runner,
    runtime_options=runtime_options,
)
```

Apply the same pattern to all workflow factories in `ExistingWorkflowExecutor._workflow_factories()`.

- [ ] **Step 12: Add behavior tests for separated runtime inputs**

Add to `tests/test_phase5_workflows.py`:

```python
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


def test_prefill_workflow_uses_runtime_options_for_pension_skip(self):
    events = []
    config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
    workflow = PrefillDeductionWorkflow(
        config=config,
        logger=None,
        runtime_options=WorkflowRuntimeOptions(
            run_mode="execute_no_send",
            allow_skip_personal_pension=True,
        ),
        app_factory=lambda config, logger: FakeApp(events),
    )

    with (
        patch(
            "tax_rpa.workflows.prefill_deduction_workflow.OpenComprehensiveIncomePageStep",
            FakeOpenComprehensiveIncomePageStep,
        ),
        patch(
            "tax_rpa.workflows.prefill_deduction_workflow.OpenSalaryIncomeFormStep",
            FakeOpenSalaryIncomeFormStep,
        ),
        patch(
            "tax_rpa.workflows.prefill_deduction_workflow.PrefillDeductionStep",
            FakePrefillDeductionStep,
        ),
    ):
        result = workflow.run()

    self.assertTrue(result.ok)
    self.assertIn("confirm_prefill_options:True", events)
```

If the existing fake class names differ, reuse the existing fake app/page/step names already defined in `tests/test_phase5_workflows.py`; the assertion must prove the value came from `WorkflowRuntimeOptions`, not `JobManifest`.

Add to `tests/test_workflow_composition.py`:

```python
def test_combined_workflow_attaches_explicit_action_policy_not_step_runner_policy(self):
    events = []
    policy = object()

    class FakeAppWithContext(FakeApp):
        def __init__(self, events):
            super().__init__(events)
            self.context = SimpleNamespace(action_policy=None)

    workflow = CombinedTaxWorkflow(
        config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
        logger=None,
        workflow_factories=[],
        app_factory=lambda config, logger: FakeAppWithContext(events),
        step_runner=DirectStepRunner(),
        action_policy=policy,
    )

    result = workflow.run()

    self.assertTrue(result.ok)
```

Extend this test so it asserts the app context action policy was set. Store the fake app in a local holder:

```python
holder = {}
app_factory=lambda config, logger: holder.setdefault("app", FakeAppWithContext(events))
...
self.assertIs(holder["app"].context.action_policy, policy)
```

- [ ] **Step 13: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_runtime_step_runner tests.test_workflow_job_context tests.test_phase4_workflow_migration tests.test_existing_workflow_executor tests.test_phase5_executor_integration -v
```

Expected: all tests pass.

- [ ] **Step 14: Commit**

```powershell
git add tax_rpa/runtime/step_runner.py tax_rpa/runtime/workflow_options.py tax_rpa/jobs/workflow_step_runner.py tax_rpa/workflows tax_rpa/jobs tests
git rm tax_rpa/workflows/job_context.py
git commit -m "refactor: split job context into runtime inputs"
```

---

### Task 3: Move Shared Components Under Pages Shared

**Files:**
- Create package: `tax_rpa/pages/shared/components/`
- Move implementation modules:
  - `tax_rpa/components/content_text.py` -> `tax_rpa/pages/shared/components/content_text.py`
  - `tax_rpa/components/file_dialog.py` -> `tax_rpa/pages/shared/components/file_dialog.py`
  - `tax_rpa/components/left_nav.py` -> `tax_rpa/pages/shared/components/left_nav.py`
  - `tax_rpa/components/message_dialog.py` -> `tax_rpa/pages/shared/components/message_dialog.py`
  - `tax_rpa/components/toolbar.py` -> `tax_rpa/pages/shared/components/toolbar.py`
- Keep compatibility shims in old paths.
- Leave `tax_rpa/components/login.py` in place for now because it belongs to app login, not page-shared components.
- Test: `tests/test_component_architecture.py`
- Test: `tests/test_page_step_architecture.py`
- Test: `tests/test_action_policy_components.py`

- [ ] **Step 1: Add shared component package existence test**

Add this to `tests/test_component_architecture.py`:

```python
def test_shared_components_live_under_pages_shared(self):
    modules = [
        "tax_rpa.pages.shared.components.content_text",
        "tax_rpa.pages.shared.components.file_dialog",
        "tax_rpa.pages.shared.components.left_nav",
        "tax_rpa.pages.shared.components.message_dialog",
        "tax_rpa.pages.shared.components.toolbar",
    ]

    for module_name in modules:
        with self.subTest(module=module_name):
            self.assertIsNotNone(__import__(module_name, fromlist=["*"]))
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_component_architecture -v
```

Expected: fail because `tax_rpa.pages.shared.components` does not exist.

- [ ] **Step 3: Create shared component package**

Create `tax_rpa/pages/shared/components/__init__.py`:

```python
from tax_rpa.pages.shared.components.content_text import ContentTextComponent
from tax_rpa.pages.shared.components.file_dialog import FileDialogComponent
from tax_rpa.pages.shared.components.left_nav import LeftNavComponent
from tax_rpa.pages.shared.components.message_dialog import MessageDialogComponent
from tax_rpa.pages.shared.components.toolbar import ToolbarComponent


__all__ = [
    "ContentTextComponent",
    "FileDialogComponent",
    "LeftNavComponent",
    "MessageDialogComponent",
    "ToolbarComponent",
]
```

- [ ] **Step 4: Move implementations**

Move the implementation code from these old files to the new files:

```text
tax_rpa/pages/shared/components/content_text.py
tax_rpa/pages/shared/components/file_dialog.py
tax_rpa/pages/shared/components/left_nav.py
tax_rpa/pages/shared/components/message_dialog.py
tax_rpa/pages/shared/components/toolbar.py
```

Inside the moved files, update imports to use:

```python
from tax_rpa.runtime.action_policy import ActionPolicy
```

- [ ] **Step 5: Convert old component paths to shims**

For each old shared component file, replace the implementation with a re-export. Example for `tax_rpa/components/toolbar.py`:

```python
from tax_rpa.pages.shared.components.toolbar import ToolbarComponent


__all__ = ["ToolbarComponent"]
```

Use equivalent shims for:

```text
tax_rpa/components/content_text.py
tax_rpa/components/file_dialog.py
tax_rpa/components/left_nav.py
tax_rpa/components/message_dialog.py
tax_rpa/components/toolbar.py
```

- [ ] **Step 6: Update imports in page code**

Replace imports in page modules:

```python
from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.components.toolbar import ToolbarComponent
from tax_rpa.components.content_text import ContentTextComponent
```

with:

```python
from tax_rpa.pages.shared.components.file_dialog import FileDialogComponent
from tax_rpa.pages.shared.components.left_nav import LeftNavComponent
from tax_rpa.pages.shared.components.toolbar import ToolbarComponent
from tax_rpa.pages.shared.components.content_text import ContentTextComponent
```

Update:

```text
tax_rpa/pages/person_info/page.py
tax_rpa/pages/comprehensive_income/page.py
tax_rpa/pages/special_deduction/page.py
tax_rpa/pages/shared/dialogs.py
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_component_architecture tests.test_page_step_architecture tests.test_action_policy_components tests.test_page_dialog_handling -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add tax_rpa/pages/shared/components tax_rpa/components tax_rpa/pages tests
git commit -m "refactor: move shared UI components under pages shared"
```

---

### Task 4: Make Workflow The Only Person Import Orchestrator

**Files:**
- Modify: `tax_rpa/pages/person_info/page.py`
- Modify: `tax_rpa/cli/debug_person_info_page.py`
- Modify: `tests/test_component_architecture.py`
- Modify or create: `tests/test_debug_person_info_page.py`
- Test: `tests/test_page_step_architecture.py`
- Test: `tests/test_workflow_composition.py`

- [ ] **Step 1: Add debug CLI test for step-based import-flow**

Add this test to `tests/test_debug_person_info_page.py`:

```python
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.cli.debug_person_info_page import run_debug_action
from tax_rpa.runtime.result import StepResult


class DebugPersonInfoPageImportFlowTests(unittest.TestCase):
    def test_import_flow_uses_steps_instead_of_page_import_person_file(self):
        events = []

        class FakeApp:
            context = SimpleNamespace(hwnd=100)

        class FakePage:
            def __init__(self, context, hwnd):
                self.context = context
                self.hwnd = hwnd

            def open(self):
                events.append("open")
                return StepResult(ok=True, name="page.open", status="opened")

            def import_person_file(self, _path):
                raise AssertionError("debug CLI must not use page.import_person_file")

        class FakeImportStep:
            def __init__(self, page):
                self.page = page

            def run(self, path):
                events.append(f"import:{path.name}")
                return StepResult(ok=True, name="person_info.import_person_file", status="dry_run")

        class FakeWaitStep:
            def __init__(self, page):
                self.page = page

            def run(self):
                events.append("wait")
                return StepResult(ok=True, name="person_info.wait_import_result", status="success")

        config = SimpleNamespace(person_info_file=Path("persons.xlsx"))
        logger = SimpleNamespace()

        with (
            patch("tax_rpa.cli.debug_person_info_page.attach_app", return_value=FakeApp()),
            patch("tax_rpa.cli.debug_person_info_page.PersonInfoPage", FakePage),
            patch("tax_rpa.cli.debug_person_info_page.ImportPersonFileStep", FakeImportStep),
            patch("tax_rpa.cli.debug_person_info_page.WaitImportResultStep", FakeWaitStep),
        ):
            summary = run_debug_action("import-flow", config, logger, launch=False)

        self.assertEqual(events, ["open", "import:persons.xlsx", "wait"])
        self.assertTrue(summary["result"].ok)
        self.assertEqual(summary["result"].status, "success")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_debug_person_info_page -v
```

Expected: fail because debug CLI still calls `page.import_person_file()`.

- [ ] **Step 3: Update debug CLI to use steps**

In `tax_rpa/cli/debug_person_info_page.py`, add imports:

```python
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep
```

Replace:

```python
import_result = page.import_person_file(config.person_info_file)
return {
    "action": action,
    "open": open_result,
    "result": import_result,
}
```

with:

```python
import_file = ImportPersonFileStep(page).run(config.person_info_file)
if not import_file.ok:
    return {
        "action": action,
        "open": open_result,
        "import_file": import_file,
        "result": import_file,
    }

validation_result = WaitImportResultStep(page).run()
if validation_result.status != "ready_to_submit":
    return {
        "action": action,
        "open": open_result,
        "import_file": import_file,
        "result": validation_result,
    }

submit_result = SubmitImportDataStep(page).run()
if not submit_result.ok:
    return {
        "action": action,
        "open": open_result,
        "import_file": import_file,
        "validation_result": validation_result,
        "submit_result": submit_result,
        "result": submit_result,
    }

import_result = WaitImportResultStep(page).run()
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
return {
    "action": action,
    "open": open_result,
    "import_file": import_file,
    "validation_result": validation_result,
    "submit_result": submit_result,
    "result": import_result,
}
```

- [ ] **Step 4: Remove page-level step orchestration**

In `tax_rpa/pages/person_info/page.py`, delete the `import_person_file()` method entirely:

```python
def import_person_file(self, path: Path) -> StepResult:
    from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
    from tax_rpa.pages.person_info.steps.submit_import_data import SubmitImportDataStep
    from tax_rpa.pages.person_info.steps.wait_import_result import WaitImportResultStep

    ...
```

Keep the lower-level page capability methods:

```python
click_import_button()
choose_import_file_option()
click_submit_data()
choose_person_file()
read_import_result()
```

These are what `ImportPersonFileStep`, `SubmitImportDataStep`, and `WaitImportResultStep` should call.

- [ ] **Step 5: Update legacy component architecture tests**

In `tests/test_component_architecture.py`, remove or rewrite tests that call `page.import_person_file(...)`:

```text
test_person_info_page_composes_components_for_import
test_person_info_page_wraps_import_flow_in_named_steps
test_person_info_page_stops_when_submit_data_does_not_finalize_import
```

Replace them with step-level tests that instantiate `ImportPersonFileStep`, `WaitImportResultStep`, and `SubmitImportDataStep` with a fake `PersonInfoPage`. The assertions should continue proving the same button/menu/file/result order, but the orchestrator under test must be the step or workflow, not `PersonInfoPage`.

- [ ] **Step 6: Add architecture test preventing Page from importing steps**

Add this to `tests/test_page_step_architecture.py`:

```python
def test_page_objects_do_not_import_page_steps(self):
    page_files = Path("tax_rpa/pages").rglob("page.py")
    violations = []
    for path in page_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("tax_rpa.pages") and ".steps" in module:
                    violations.append(f"{path}:{module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tax_rpa.pages") and ".steps" in alias.name:
                        violations.append(f"{path}:{alias.name}")

    self.assertEqual(violations, [])
```

- [ ] **Step 7: Add architecture test preventing workflow calls to Page.import_person_file**

Add this to `tests/test_page_step_architecture.py`:

```python
def test_workflows_do_not_call_page_import_person_file(self):
    workflow_files = Path("tax_rpa/workflows").glob("*_workflow.py")
    violations = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        if ".import_person_file(" in text:
            violations.append(str(path))

    self.assertEqual(violations, [])
```

- [ ] **Step 8: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_debug_person_info_page tests.test_page_step_architecture tests.test_workflow_composition tests.test_component_architecture -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add tax_rpa/cli/debug_person_info_page.py tax_rpa/pages/person_info/page.py tests
git commit -m "refactor: route person import flow through steps"
```

---

### Task 5: Add Import Boundary Tests And Update Docs

**Files:**
- Create: `tests/test_architecture_boundaries.py`
- Modify: `docs/learning/01-project-map.md`
- Modify: `docs/learning/02-architecture-walkthrough.md`
- Modify: `docs/learning/05-extension-playbook.md`
- Modify: `docs/rpa_page_step_architecture.md`
- Modify: `docs/rpa_component_architecture.md`

- [ ] **Step 1: Add import boundary test**

Create `tests/test_architecture_boundaries.py`:

```python
import ast
import unittest
from pathlib import Path


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_workflows_do_not_import_jobs(self):
        violations = []
        for path in Path("tax_rpa/workflows").glob("*.py"):
            for module in imported_modules(path):
                if module.startswith("tax_rpa.jobs"):
                    violations.append(f"{path}:{module}")

        self.assertEqual(violations, [])

    def test_pages_and_components_do_not_import_jobs(self):
        roots = [Path("tax_rpa/pages"), Path("tax_rpa/components")]
        violations = []
        for root in roots:
            for path in root.rglob("*.py"):
                for module in imported_modules(path):
                    if module.startswith("tax_rpa.jobs"):
                        violations.append(f"{path}:{module}")

        self.assertEqual(violations, [])

    def test_page_steps_do_not_import_drivers(self):
        violations = []
        for path in Path("tax_rpa/pages").rglob("steps/*.py"):
            for module in imported_modules(path):
                if module.startswith("tax_rpa.drivers"):
                    violations.append(f"{path}:{module}")

        self.assertEqual(violations, [])

    def test_page_objects_do_not_import_page_steps(self):
        violations = []
        for path in Path("tax_rpa/pages").rglob("page.py"):
            for module in imported_modules(path):
                if module.startswith("tax_rpa.pages") and ".steps" in module:
                    violations.append(f"{path}:{module}")

        self.assertEqual(violations, [])

    def test_workflows_job_context_module_removed(self):
        self.assertFalse(Path("tax_rpa/workflows/job_context.py").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run boundary test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_architecture_boundaries -v
```

Expected: pass after Tasks 1-4 are complete.

- [ ] **Step 3: Update docs project map**

In `docs/learning/01-project-map.md`, update the directory table to say:

```markdown
| `tax_rpa/pages/shared/components` | 跨页面复用的 UI 操作组件，例如 toolbar、file dialog、left nav、message dialog。 |
| `tax_rpa/components` | 旧路径兼容层；新增页面组件不要放这里。 |
| `tax_rpa/jobs` | Job 运行、状态、锁、preflight、安全审计、观测、回调、生产门禁。Job 调用 workflow executor，不直接操作 page/component。 |
```

Update the main chain to:

```text
tax_rpa.cli.run_tax_workflow
  -> CombinedTaxWorkflow.run()
  -> AppLifecycleWorkflow.run()
  -> business workflow.run_on_app()
  -> Open*PageStep
  -> Business Step
  -> Page capability
  -> Shared/Page Component
  -> Driver
```

- [ ] **Step 4: Update architecture walkthrough**

In `docs/learning/02-architecture-walkthrough.md`, make the layer model:

```text
CLI / Job
  -> Workflow
    -> Step
      -> Page
        -> Component
          -> Element / Driver
```

Add this clarification:

```markdown
`Job` 不是页面自动化层的一部分。它负责生产运行治理，包括 manifest、preflight、锁、状态、产物、回调和审计。业务顺序仍由 `Workflow` 编排，页面动作仍由 `Step/Page/Component` 执行。
```

- [ ] **Step 5: Update extension playbook**

In `docs/learning/05-extension-playbook.md`, replace "接入 Job 上下文" with "接入 StepRunner":

```python
def _run_step(self, step: str, operation: Callable[[], StepResult]) -> StepResult:
    if self.step_runner is None:
        return operation()
    return self.step_runner.run_step(
        workflow="your_workflow",
        step=step,
        operation=operation,
    )
```

Add:

```markdown
Workflow should accept `step_runner` and `runtime_options` as explicit constructor arguments. `job_context` is only a short migration alias inside workflow constructors; no workflow may import `tax_rpa.workflows.job_context` or read `JobManifest` fields directly.
```

- [ ] **Step 6: Update component architecture docs**

In `docs/rpa_component_architecture.md` and `docs/rpa_page_step_architecture.md`, update component guidance:

```markdown
- Cross-page components live in `tax_rpa/pages/shared/components`.
- Page-owned components live in `tax_rpa/pages/<page>/components`.
- `tax_rpa/components` is a compatibility package for old imports; do not add new shared component implementations there.
```

Update person import guidance:

```markdown
`PersonInfoPage` exposes page capabilities such as `click_import_button()`, `choose_person_file()`, and `read_import_result()`. It must not import or orchestrate page steps. New code should compose `ImportPersonFileStep`, `WaitImportResultStep`, and `SubmitImportDataStep` from workflow or debug tooling.
```

- [ ] **Step 7: Run architecture and doc-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_architecture_boundaries tests.test_page_step_architecture tests.test_component_architecture tests.test_workflow_composition -v
```

Expected: all tests pass.

- [ ] **Step 8: Run full suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```powershell
git add tests/test_architecture_boundaries.py docs tax_rpa
git commit -m "test: enforce architecture boundaries"
```

---

## Rollout Notes

- Do not delete compatibility shims in the same migration. Keep old imports working until downstream scripts and docs have been updated.
- Do not move `tax_rpa/components/login.py` in this plan. It is app-login specific and should be reviewed separately with `tax_rpa/app`.
- Do not introduce a new dependency injection framework. Existing constructor injection is sufficient.
- Do not change RPA behavior, OCR thresholds, click strategy, retry policy, or run modes in this cleanup.
- Treat `job_context` as a short migration alias after Task 2. New code must use `step_runner`, `runtime_options`, and explicit `action_policy`.
- Do not keep a `tax_rpa/workflows/job_context.py` re-export shim. It would preserve a `workflows -> jobs` dependency and undermine the import-boundary tests.

## Acceptance Criteria

- New shared component implementations live under `tax_rpa/pages/shared/components`.
- `tax_rpa/components` contains only compatibility shims plus explicitly app-owned legacy modules.
- UI/page/component code does not import `tax_rpa.jobs`.
- Workflow code does not import concrete job modules.
- `tax_rpa/workflows/job_context.py` is removed; job step instrumentation lives in `tax_rpa/jobs/workflow_step_runner.py`.
- Workflow code receives manifest-derived values via `WorkflowRuntimeOptions`, not by reading `JobManifest`.
- `CombinedTaxWorkflow` receives `action_policy` explicitly and does not read it from `step_runner`.
- Page objects do not import or orchestrate page steps.
- Person import production workflow and debug import-flow both compose page steps explicitly.
- Architecture docs match the code structure.
- Full `unittest` suite passes.
