# Phase 0 Baseline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove current unsafe behavior before adding the job layer or new tax declaration workflows.

**Architecture:** This phase keeps the current workflow/page/component structure and hardens the existing runtime contracts. It makes unknown results fail, page navigation failures stop immediately, salary import wait for a result, and automatic retry respect side-effect metadata.

**Tech Stack:** Python 3, `unittest`, existing `tax_rpa` package, fake-driver/fake-page tests.

---

## Scope Check

The full unattended tax RPA spec covers multiple subsystems. This plan implements only Phase 0 from `docs/superpowers/specs/2026-05-24-unattended-tax-rpa-design.md`.

Later plans cover:

- Phase 1: job manifest, state store, artifact store, lock, preflight.
- Phase 2: `ActionPolicy`, `SubmitAuthorization`, high-risk click interception.
- Phase 3: job-scoped observability and troubleshooting package.
- Phase 4-7: workflow migration, new business workflows, callback, retention, canary.

Do not implement those later phases in this plan.

## File Structure

Files to modify:

- `tax_rpa/runtime/result.py`
  Add retry and side-effect metadata to `StepResult` and `WorkflowResult` with safe defaults.

- `tax_rpa/pages/person_info/components/import_result.py`
  Treat only `success` as `ok=True`; `failed` and `unknown` are failures.

- `tax_rpa/app/main_shell.py`
  Check each page `open()` result and raise immediately when navigation fails.

- `tax_rpa/workflows/recovery_policy.py`
  Add retry-safety helpers that inspect side-effect metadata.

- `tax_rpa/workflows/combined_tax_workflow.py`
  Retry only when environment failure is recoverable and the failed workflow is retry-safe.

- `tax_rpa/pages/comprehensive_income/page.py`
  Add an injectable salary import result reader and page method for reading salary import result.

- `tax_rpa/pages/comprehensive_income/elements/import_result.py`
  Add classification texts for salary import success/failure.

- `tax_rpa/pages/comprehensive_income/components/import_result.py`
  Add salary import result reader based on dialogs and OCR.

- `tax_rpa/pages/comprehensive_income/steps/import_salary_income_data.py`
  After file submission, wait for explicit salary import result.

Tests to create or modify:

- `tests/test_runtime_result_metadata.py`
- `tests/test_import_result_component.py`
- `tests/test_main_shell_open_checks.py`
- `tests/test_workflow_composition.py`
- `tests/test_comprehensive_income_steps.py`
- `tests/test_salary_income_import_result.py`

## Task 1: Add Runtime Result Metadata

**Files:**
- Modify: `tax_rpa/runtime/result.py`
- Test: `tests/test_runtime_result_metadata.py`

- [ ] **Step 1: Write the failing metadata tests**

Create `tests/test_runtime_result_metadata.py`:

```python
import unittest

from tax_rpa.runtime.result import StepResult, WorkflowResult


class RuntimeResultMetadataTests(unittest.TestCase):
    def test_step_result_defaults_are_retry_safe_for_existing_callers(self):
        result = StepResult(ok=True, name="step", status="ok")

        self.assertFalse(result.side_effect_started)
        self.assertFalse(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)
        self.assertEqual(result.evidence_paths, [])
        self.assertEqual(result.ui_text, [])

    def test_workflow_result_defaults_are_retry_safe_for_existing_callers(self):
        result = WorkflowResult(ok=False, name="workflow", status="timeout")

        self.assertFalse(result.side_effect_started)
        self.assertFalse(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_runtime_result_metadata -v
```

Expected: FAIL with `AttributeError` for `side_effect_started`.

- [ ] **Step 3: Add metadata fields**

Replace `tax_rpa/runtime/result.py` with:

```python
from dataclasses import dataclass, field
from typing import Any


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


@dataclass(frozen=True)
class WorkflowResult:
    ok: bool
    name: str
    status: str
    steps: list[StepResult] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    side_effect_started: bool = False
    side_effect_committed: bool = False
    retry_allowed: bool = False
```

- [ ] **Step 4: Run metadata tests**

Run:

```powershell
python -m unittest tests.test_runtime_result_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Run existing result-adjacent tests**

Run:

```powershell
python -m unittest tests.test_workflow_composition tests.test_app_lifecycle_workflow tests.test_component_architecture -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tax_rpa/runtime/result.py tests/test_runtime_result_metadata.py
git commit -m "feat: add runtime result metadata"
```

## Task 2: Treat Unknown Personnel Import Result As Failure

**Files:**
- Modify: `tax_rpa/pages/person_info/components/import_result.py`
- Test: `tests/test_import_result_component.py`

- [ ] **Step 1: Write failing component tests**

Create `tests/test_import_result_component.py`:

```python
import unittest
from types import SimpleNamespace

