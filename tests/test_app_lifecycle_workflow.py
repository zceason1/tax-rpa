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

    def test_lifecycle_propagates_login_failure_details(self):
        class LoginFailureApp(FakeLifecycleApp):
            def wait_for_login(self):
                self.events.append("wait_login")
                return StepResult(
                    ok=False,
                    name="wait_login",
                    status="auto_login_failed",
                    evidence={"last_error": "OCR did not find text '申报密码登录'"},
                    error="Auto login failed after 3 attempts",
                    error_type="LOGIN_FAILED",
                    error_code="auto_login_element_not_found",
                )

        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = AppLifecycleWorkflow(
            config=config,
            logger=None,
            reset=False,
            app_factory=lambda config, logger: LoginFailureApp(events),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "auto_login_failed")
        self.assertEqual(result.error, "Auto login failed after 3 attempts")
        self.assertEqual(result.error_type, "LOGIN_FAILED")
        self.assertEqual(result.error_code, "auto_login_element_not_found")
        self.assertEqual(
            result.evidence["last_error"],
            "OCR did not find text '申报密码登录'",
        )


if __name__ == "__main__":
    unittest.main()
