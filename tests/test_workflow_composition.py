import unittest
from pathlib import Path

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow


class FakeApp:
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


class LoginFailureApp(FakeApp):
    def wait_for_login(self):
        self.events.append("wait_login")
        return StepResult(
            ok=False,
            name="wait_login",
            status="auto_login_failed",
            evidence={"last_error": "Cursor did not move to target"},
            error="Auto login failed after 3 attempts",
            error_type="LOGIN_FAILED",
            error_code="auto_login_element_not_found",
        )


class FakeBusinessWorkflow:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def run_on_app(self, app):
        self.events.append(f"business:{self.name}")
        return WorkflowResult(
            ok=True,
            name=self.name,
            status=f"{self.name}_done",
            steps=[
                StepResult(ok=True, name=self.name, status=f"{self.name}_step"),
            ],
        )


class WorkflowCompositionTests(unittest.TestCase):
    def test_combined_workflow_runs_lifecycle_once_then_business_workflows_in_order(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = CombinedTaxWorkflow(
            config=config,
            logger=None,
            reset=True,
            workflow_factories=[
                lambda config, logger: FakeBusinessWorkflow("person_info", events),
                lambda config, logger: FakeBusinessWorkflow("special_deduction", events),
                lambda config, logger: FakeBusinessWorkflow("salary_income", events),
            ],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "reset",
                "start",
                "wait_login",
                "business:person_info",
                "business:special_deduction",
                "business:salary_income",
            ],
        )
        self.assertEqual(result.status, "salary_income_done")
        self.assertEqual([step.status for step in result.steps], ["reset_done", "started", "main_window_found"])
        self.assertEqual(
            [item.status for item in result.evidence["business_results"]],
            ["person_info_done", "special_deduction_done", "salary_income_done"],
        )

    def test_combined_workflow_propagates_lifecycle_failure_details(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = CombinedTaxWorkflow(
            config=config,
            logger=None,
            workflow_factories=[
                lambda config, logger: FakeBusinessWorkflow("person_info", events),
            ],
            app_factory=lambda config, logger: LoginFailureApp(events),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "auto_login_failed")
        self.assertEqual(result.error, "Auto login failed after 3 attempts")
        self.assertEqual(result.error_type, "LOGIN_FAILED")
        self.assertEqual(result.error_code, "auto_login_element_not_found")
        self.assertEqual(
            result.evidence["lifecycle"]["last_error"],
            "Cursor did not move to target",
        )
        self.assertEqual(events, ["start", "wait_login"])

    def test_combined_workflow_does_not_reset_between_successful_business_workflows(self):
        events = []
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = CombinedTaxWorkflow(
            config=config,
            logger=None,
            reset=False,
            workflow_factories=[
                lambda config, logger: FakeBusinessWorkflow("person_info", events),
                lambda config, logger: FakeBusinessWorkflow("special_deduction", events),
            ],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "business:person_info",
                "business:special_deduction",
            ],
        )

    def test_combined_workflow_resets_and_retries_current_workflow_after_environment_failure(self):
        events = []
        attempts = {"special_deduction": 0}

        class RecoveringWorkflow:
            def run_on_app(self, app):
                attempts["special_deduction"] += 1
                events.append(f"business:special_deduction:{attempts['special_deduction']}")
                if attempts["special_deduction"] == 1:
                    return WorkflowResult(
                        ok=False,
                        name="special_deduction",
                        status="timeout",
                        error="Timed out waiting for page: 专项附加扣除信息采集",
                        retry_allowed=True,
                    )
                return WorkflowResult(ok=True, name="special_deduction", status="done")

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = CombinedTaxWorkflow(
            config=config,
            logger=None,
            reset=False,
            workflow_factories=[
                lambda config, logger: RecoveringWorkflow(),
            ],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(
            events,
            [
                "start",
                "wait_login",
                "business:special_deduction:1",
                "reset",
                "start",
                "wait_login",
                "business:special_deduction:2",
            ],
        )

    def test_combined_workflow_does_not_reset_after_non_environment_failure(self):
        events = []

        class FailingWorkflow:
            def run_on_app(self, app):
                events.append("business:salary_income")
                return WorkflowResult(
                    ok=False,
                    name="salary_income",
                    status="file_dialog_missing",
                    error="Import data file dialog was not opened",
                )

        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        workflow = CombinedTaxWorkflow(
            config=config,
            logger=None,
            reset=False,
            workflow_factories=[
                lambda config, logger: FailingWorkflow(),
            ],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(events, ["start", "wait_login", "business:salary_income"])

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

    def test_combined_workflow_does_not_retry_recoverable_failure_without_retry_allowed(self):
        events = []

        class RetryDisallowedWorkflow:
            def run_on_app(self, app):
                events.append("business:retry_disallowed")
                return WorkflowResult(
                    ok=False,
                    name="safe_navigation",
                    status="timeout",
                    error="Timed out waiting for page: safe page",
                )

        workflow = CombinedTaxWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            workflow_factories=[lambda config, logger: RetryDisallowedWorkflow()],
            app_factory=lambda config, logger: FakeApp(events),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(events, ["start", "wait_login", "business:retry_disallowed"])

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


if __name__ == "__main__":
    unittest.main()