from tax_rpa.pages.person_info.components.import_result import ImportResultComponent


class FakeLogger:
    def screenshot(self, *_args, **_kwargs):
        return "screenshot.png"

    def log(self, *_args, **_kwargs):
        pass


class FixedImportResultComponent(ImportResultComponent):
    def __init__(self, status):
        super().__init__(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(dry_run=False, result_timeout_seconds=1),
            allowed_pids={1},
        )
        self.fixed_status = status

    def wait_for_import_result(self):
        return {"status": self.fixed_status, "source": "test"}


class ImportResultComponentTests(unittest.TestCase):
    def test_success_result_is_ok(self):
        result = FixedImportResultComponent("success").read_result()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")

    def test_failed_result_is_not_ok(self):
        result = FixedImportResultComponent("failed").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_type, "IMPORT_FAILED")

    def test_unknown_result_is_not_ok(self):
        result = FixedImportResultComponent("unknown").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")
        self.assertEqual(result.error_code, "person_import_result_unknown")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_import_result_component -v
```

Expected: FAIL because `unknown` currently returns `ok=True`.

- [ ] **Step 3: Implement strict import result classification**

In `tax_rpa/pages/person_info/components/import_result.py`, replace `read_result()` with:

```python
    def read_result(self) -> StepResult:
        if self.config.dry_run:
            return StepResult(ok=True, name="wait_import_result", status="dry_run")
        result = self.wait_for_import_result()
        status = str(result.get("status", "unknown"))
        ok = status == "success"
        if status == "failed":
            error_type = "IMPORT_FAILED"
            error_code = "person_import_failed"
            error = "Personnel import failed"
        elif status == "success":
            error_type = None
            error_code = None
            error = None
        else:
            error_type = "UNKNOWN_RESULT"
            error_code = "person_import_result_unknown"
            error = "Personnel import result was not recognized"
        return StepResult(
            ok=ok,
            name="wait_import_result",
            status=status,
            evidence={"result": result},
            error=error,
            error_type=error_type,
            error_code=error_code,
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )
```

- [ ] **Step 4: Run strict import result tests**

Run:

```powershell
python -m unittest tests.test_import_result_component -v
```

Expected: PASS.

- [ ] **Step 5: Run existing import helper tests**

Run:

```powershell
python -m unittest tests.test_import_person_info_helpers tests.test_component_architecture -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tax_rpa/pages/person_info/components/import_result.py tests/test_import_result_component.py
git commit -m "fix: fail unknown personnel import results"
```

## Task 3: Stop When Page Open Fails

**Files:**
- Modify: `tax_rpa/app/main_shell.py`
- Test: `tests/test_main_shell_open_checks.py`

- [ ] **Step 1: Write failing main shell tests**

Create `tests/test_main_shell_open_checks.py`:

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.app.main_shell import MainShell
from tax_rpa.runtime.result import StepResult


class FakePage:
    def __init__(self, _context, _hwnd, result):
        self.result = result

    def open(self):
        return self.result


class MainShellOpenChecksTests(unittest.TestCase):
    def test_person_info_open_failure_raises(self):
        shell = MainShell(SimpleNamespace(hwnd=100))

        with patch(
            "tax_rpa.app.main_shell.PersonInfoPage",
            lambda context, hwnd: FakePage(
                context,
                hwnd,
                StepResult(
                    ok=False,
                    name="person_info_page.open",
                    status="timeout",
                    error="Timed out waiting for page",
                ),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Timed out waiting for page"):
                shell.open_person_info_page()

    def test_comprehensive_income_open_success_returns_page(self):
        shell = MainShell(SimpleNamespace(hwnd=100))

        with patch(
            "tax_rpa.app.main_shell.ComprehensiveIncomePage",
            lambda context, hwnd: FakePage(
                context,
                hwnd,
                StepResult(ok=True, name="comprehensive_income_page.open", status="navigated"),
            ),
        ):
            page = shell.open_comprehensive_income_page()

        self.assertIsInstance(page, FakePage)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_main_shell_open_checks -v
```

Expected: FAIL because `MainShell` currently ignores failed `page.open()`.

- [ ] **Step 3: Implement checked page opening**

Replace `tax_rpa/app/main_shell.py` with:

```python
from typing import Any

from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.pages.special_deduction.page import SpecialDeductionPage
from tax_rpa.runtime.context import RpaContext


class MainShell:
    def __init__(self, context: RpaContext) -> None:
        self.context = context

    def open_person_info_page(self) -> PersonInfoPage:
        return self._open_checked(
            PersonInfoPage,
            "person_info_page.open",
        )

    def open_special_deduction_page(self) -> SpecialDeductionPage:
        return self._open_checked(
            SpecialDeductionPage,
            "special_deduction_page.open",
        )

    def open_comprehensive_income_page(self) -> ComprehensiveIncomePage:
        return self._open_checked(
            ComprehensiveIncomePage,
            "comprehensive_income_page.open",
        )

    def _open_checked(self, page_class: type[Any], action_name: str) -> Any:
        if self.context.hwnd is None:
            raise RuntimeError("Main window is not available")
        page = page_class(self.context, self.context.hwnd)
        result = page.open()
        if not result.ok:
            message = result.error or f"{action_name} failed with status: {result.status}"
            raise RuntimeError(message)
        return page
```

- [ ] **Step 4: Run page open tests**

Run:

```powershell
python -m unittest tests.test_main_shell_open_checks -v
```

Expected: PASS.

- [ ] **Step 5: Run workflow tests that use shell opening**

Run:

```powershell
python -m unittest tests.test_component_architecture tests.test_workflow_composition tests.test_page_step_architecture -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tax_rpa/app/main_shell.py tests/test_main_shell_open_checks.py
git commit -m "fix: stop workflow when page open fails"
```

## Task 4: Wait For Salary Import Result

**Files:**
- Create: `tax_rpa/pages/comprehensive_income/elements/import_result.py`
- Create: `tax_rpa/pages/comprehensive_income/components/import_result.py`
- Modify: `tax_rpa/pages/comprehensive_income/page.py`
- Modify: `tax_rpa/pages/comprehensive_income/steps/import_salary_income_data.py`
- Test: `tests/test_comprehensive_income_steps.py`
- Test: `tests/test_salary_income_import_result.py`

- [ ] **Step 1: Add failing salary step tests**

Append these tests to `tests/test_comprehensive_income_steps.py`:

```python
    def test_import_salary_income_data_waits_for_import_result_after_file_submit(self):
        class Page(FakeComprehensiveIncomePage):
            def __init__(self):
                super().__init__(dry_run=False, file_dialog_opened=True)
                self.events = []

            def read_salary_income_import_result(self):
                self.events.append("read_result")
                return StepResult(
                    ok=True,
                    name="salary_income.wait_import_result",
                    status="success",
                )

        page = Page()

        result = ImportSalaryIncomeDataStep(page).run(Path("salary.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")
        self.assertEqual(page.events, ["read_result"])
        self.assertIn("import_result", result.evidence)

    def test_import_salary_income_data_stops_when_import_result_unknown(self):
        class Page(FakeComprehensiveIncomePage):
            def __init__(self):
                super().__init__(dry_run=False, file_dialog_opened=True)

            def read_salary_income_import_result(self):
                return StepResult(
                    ok=False,
                    name="salary_income.wait_import_result",
                    status="unknown",
                    error="Salary income import result was not recognized",
                    error_type="UNKNOWN_RESULT",
                    error_code="salary_income_import_result_unknown",
                )

        result = ImportSalaryIncomeDataStep(Page()).run(Path("salary.xlsx"))

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_comprehensive_income_steps -v
```

Expected: FAIL because `ImportSalaryIncomeDataStep` does not call `read_salary_income_import_result()`.

- [ ] **Step 3: Add salary import result classifier**

Create `tax_rpa/pages/comprehensive_income/elements/import_result.py`:

```python
RESULT_TEXTS = {
    "success": (
        "导入成功",
        "导入完成",
        "成功导入",
    ),
    "failed": (
        "导入失败",
        "异常",
        "错误",
        "失败",
    ),
}


def classify_salary_income_import_result(texts: list[str]) -> str:
    joined = "\n".join(texts)
    if any(keyword in joined for keyword in RESULT_TEXTS["failed"]):
        return "failed"
    if any(keyword in joined for keyword in RESULT_TEXTS["success"]):
        return "success"
    return "unknown"
```

- [ ] **Step 4: Add salary import result component tests**

Create `tests/test_salary_income_import_result.py`:

```python
import unittest
from types import SimpleNamespace

from tax_rpa.pages.comprehensive_income.components.import_result import (
    SalaryIncomeImportResultComponent,
)
from tax_rpa.pages.comprehensive_income.elements.import_result import (
    classify_salary_income_import_result,
)


class FakeLogger:
    def screenshot(self, *_args, **_kwargs):
        return "screenshot.png"

    def log(self, *_args, **_kwargs):
        pass


class FixedSalaryImportResultComponent(SalaryIncomeImportResultComponent):
    def __init__(self, status):
        super().__init__(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(dry_run=False, result_timeout_seconds=1),
            allowed_pids={1},
        )
        self.fixed_status = status

    def wait_for_import_result(self):
        return {"status": self.fixed_status, "source": "test"}


class SalaryIncomeImportResultTests(unittest.TestCase):
    def test_classify_success(self):
        self.assertEqual(
            classify_salary_income_import_result(["工资薪金导入成功"]),
            "success",
        )

    def test_classify_failed(self):
        self.assertEqual(
            classify_salary_income_import_result(["导入失败", "金额格式错误"]),
            "failed",
        )

    def test_classify_unknown(self):
        self.assertEqual(
            classify_salary_income_import_result(["请选择导入文件"]),
            "unknown",
        )

    def test_unknown_result_is_not_ok(self):
        result = FixedSalaryImportResultComponent("unknown").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Add salary import result component**

Create `tax_rpa/pages/comprehensive_income/components/import_result.py`:

```python
import time
from typing import Any

from tax_rpa.drivers.ocr_driver import ocr_rect
from tax_rpa.drivers.win32_driver import Win32Driver
from tax_rpa.pages.comprehensive_income.elements.import_result import (
    classify_salary_income_import_result,
)
from tax_rpa.runtime.result import StepResult


