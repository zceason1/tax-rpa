import tempfile
import unittest
from pathlib import Path

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.jobs.artifact_store import JobArtifacts
from tax_rpa.jobs.manifest import JobManifest, ManifestFile
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
from tax_rpa.runtime.result import StepResult, WorkflowResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.base import BusinessWorkflow
from tax_rpa.workflows.context import WorkflowContext
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.prefill_deduction_workflow import PrefillDeductionWorkflow


class RecordingStepRunner:
    def __init__(self) -> None:
        self.calls = []

    def run_step(
        self,
        *,
        workflow,
        step,
        operation,
        matrix_step=None,
        side_effect_step=False,
    ):
        self.calls.append(
            {
                "workflow": workflow,
                "step": step,
                "matrix_step": matrix_step,
                "side_effect_step": side_effect_step,
            }
        )
        return operation()


class FakeLifecycleApp:
    def __init__(self, events, *, fail_login=False) -> None:
        self.events = events
        self.fail_login = fail_login

    def reset(self):
        self.events.append("reset")
        return StepResult(ok=True, name="reset", status="reset_done")

    def start_if_needed(self):
        self.events.append("start")
        return StepResult(ok=True, name="start", status="started")

    def wait_for_login(self):
        self.events.append("wait_login")
        if self.fail_login:
            return StepResult(
                ok=False,
                name="wait_login",
                status="auto_login_failed",
                evidence={"last_error": "login marker missing"},
                error="Auto login failed",
                error_type="LOGIN_FAILED",
                error_code="auto_login_element_not_found",
                side_effect_started=True,
                side_effect_committed=False,
                retry_allowed=True,
            )
        return StepResult(
            ok=True,
            name="wait_login",
            status="main_window_found",
            evidence={"window": "main"},
        )


class SampleBusinessWorkflow(BusinessWorkflow):
    name = "sample_workflow"

    def __init__(self, config, logger, app_factory=None, runtime_options=None, step_runner=None):
        self._init_workflow(
            config=config,
            logger=logger,
            app_factory=app_factory,
            runtime_options=runtime_options,
            step_runner=step_runner,
        )

    def execute(self, app):
        step = StepResult(
            ok=True,
            name="sample.step",
            status="done",
            evidence={"value": 1},
        )
        return WorkflowResult(
            ok=True,
            name=self.name,
            status="done",
            steps=[step],
            evidence={"sample": step.evidence},
        )


