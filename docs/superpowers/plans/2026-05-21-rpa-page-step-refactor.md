# RPA Page Step Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the personnel information import flow to follow the documented page-step architecture while preserving the existing workflow entry point.

**Architecture:** Use `pages/person_info/` as the first migrated page module. Keep low-level automation in `drivers`, centralize page recognition constants in `elements`, expose semantic page actions through `components` and `steps`, and keep `ImportPersonInfoWorkflow` as a pure business step orchestrator.

**Tech Stack:** Python 3.11, stdlib `unittest`, existing Win32/OCR driver abstractions, existing `StepResult` and `WorkflowResult` runtime models.

---

### Task 1: Add Architecture Boundary Tests

**Files:**
- Modify: `tests/test_component_architecture.py`
- Create: `tests/test_page_step_architecture.py`

- [ ] **Step 1: Write tests for the new person_info package shape**

Add tests that import the new page, elements, component, and step modules:

```python
from tax_rpa.pages.person_info.page import PersonInfoPage
from tax_rpa.pages.person_info.elements.import_menu import IMPORT_BUTTON
from tax_rpa.pages.person_info.components.import_dropdown import ImportDropdownComponent
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
```

- [ ] **Step 2: Write tests proving workflow only composes steps**

Patch the workflow step classes with fakes and assert events equal:

```text
start
wait_login
open_person_page
import_person_file:persons.xlsx
wait_import_result
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_page_step_architecture -v
```

Expected: FAIL because `tax_rpa.pages.person_info` does not exist yet.

### Task 2: Create Person Info Elements

**Files:**
- Create: `tax_rpa/pages/person_info/elements/targets.py`
- Create: `tax_rpa/pages/person_info/elements/page_markers.py`
- Create: `tax_rpa/pages/person_info/elements/import_menu.py`
- Create: `tax_rpa/pages/person_info/elements/import_result.py`

- [ ] **Step 1: Add immutable text target structures**

Create `TextTarget` with `text`, `aliases`, and `screenshot_name`.

- [ ] **Step 2: Move person info page markers into elements**

Define `PERSON_INFO_PAGE_MARKER`, `IMPORT_BUTTON`, and `IMPORT_FILE_OPTIONS`.

- [ ] **Step 3: Keep compatibility with existing constants**

Existing constants in `tax_rpa.constants` may remain, but new page code should import from `pages/person_info/elements`.

### Task 3: Move Page-Owned Component

**Files:**
- Create: `tax_rpa/pages/person_info/components/import_dropdown.py`
- Modify: `tax_rpa/components/import_dropdown.py`

- [ ] **Step 1: Move the implementation to the page-owned component path**

The new component imports `IMPORT_FILE_OPTIONS` from page elements.

- [ ] **Step 2: Leave a compatibility wrapper**

Keep `tax_rpa.components.import_dropdown.ImportDropdownComponent` re-exporting the new class so existing imports do not break during migration.

### Task 4: Split PersonInfoPage and Steps

**Files:**
- Create: `tax_rpa/pages/person_info/page.py`
- Create: `tax_rpa/pages/person_info/steps/open_page.py`
- Create: `tax_rpa/pages/person_info/steps/import_person_file.py`
- Create: `tax_rpa/pages/person_info/steps/wait_import_result.py`
- Modify: `tax_rpa/pages/person_info_page.py`

- [ ] **Step 1: Move page readiness and component factories into `page.py`**

`PersonInfoPage` owns `inspect()`, `is_ready()`, `open()`, and component factory methods.

- [ ] **Step 2: Move import sequence into `ImportPersonFileStep`**

The step performs close-message-dialog, click-import-button, choose-import-option, and choose-file.

- [ ] **Step 3: Move result polling into `WaitImportResultStep`**

The step owns dialog/OCR result polling and returns `StepResult`.

- [ ] **Step 4: Keep legacy page import path working**

`tax_rpa.pages.person_info_page.PersonInfoPage` re-exports the new page class.

### Task 5: Update Workflow and Entrypoints

**Files:**
- Modify: `tax_rpa/app/main_shell.py`
- Modify: `tax_rpa/cli/debug_person_info_page.py`
- Modify: `tax_rpa/workflows/import_person_info_workflow.py`

- [ ] **Step 1: Update imports to the new package path**

Use `tax_rpa.pages.person_info.page.PersonInfoPage`.

- [ ] **Step 2: Make workflow compose step classes**

`ImportPersonInfoWorkflow.run()` should instantiate and run:

```python
OpenPersonInfoPageStep(app.shell())
ImportPersonFileStep(page)
WaitImportResultStep(page)
```

- [ ] **Step 3: Preserve CLI behavior**

Debug CLI still supports `inspect`, `open`, and `import-flow`.

### Task 6: Verify

**Files:**
- No production file edits.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_page_step_architecture tests.test_component_architecture tests.test_driver_boundaries -v
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 3: Verify workflow script imports and reaches dry-run launch decision**

Run:

```powershell
.\.venv\Scripts\python.exe -m tax_rpa.cli.from_zero_import_person_info --config .\config\person_import.example.json --dry-run --no-self-elevate
```

Expected: The module starts successfully. On machines without the tax client running, it may exit with `missing_app_path`; that still confirms the workflow entrypoint loads the refactored framework.