class SalaryIncomeImportResultComponent:
    def __init__(
        self,
        hwnd: int,
        logger: Any,
        config: Any,
        allowed_pids: set[int],
        win32: Win32Driver | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.logger = logger
        self.config = config
        self.allowed_pids = allowed_pids
        self.win32 = win32 or Win32Driver()

    def read_result(self) -> StepResult:
        if self.config.dry_run:
            return StepResult(
                ok=True,
                name="salary_income.wait_import_result",
                status="dry_run",
            )
        result = self.wait_for_import_result()
        status = str(result.get("status", "unknown"))
        ok = status == "success"
        if status == "failed":
            error_type = "IMPORT_FAILED"
            error_code = "salary_income_import_failed"
            error = "Salary income import failed"
        elif status == "success":
            error_type = None
            error_code = None
            error = None
        else:
            error_type = "UNKNOWN_RESULT"
            error_code = "salary_income_import_result_unknown"
            error = "Salary income import result was not recognized"
        return StepResult(
            ok=ok,
            name="salary_income.wait_import_result",
            status=status,
            evidence={"result": result},
            error=error,
            error_type=error_type,
            error_code=error_code,
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

    def collect_result_dialogs(self) -> list[dict[str, Any]]:
        dialogs = []
        for window in self.win32.collect_top_windows():
            if window["pid"] not in self.allowed_pids:
                continue
            if window["class"] == "#32770" and window["area"] > 1000:
                texts = self.win32.collect_window_texts(window["hwnd"])
                dialogs.append(
                    {
                        **window,
                        "texts": texts,
                        "result": classify_salary_income_import_result(texts),
                    }
                )
        return dialogs

    def wait_for_import_result(self) -> dict[str, Any]:
        deadline = time.time() + self.config.result_timeout_seconds
        last_dialogs: list[dict[str, Any]] = []

        while time.time() < deadline:
            dialogs = self.collect_result_dialogs()
            last_dialogs = dialogs
            for dialog in dialogs:
                if dialog["result"] in {"success", "failed"}:
                    self.logger.screenshot(f"salary_result_dialog_{dialog['result']}", dialog["rect"])
                    return {
                        "status": dialog["result"],
                        "source": "dialog",
                        "dialog": dialog,
                    }

            rect = self.win32.get_rect(self.hwnd)
            rows, _image_size, image_path = ocr_rect(rect, "after_salary_import_scan", self.logger)
            texts = [str(row.get("text", "")) for row in rows]
            result = classify_salary_income_import_result(texts)
            self.logger.log("scan_salary_import_result", result, texts=texts, screenshot=image_path)
            if result in {"success", "failed"}:
                return {"status": result, "source": "main_ocr", "texts": texts}
            time.sleep(2.0)

        return {"status": "unknown", "source": "timeout", "dialogs": last_dialogs}
```

- [ ] **Step 6: Add page method for reading salary result**

In `tax_rpa/pages/comprehensive_income/page.py`:

1. Add this import:

```python
from tax_rpa.pages.comprehensive_income.components.import_result import (
    SalaryIncomeImportResultComponent,
)
```

2. Add `salary_import_result_reader` to `__init__` parameters after `message_dialog`:

```python
        salary_import_result_reader: Any | None = None,
```

3. Store it in `__init__`:

```python
        self.salary_import_result_reader = salary_import_result_reader
```

4. Add this method to `ComprehensiveIncomePage`:

```python
    def read_salary_income_import_result(self) -> StepResult:
        if self.salary_import_result_reader is not None:
            return self.salary_import_result_reader()
        if self.context is None or self.context.main_window is None:
            raise RuntimeError("Salary income import result requires RpaContext with main_window")
        return SalaryIncomeImportResultComponent(
            self.hwnd,
            self.context.logger,
            self.context.config,
            {int(self.context.main_window["pid"])},
            win32=self.win32,
        ).read_result()
```

- [ ] **Step 7: Update salary import step to wait for result**

In `tax_rpa/pages/comprehensive_income/steps/import_salary_income_data.py`, replace the final return block with:

```python
        if not file_result.ok:
            return StepResult(
                ok=False,
                name="comprehensive_income.import_salary_income_data",
                status=file_result.status,
                evidence={
                    "import_button": import_button_result,
                    "import_option": import_option_result,
                    "file_dialog": file_result,
                },
                error=file_result.error,
                error_type=file_result.error_type,
                error_code=file_result.error_code,
                side_effect_started=True,
                side_effect_committed=True,
                retry_allowed=False,
            )

        with self.page.step("等待工资薪金导入结果"):
            import_result = self.page.read_salary_income_import_result()

        return StepResult(
            ok=import_result.ok,
            name="comprehensive_income.import_salary_income_data",
            status=import_result.status,
            evidence={
                "import_button": import_button_result,
                "import_option": import_option_result,
                "file_dialog": file_result,
                "import_result": import_result,
            },
            error=import_result.error,
            error_type=import_result.error_type,
            error_code=import_result.error_code,
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )
```

- [ ] **Step 8: Run salary import tests**

Run:

```powershell
python -m unittest tests.test_comprehensive_income_steps tests.test_salary_income_import_result -v
```

Expected: PASS.

- [ ] **Step 9: Run related workflow tests**

Run:

```powershell
python -m unittest tests.test_new_workflow_cli tests.test_combined_cli -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add tax_rpa/pages/comprehensive_income tests/test_comprehensive_income_steps.py tests/test_salary_income_import_result.py
git commit -m "feat: wait for salary income import result"
```

## Task 5: Prevent Automatic Retry After Side Effects

**Files:**
- Modify: `tax_rpa/workflows/recovery_policy.py`
- Modify: `tax_rpa/workflows/combined_tax_workflow.py`
- Modify: `tests/test_workflow_composition.py`

- [ ] **Step 1: Add failing recovery policy tests**

Append these tests to `tests/test_workflow_composition.py`:

```python
    def test_combined_workflow_retries_recoverable_failure_only_when_retry_allowed(self):
        events = []
        attempts = {"workflow": 0}

        class RetryAllowedWorkflow:
            def run_on_app(self, app):
                attempts["workflow"] += 1
                events.append(f"business:attempt:{attempts['workflow']}")
                if attempts["workflow"] == 1:
                    return WorkflowResult(
                        ok=False,
                        name="safe_navigation",
                        status="timeout",
                        error="Timed out waiting for page: safe page",
                        retry_allowed=True,
                    )
                return WorkflowResult(ok=True, name="safe_navigation", status="done")

        workflow = CombinedTaxWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            workflow_factories=[lambda config, logger: RetryAllowedWorkflow()],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "business:attempt:1",
                "reset",
                "start",
                "wait_login",
                "business:attempt:2",
            ],
        )

    def test_combined_workflow_does_not_retry_recoverable_failure_after_side_effect(self):
        events = []

        class SideEffectWorkflow:
            def run_on_app(self, app):
                events.append("business:side_effect")
                return WorkflowResult(
                    ok=False,
                    name="salary_income",
                    status="timeout",
                    steps=[
                        StepResult(
                            ok=False,
                            name="submit_file_dialog",
                            status="timeout",
                            side_effect_started=True,
                            side_effect_committed=True,
                        )
                    ],
                    error="Timed out waiting for page after import",
                    retry_allowed=True,
                    side_effect_started=True,
                    side_effect_committed=True,
                )

        workflow = CombinedTaxWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            workflow_factories=[lambda config, logger: SideEffectWorkflow()],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(events, ["start", "wait_login", "business:side_effect"])