class WorkflowContextTests(unittest.TestCase):
    def test_step_uses_step_runner_with_context(self):
        runner = RecordingStepRunner()
        ctx = self._context(step_runner=runner)

        result = ctx.step(
            "sample.step",
            lambda: StepResult(ok=True, name="sample.step", status="done"),
            matrix_step="sample_matrix",
            side_effect_step=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            runner.calls,
            [
                {
                    "workflow": "sample_workflow",
                    "step": "sample.step",
                    "matrix_step": "sample_matrix",
                    "side_effect_step": True,
                }
            ],
        )

    def test_step_rejects_non_step_result_without_runner(self):
        ctx = self._context()

        with self.assertRaisesRegex(TypeError, "must return StepResult"):
            ctx.step("open.page", lambda: object())

    def test_step_rejects_non_step_result_before_fake_runner_consumes_it(self):
        ctx = self._context(step_runner=RecordingStepRunner())

        with self.assertRaisesRegex(TypeError, "must return StepResult"):
            ctx.step("open.page", lambda: object())

    def test_step_rejects_non_step_result_before_job_runner_consumes_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = JobStepRunner(
                manifest=self._manifest(root),
                artifacts=JobArtifacts(root),
                observability=JobObservability(
                    artifacts=JobArtifacts(root),
                    context=JobLogContext(
                        job_id="job-1",
                        idempotency_key="job-1-key",
                        run_mode="execute_no_send",
                        workflow="sample_workflow",
                        step="start",
                        attempt=1,
                        correlation_id="corr-1",
                    ),
                ),
            )
            ctx = self._context(step_runner=runner)

            with self.assertRaisesRegex(TypeError, "must return StepResult"):
                ctx.step("open.page", lambda: object())

    def test_result_from_step_requires_explicit_evidence_and_preserves_fields(self):
        ctx = self._context()
        step = StepResult(
            ok=False,
            name="submit",
            status="failed",
            evidence={"button": "submit"},
            error="Submit failed",
            error_type="UI_ACTION_FAILED",
            error_code="submit_failed",
            side_effect_started=False,
            side_effect_committed=False,
            retry_allowed=True,
            evidence_paths=["internal-path"],
            ui_text=["internal text"],
        )

        result = ctx.result_from_step(
            step,
            steps=[step],
            evidence={"submit_result": step.evidence},
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.name, "sample_workflow")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.evidence, {"submit_result": {"button": "submit"}})
        self.assertEqual(result.error_type, "UI_ACTION_FAILED")
        self.assertEqual(result.error_code, "submit_failed")
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)
        self.assertFalse(hasattr(result, "evidence_paths"))
        self.assertFalse(hasattr(result, "ui_text"))

    def test_failed_from_step_accepts_explicit_side_effect_overrides(self):
        ctx = self._context()
        submit = StepResult(
            ok=False,
            name="submit",
            status="failed",
            retry_allowed=True,
        )

        result = ctx.failed_from_step(
            submit,
            steps=[submit],
            evidence={"submit": {}},
            side_effect_started=True,
            side_effect_committed=True,
            retry_allowed=False,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def _context(self, *, step_runner=None):
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        return WorkflowContext(
            workflow="sample_workflow",
            config=config,
            logger=None,
            runtime_options=WorkflowRuntimeOptions.from_config(config),
            step_runner=step_runner,
        )

    def _manifest(self, root: Path) -> JobManifest:
        person_file = root / "person.xlsx"
        salary_file = root / "salary.xlsx"
        person_file.write_bytes(b"person")
        salary_file.write_bytes(b"salary")
        return JobManifest(
            job_id="job-1",
            idempotency_key="job-1-key",
            company_name="ExampleCo",
            credit_code="91440300ABCDEF1234",
            tax_period="2026-05",
            person_action="import_file",
            run_mode="execute_no_send",
            submit_enabled=False,
            files={
                "person_info": ManifestFile(path=person_file, sha256="a" * 64),
                "salary_income": ManifestFile(path=salary_file, sha256="b" * 64),
            },
        )


class BusinessWorkflowTests(unittest.TestCase):
    def test_run_starts_lifecycle_once_and_merges_business_steps(self):
        events = []
        workflow = SampleBusinessWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            app_factory=lambda config, logger: FakeLifecycleApp(events),
        )

        result = workflow.run()

        self.assertTrue(result.ok)
        self.assertEqual(events, ["start", "wait_login"])
        self.assertEqual(
            [step.status for step in result.steps],
            ["started", "main_window_found", "done"],
        )
        self.assertEqual(result.evidence, {"sample": {"value": 1}})

    def test_run_lifecycle_failure_preserves_full_metadata_and_evidence(self):
        events = []
        workflow = SampleBusinessWorkflow(
            config=PersonImportConfig(person_info_file=Path("persons.xlsx")),
            logger=None,
            app_factory=lambda config, logger: FakeLifecycleApp(events, fail_login=True),
        )

        result = workflow.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.name, "sample_workflow")
        self.assertEqual(result.status, "auto_login_failed")
        self.assertEqual(result.error, "Auto login failed")
        self.assertEqual(result.error_type, "LOGIN_FAILED")
        self.assertEqual(result.error_code, "auto_login_element_not_found")
        self.assertEqual(result.evidence, {"last_error": "login marker missing"})
        self.assertTrue(result.side_effect_started)
        self.assertFalse(result.side_effect_committed)
        self.assertTrue(result.retry_allowed)

    def test_existing_workflow_constructor_positional_abi_is_unchanged(self):
        config = PersonImportConfig(person_info_file=Path("persons.xlsx"))
        app_factory = object()
        runtime_options = WorkflowRuntimeOptions(run_mode="inspect_only")
        step_runner = object()

        early = ImportPersonInfoWorkflow(
            config,
            None,
            app_factory,
            runtime_options,
            step_runner,
            True,
        )
        phase5 = PrefillDeductionWorkflow(
            config,
            None,
            runtime_options,
            step_runner,
            app_factory,
        )

        self.assertIs(early.app_factory, app_factory)
        self.assertIs(early.runtime_options, runtime_options)
        self.assertIs(early.step_runner, step_runner)
        self.assertTrue(early.reset)
        self.assertIs(phase5.runtime_options, runtime_options)
        self.assertIs(phase5.step_runner, step_runner)
        self.assertIs(phase5.app_factory, app_factory)


if __name__ == "__main__":
    unittest.main()
