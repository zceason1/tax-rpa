import unittest
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.pages.person_info.elements.import_menu import SUBMIT_DATA_BUTTON
from tax_rpa.pages.person_info.elements.import_menu import IMPORT_BUTTON, IMPORT_FILE_OPTIONS
from tax_rpa.pages.person_info.steps.import_person_file import ImportPersonFileStep
from tax_rpa.pages.person_info.page import PersonInfoPage
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

    def step(self, _name, **_data):
        return nullcontext()

    def close_message_dialog_if_present(self):
        self.events.append("message_dialog")
        return StepResult(ok=True, name="message_dialog", status="ok")

    def click_import_button(self):
        self.events.append(f"toolbar:{IMPORT_BUTTON.text}")
        return StepResult(ok=True, name="toolbar", status="ok")

    def choose_import_file_option(self):
        self.events.append(f"dropdown:{IMPORT_FILE_OPTIONS[0].text}")
        return StepResult(ok=True, name="dropdown", status="ok", evidence={"dialog": {"hwnd": 1}})

    def choose_person_file(self, path, _dropdown_result):
        self.events.append(f"file_dialog:{path.name}")
        return StepResult(ok=True, name="file_dialog", status="ok")

    def read_import_result(self):
        self.events.append("wait_import_result")
        return StepResult(ok=True, name="wait_import_result", status="success")


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


def event_kind(event):
    if event.startswith("step_start:"):
        return "step_start"
    if event.startswith("step_passed:"):
        return "step_passed"
    return event


class ComponentArchitectureTests(unittest.TestCase):
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
            [
                "start",
                "wait_login",
                "open_person_page",
                "message_dialog",
                f"toolbar:{IMPORT_BUTTON.text}",
                f"dropdown:{IMPORT_FILE_OPTIONS[0].text}",
                "file_dialog:persons.xlsx",
                "wait_import_result",
            ],
        )

    def test_import_person_file_step_composes_page_components(self):
        events = []
        page = PersonInfoPage(
            context=None,
            hwnd=100,
            toolbar=FakeComponent(events, "toolbar"),
            import_dropdown=FakeComponent(events, "dropdown"),
            file_dialog=FakeComponent(events, "file_dialog"),
            message_dialog=FakeComponent(events, "message_dialog"),
        )

        result = ImportPersonFileStep(page).run(Path("persons.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "message_dialog",
                f"toolbar:{IMPORT_BUTTON.text}",
                f"dropdown:{IMPORT_FILE_OPTIONS[0].text}",
                "file_dialog:persons.xlsx",
            ],
        )

    def test_import_person_file_step_wraps_page_capabilities_in_named_steps(self):
        events = []
        page = PersonInfoPage(
            context=SimpleNamespace(logger=FakeStepLogger(events)),
            hwnd=100,
            toolbar=FakeComponent(events, "toolbar"),
            import_dropdown=FakeComponent(events, "dropdown"),
            file_dialog=FakeComponent(events, "file_dialog"),
            message_dialog=FakeComponent(events, "message_dialog"),
        )

        result = ImportPersonFileStep(page).run(Path("persons.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(
            [event_kind(event) for event in events],
            [
                "step_start",
                "message_dialog",
                "step_passed",
                "step_start",
                f"toolbar:{IMPORT_BUTTON.text}",
                "step_passed",
                "step_start",
                f"dropdown:{IMPORT_FILE_OPTIONS[0].text}",
                "step_passed",
                "step_start",
                "file_dialog:persons.xlsx",
                "step_passed",
            ],
        )
        self.assertTrue(
            all(
                event.split(":", 1)[1]
                for event in events
                if event.startswith(("step_start:", "step_passed:"))
            )
        )


class SubmitDataStallTests(unittest.TestCase):
    def test_person_import_workflow_stops_when_submit_data_does_not_finalize_import(self):
        events = []
        responses = iter(
            [
                StepResult(ok=True, name="wait_import_result", status="ready_to_submit"),
                StepResult(ok=True, name="wait_import_result", status="ready_to_submit"),
            ]
        )

        class StallShell:
            def open_person_info_page(self):
                events.append("open_person_page")
                return PersonInfoPage(
                    context=None,
                    hwnd=100,
                    toolbar=FakeComponent(events, "toolbar"),
                    import_dropdown=FakeComponent(events, "dropdown"),
                    file_dialog=FakeComponent(events, "file_dialog"),
                    message_dialog=FakeComponent(events, "message_dialog"),
                    import_result_reader=lambda: next(responses),
                )

        class StallApp:
            def start_if_needed(self):
                events.append("start")
                return StepResult(ok=True, name="start", status="ok")

            def wait_for_login(self):
                events.append("wait_login")
                return StepResult(ok=True, name="wait_login", status="ok")

            def shell(self):
                return StallShell()

        workflow = ImportPersonInfoWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            app_factory=lambda config, logger: StallApp(),
        )

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
                "message_dialog",
                f"toolbar:{IMPORT_BUTTON.text}",
                f"dropdown:{IMPORT_FILE_OPTIONS[0].text}",
                "file_dialog:persons.xlsx",
                f"toolbar:{SUBMIT_DATA_BUTTON.text}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