```

- [ ] **Step 2: Update existing retry test expectation**

In `tests/test_workflow_composition.py`, update the existing `RecoveringWorkflow` failure to set `retry_allowed=True`:

```python
                    return WorkflowResult(
                        ok=False,
                        name="special_deduction",
                        status="timeout",
                        error="Timed out waiting for page: 涓撻」闄勫姞鎵ｉ櫎淇℃伅閲囬泦",
                        retry_allowed=True,
                    )
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
python -m unittest tests.test_workflow_composition -v
```

Expected: FAIL because `CombinedTaxWorkflow` currently retries based only on status/error markers.

- [ ] **Step 4: Implement retry safety helper**

Replace `tax_rpa/workflows/recovery_policy.py` with:

```python
from tax_rpa.runtime.result import WorkflowResult


RECOVERABLE_STATUSES = {
    "timeout",
    "missing_app_path",
    "main_window_missing",
    "main_window_lost",
    "process_not_found",
}

RECOVERABLE_ERROR_MARKERS = (
    "Timed out waiting for page",
    "Timed out waiting for main window",
    "Main window is not available",
    "Client process is not running",
    "process is not running",
)


def is_recoverable_environment_failure(result: WorkflowResult) -> bool:
    if result.ok:
        return False
    if result.status in RECOVERABLE_STATUSES:
        return True
    error = result.error or ""
    return any(marker in error for marker in RECOVERABLE_ERROR_MARKERS)


def has_business_side_effect(result: WorkflowResult) -> bool:
    if result.side_effect_started or result.side_effect_committed:
        return True
    return any(
        step.side_effect_started or step.side_effect_committed
        for step in result.steps
    )


def can_retry_after_failure(result: WorkflowResult) -> bool:
    if not is_recoverable_environment_failure(result):
        return False
    if has_business_side_effect(result):
        return False
    return bool(result.retry_allowed)
```

- [ ] **Step 5: Update combined workflow to use retry safety**

In `tax_rpa/workflows/combined_tax_workflow.py`:

1. Replace the import:

```python
from tax_rpa.workflows.recovery_policy import can_retry_after_failure
```

2. Replace this condition:

```python
            if not result.ok and is_recoverable_environment_failure(result):
```

with:

```python
            if not result.ok and can_retry_after_failure(result):
```

- [ ] **Step 6: Run workflow composition tests**

Run:

```powershell
python -m unittest tests.test_workflow_composition -v
```

Expected: PASS.

- [ ] **Step 7: Run combined workflow CLI tests**

Run:

```powershell
python -m unittest tests.test_combined_cli tests.test_new_workflow_cli -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add tax_rpa/workflows/recovery_policy.py tax_rpa/workflows/combined_tax_workflow.py tests/test_workflow_composition.py
git commit -m "fix: prevent retry after workflow side effects"
```

## Task 6: Phase 0 Regression Run

**Files:**
- No code changes.

- [ ] **Step 1: Run full unit test suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 2: Run self-check CLI if available**

Run:

```powershell
python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate
```

Expected: command exits with code `0` and writes a summary path under `artifacts/`.

- [ ] **Step 3: Document Phase 0 completion in a short note**

Create `docs/superpowers/plans/2026-05-24-phase-0-completion.md`:

```markdown
# Phase 0 Completion Note

Phase 0 baseline hardening is complete.

Verified:

- Unknown personnel import results fail.
- Page open failures stop the workflow.
- Salary income import waits for explicit result.
- Automatic retry does not cross side-effect boundaries.
- Full unit test suite passes.

Commands:

- `python -m unittest discover -s tests -v`
- `python -m tax_rpa.cli.run_tax_workflow --self-check --no-self-elevate`
```

- [ ] **Step 4: Commit completion note**

```powershell
git add docs/superpowers/plans/2026-05-24-phase-0-completion.md
git commit -m "docs: record phase 0 completion"
```

## Self-Review Checklist

- Phase 0 covers every baseline hardening item from the spec.
- Every unsafe behavior has a failing test before implementation.
- Every side-effect-aware retry behavior uses `retry_allowed` and side-effect metadata.
- No new job-layer modules are implemented in Phase 0.
- No real tax client access is required for automated tests.
