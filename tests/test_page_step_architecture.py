import importlib
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow


class FakeApp:
    def __init__(self, events):
        self.events = events

    def start_if_needed(self):
        self.events.append("start")
        return StepResult(ok=True, name="start", status="ok")

    def wait_for_login(self):
        self.events.append("wait_login")
        return StepResult(ok=True, name="wait_login", status="ok")

    def shell(self):
        return SimpleNamespace(name="shell")


class FakeOpenPersonInfoPageStep:
    def __init__(self, shell):
        self.shell = shell

    def run(self):
        self.shell.name = "open_person_page"
        return SimpleNamespace(name="person_page")


class FakeImportPersonFileStep:
    def __init__(self, page):
        self.page = page

    def run(self, path):
        return StepResult(
            ok=True,
            name="person_info.import_person_file",
            status=f"import_person_file:{path.name}",
        )


class FakeWaitImportResultStep:
    def __init__(self, page):
        self.page = page

    def run(self):
        return StepResult(ok=True, name="person_info.wait_import_result", status="wait_import_result")


class PageStepArchitectureTests(unittest.TestCase):
    def test_person_info_modules_exist_at_page_step_paths(self):
        modules = [
            "tax_rpa.pages.person_info.page",
            "tax_rpa.pages.person_info.elements.page_markers",
            "tax_rpa.pages.person_info.elements.import_menu",
            "tax_rpa.pages.person_info.elements.import_result",
            "tax_rpa.pages.person_info.components.import_dropdown",
            "tax_rpa.pages.person_info.components.import_result",
            "tax_rpa.pages.person_info.steps.open_page",
            "tax_rpa.pages.person_info.steps.import_person_file",
            "tax_rpa.pages.person_info.steps.wait_import_result",
        ]

        for module_name in modules:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    def test_person_info_elements_centralize_page_and_import_targets(self):
        page_markers = importlib.import_module("tax_rpa.pages.person_info.elements.page_markers")
        import_menu = importlib.import_module("tax_rpa.pages.person_info.elements.import_menu")
        import_result = importlib.import_module("tax_rpa.pages.person_info.elements.import_result")

        self.assertEqual(page_markers.PERSON_INFO_PAGE_MARKER.text, "人员信息采集")
        self.assertEqual(import_menu.IMPORT_BUTTON.text, "导入")
        self.assertIn("导入文件", [target.text for target in import_menu.IMPORT_FILE_OPTIONS])
        self.assertIn("success", import_result.RESULT_TEXTS)
        self.assertIn("failed", import_result.RESULT_TEXTS)

    def test_workflow_composes_page_steps_in_business_order(self):
        events = []

        class RecordingOpenStep(FakeOpenPersonInfoPageStep):
            def run(self):
                events.append("open_person_page")
                return super().run()

        class RecordingImportStep(FakeImportPersonFileStep):
            def run(self, path):
                result = super().run(path)
                events.append(result.status)
                return result

        class RecordingWaitStep(FakeWaitImportResultStep):
            def run(self):
                result = super().run()
                events.append(result.status)
                return result

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = ImportPersonInfoWorkflow(
            config=config,
            logger=None,
            app_factory=lambda config, logger: FakeApp(events),
        )

        with (
            patch("tax_rpa.workflows.import_person_info_workflow.OpenPersonInfoPageStep", RecordingOpenStep),
            patch("tax_rpa.workflows.import_person_info_workflow.ImportPersonFileStep", RecordingImportStep),
            patch("tax_rpa.workflows.import_person_info_workflow.WaitImportResultStep", RecordingWaitStep),
        ):
            result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "open_person_page",
                "import_person_file:persons.xlsx",
                "wait_import_result",
            ],
        )

    def test_legacy_person_info_page_import_reexports_new_page_class(self):
        legacy = importlib.import_module("tax_rpa.pages.person_info_page")
        new = importlib.import_module("tax_rpa.pages.person_info.page")

        self.assertIs(legacy.PersonInfoPage, new.PersonInfoPage)

    def test_page_steps_do_not_import_driver_or_element_modules_directly(self):
        step_files = [
            Path("tax_rpa/pages/person_info/steps/open_page.py"),
            Path("tax_rpa/pages/person_info/steps/import_person_file.py"),
            Path("tax_rpa/pages/person_info/steps/wait_import_result.py"),
        ]
        forbidden_prefixes = (
            "tax_rpa.drivers",
            "tax_rpa.pages.person_info.elements",
        )

        violations = []
        for path in step_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                else:
                    continue
                for module in modules:
                    if module.startswith(forbidden_prefixes):
                        violations.append(f"{path}:{module}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
