import unittest
from pathlib import Path

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult
from tax_rpa.workflows.app_lifecycle_workflow import AppLifecycleWorkflow


class FakeLifecycleApp:
    def __init__(self, events):
        self.events = events

    def reset(self):
        self.events.append("reset")
        return StepResult(ok=True, name="reset", status="reset_done")

    def start_if_needed(self):
        self.events.append("start")
        return StepResult(ok=True, name="start", status="started")

    def wait_for_login(self):
        self.events.append("wait_login")
        return StepResult(ok=True, name="wait_login", status="main_window_found")


class AppLifecycleWorkflowTests(unittest.TestCase):
    def test_without_reset_starts_and_waits_for_login(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = AppLifecycleWorkflow(
            config=config,
            logger=None,
            reset=False,
            app_factory=lambda config, logger: FakeLifecycleApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(events, ["start", "wait_login"])
        self.assertEqual([step.status for step in result.steps], ["started", "main_window_found"])

    def test_with_reset_resets_before_starting_and_waiting_for_login(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = AppLifecycleWorkflow(
            config=config,
            logger=None,
            reset=True,
            app_factory=lambda config, logger: FakeLifecycleApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(events, ["reset", "start", "wait_login"])
        self.assertEqual(
            [step.status for step in result.steps],
            ["reset_done", "started", "main_window_found"],
        )

    def test_lifecycle_result_does_not_embed_app_object_in_json_evidence(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = AppLifecycleWorkflow(
            config=config,
            logger=None,
            reset=False,
            app_factory=lambda config, logger: FakeLifecycleApp(events),
        )

        result = workflow.run()

        self.assertNotIn("app", result.evidence)
        self.assertIsNotNone(workflow.app)


if __name__ == "__main__":
    unittest.main()
