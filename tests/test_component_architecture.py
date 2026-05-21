import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from tax_rpa.constants import IMPORT_BUTTON_TEXT, IMPORT_OPTION_TEXTS
from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.person_info_page import PersonInfoPage
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
        return FakeShell(self.events)


class FakeShell:
    def __init__(self, events):
        self.events = events

    def open_person_info_page(self):
        self.events.append("open_person_page")
        return FakePersonPage(self.events)


class FakePersonPage:
    def __init__(self, events):
        self.events = events

    def import_person_file(self, path):
        self.events.append(f"import:{path.name}")
        return StepResult(ok=True, name="import_person_file", status="success")


class FakeComponent:
    def __init__(self, events, name):
        self.events = events
        self.name = name

    def close_if_present(self):
        self.events.append(self.name)
        return StepResult(ok=True, name=self.name, status="ok")

    def click_button(self, text):
        self.events.append(f"{self.name}:{text}")
        return StepResult(ok=True, name=self.name, status="ok")

    def choose_item(self, text):
        self.events.append(f"{self.name}:{text}")
        return StepResult(ok=True, name=self.name, status="ok", evidence={"dialog": {"hwnd": 1}})

    def choose_file(self, path):
        self.events.append(f"{self.name}:{path.name}")
        return StepResult(ok=True, name=self.name, status="ok")


class FakeStepLogger:
    def __init__(self, events):
        self.events = events

    @contextmanager
    def step(self, name, **_data):
        self.events.append(f"step_start:{name}")
        try:
            yield
        except Exception:
            self.events.append(f"step_failed:{name}")
            raise
        else:
            self.events.append(f"step_passed:{name}")


class ComponentArchitectureTests(unittest.TestCase):
    def test_workflow_composes_app_shell_and_page(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = ImportPersonInfoWorkflow(
            config=config,
            logger=None,
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            ["start", "wait_login", "open_person_page", "import:persons.xlsx"],
        )

    def test_person_info_page_composes_components_for_import(self):
        events = []
        page = PersonInfoPage(
            context=None,
            hwnd=100,
            toolbar=FakeComponent(events, "toolbar"),
            import_dropdown=FakeComponent(events, "dropdown"),
            file_dialog=FakeComponent(events, "file_dialog"),
            message_dialog=FakeComponent(events, "message_dialog"),
            import_result_reader=lambda: StepResult(
                ok=True,
                name="wait_import_result",
                status="success",
            ),
        )

        result = page.import_person_file(Path("persons.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "message_dialog",
                f"toolbar:{IMPORT_BUTTON_TEXT}",
                f"dropdown:{IMPORT_OPTION_TEXTS[0]}",
                "file_dialog:persons.xlsx",
            ],
        )

    def test_person_info_page_wraps_import_flow_in_named_steps(self):
        events = []
        page = PersonInfoPage(
            context=SimpleNamespace(logger=FakeStepLogger(events)),
            hwnd=100,
            toolbar=FakeComponent(events, "toolbar"),
            import_dropdown=FakeComponent(events, "dropdown"),
            file_dialog=FakeComponent(events, "file_dialog"),
            message_dialog=FakeComponent(events, "message_dialog"),
            import_result_reader=lambda: StepResult(
                ok=True,
                name="wait_import_result",
                status="success",
            ),
        )

        result = page.import_person_file(Path("persons.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "step_start:关闭提示弹窗",
                "message_dialog",
                "step_passed:关闭提示弹窗",
                "step_start:点击导入按钮",
                f"toolbar:{IMPORT_BUTTON_TEXT}",
                "step_passed:点击导入按钮",
                "step_start:选择导入文件菜单",
                f"dropdown:{IMPORT_OPTION_TEXTS[0]}",
                "step_passed:选择导入文件菜单",
                "step_start:选择人员信息文件",
                "file_dialog:persons.xlsx",
                "step_passed:选择人员信息文件",
                "step_start:等待导入结果",
                "step_passed:等待导入结果",
            ],
        )


if __name__ == "__main__":
    unittest.main()
