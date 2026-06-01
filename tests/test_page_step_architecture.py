import importlib
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import UpdateSpecialDeductionWorkflow


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


class FakeSubmitImportDataStep:
    def __init__(self, page):
        self.page = page

    def run(self):
        return StepResult(
            ok=True,
            name="person_info.submit_import_data",
            status="submit_import_data",
            side_effect_started=True,
            side_effect_committed=True,
        )


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
            "tax_rpa.pages.person_info.steps.submit_import_data",
        ]

        for module_name in modules:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    def test_new_business_page_modules_exist_at_page_step_paths(self):
        modules = [
            "tax_rpa.pages.special_deduction.page",
            "tax_rpa.pages.special_deduction.elements.page_markers",
            "tax_rpa.pages.special_deduction.elements.download_update",
            "tax_rpa.pages.special_deduction.steps.open_page",
            "tax_rpa.pages.special_deduction.steps.download_update_all_persons",
            "tax_rpa.pages.comprehensive_income.page",
            "tax_rpa.pages.comprehensive_income.elements.page_markers",
            "tax_rpa.pages.comprehensive_income.elements.salary_income",
            "tax_rpa.pages.comprehensive_income.elements.import_menu",
            "tax_rpa.pages.comprehensive_income.steps.open_page",
            "tax_rpa.pages.comprehensive_income.steps.open_salary_income_form",
            "tax_rpa.pages.comprehensive_income.steps.import_salary_income_data",
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

    def test_workflow_submits_validated_person_info_before_final_result(self):
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

        class RecordingWaitStep:
            wait_count = 0

            def __init__(self, page):
                self.page = page

            def run(self):
                RecordingWaitStep.wait_count += 1
                status = "ready_to_submit" if RecordingWaitStep.wait_count == 1 else "success"
                events.append("wait_import_result")
                return StepResult(
                    ok=True,
                    name="person_info.wait_import_result",
                    status=status,
                )

        class RecordingSubmitStep(FakeSubmitImportDataStep):
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
            patch("tax_rpa.workflows.import_person_info_workflow.SubmitImportDataStep", RecordingSubmitStep),
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
                "submit_import_data",
                "wait_import_result",
            ],
        )

    def test_workflow_stops_when_submit_data_does_not_finalize_import(self):
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

        class RecordingWaitStep:
            def __init__(self, page):
                self.page = page

            def run(self):
                events.append("wait_import_result")
                return StepResult(
                    ok=True,
                    name="person_info.wait_import_result",
                    status="ready_to_submit",
                )

        class RecordingSubmitStep(FakeSubmitImportDataStep):
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
            patch("tax_rpa.workflows.import_person_info_workflow.SubmitImportDataStep", RecordingSubmitStep),
        ):
            result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")
        self.assertEqual(result.error_code, "person_import_result_unknown")
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "open_person_page",
                "import_person_file:persons.xlsx",
                "wait_import_result",
                "submit_import_data",
                "wait_import_result",
            ],
        )

    def test_special_deduction_workflow_composes_steps_in_business_order(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = UpdateSpecialDeductionWorkflow(
            config=config,
            logger=None,
            app_factory=lambda config, logger: FakeApp(events),
        )

        class RecordingOpenStep:
            def __init__(self, shell):
                self.shell = shell

            def run(self):
                events.append("open_special_deduction_page")
                return SimpleNamespace(name="special_deduction_page")

        class RecordingDownloadStep:
            def __init__(self, page):
                self.page = page

            def run(self):
                events.append("download_update")
                events.append("all_persons")
                return StepResult(
                    ok=True,
                    name="special_deduction.download_update_all_persons",
                    status="all_persons_clicked",
                )

        with (
            patch(
                "tax_rpa.workflows.update_special_deduction_workflow.OpenSpecialDeductionPageStep",
                RecordingOpenStep,
            ),
            patch(
                "tax_rpa.workflows.update_special_deduction_workflow.DownloadUpdateAllPersonsStep",
                RecordingDownloadStep,
            ),
        ):
            result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "open_special_deduction_page",
                "download_update",
                "all_persons",
            ],
        )

    def test_salary_income_workflow_composes_steps_in_business_order(self):
        import tempfile

        events = []
        with tempfile.TemporaryDirectory() as temp_dir:
            salary_file = Path(temp_dir) / "salary.xlsx"
            salary_file.write_bytes(b"placeholder")
            config = PersonImportConfig(
                person_info_file=Path("persons.xlsx"),
                imports={"salary_income": SimpleNamespace(file=salary_file)},
            )
            workflow = ImportSalaryIncomeWorkflow(
                config=config,
                logger=None,
                app_factory=lambda config, logger: FakeApp(events),
            )

            class RecordingOpenPageStep:
                def __init__(self, shell):
                    self.shell = shell

                def run(self):
                    events.append("open_comprehensive_income_page")
                    return SimpleNamespace(name="comprehensive_income_page")

            class RecordingOpenFormStep:
                def __init__(self, page):
                    self.page = page

                def run(self):
                    events.append("open_salary_income_form")
                    return StepResult(
                        ok=True,
                        name="comprehensive_income.open_salary_income_form",
                        status="opened",
                    )

            class RecordingImportStep:
                def __init__(self, page):
                    self.page = page

                def run(self, path):
                    events.append(f"import_salary_income_data:{path.name}")
                    return StepResult(
                        ok=True,
                        name="comprehensive_income.import_salary_income_data",
                        status="dry_run",
                    )

            with (
                patch(
                    "tax_rpa.workflows.import_salary_income_workflow.OpenComprehensiveIncomePageStep",
                    RecordingOpenPageStep,
                ),
                patch(
                    "tax_rpa.workflows.import_salary_income_workflow.OpenSalaryIncomeFormStep",
                    RecordingOpenFormStep,
                ),
                patch(
                    "tax_rpa.workflows.import_salary_income_workflow.ImportSalaryIncomeDataStep",
                    RecordingImportStep,
                ),
            ):
                result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "open_comprehensive_income_page",
                "open_salary_income_form",
                "import_salary_income_data:salary.xlsx",
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
            Path("tax_rpa/pages/special_deduction/steps/open_page.py"),
            Path("tax_rpa/pages/special_deduction/steps/download_update_all_persons.py"),
            Path("tax_rpa/pages/comprehensive_income/steps/open_page.py"),
            Path("tax_rpa/pages/comprehensive_income/steps/open_salary_income_form.py"),
            Path("tax_rpa/pages/comprehensive_income/steps/import_salary_income_data.py"),
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
