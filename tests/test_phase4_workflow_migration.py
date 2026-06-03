import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tax_rpa.cli.from_zero_import_person_info import SelfCheckApp
from tax_rpa.config.person_import import ImportFileConfig, PersonImportConfig
from tax_rpa.runtime.action_policy import ActionAuditLogger, ActionPolicy
from tax_rpa.jobs.artifact_store import ArtifactStore
from tax_rpa.jobs.manifest import JobManifest, ManifestFile
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions
from tax_rpa.workflows.combined_tax_workflow import CombinedTaxWorkflow
from tax_rpa.workflows.import_person_info_workflow import ImportPersonInfoWorkflow
from tax_rpa.workflows.import_salary_income_workflow import ImportSalaryIncomeWorkflow
from tax_rpa.workflows.update_special_deduction_workflow import (
    UpdateSpecialDeductionWorkflow,
)


class Phase4WorkflowMigrationTests(unittest.TestCase):
    def test_execute_no_send_fake_driver_reaches_salary_import_success_with_job_logs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person_file = root / "person.xlsx"
            salary_file = root / "salary.xlsx"
            person_file.write_bytes(b"person")
            salary_file.write_bytes(b"salary")
            config = PersonImportConfig(
                person_info_file=person_file,
                dry_run=False,
                imports={"salary_income": ImportFileConfig(file=salary_file)},
            )
            artifacts, step_runner, action_policy, runtime_options = self._job_runtime(root)

            result = CombinedTaxWorkflow(
                config=config,
                logger=None,
                workflow_factories=self._workflow_factories(),
                app_factory=lambda config, logger: SelfCheckApp(config, logger),
                step_runner=step_runner,
                action_policy=action_policy,
                runtime_options=runtime_options,
            ).run()

            journal = [
                json.loads(line)
                for line in (artifacts.logs_dir / "step_journal.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            step_events = [
                json.loads(line)
                for line in (artifacts.logs_dir / "steps.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")
        self.assertEqual(
            [item.name for item in result.evidence["business_results"]],
            [
                "import_person_info_workflow",
                "update_special_deduction_workflow",
                "import_salary_income_workflow",
            ],
        )
        self.assertIn("comprehensive_income.import_salary_income_data", [item["step"] for item in journal])
        self.assertIn("side_effect_started", [item["event"] for item in journal])
        self.assertEqual(
            step_events[-1]["result_matrix"]["matrix_step"],
            "salary_income_import",
        )
        self.assertEqual(step_events[-1]["result_matrix"]["outcome"], "success")

    def test_unknown_person_import_result_stops_before_special_deduction(self):
        events = []

        class UnknownPersonImportApp(SelfCheckApp):
            def shell(self):
                return UnknownPersonImportShell(events)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            person_file = root / "person.xlsx"
            salary_file = root / "salary.xlsx"
            person_file.write_bytes(b"person")
            salary_file.write_bytes(b"salary")
            config = PersonImportConfig(
                person_info_file=person_file,
                dry_run=False,
                imports={"salary_income": ImportFileConfig(file=salary_file)},
            )
            artifacts, step_runner, action_policy, runtime_options = self._job_runtime(root)

            result = CombinedTaxWorkflow(
                config=config,
                logger=None,
                workflow_factories=self._workflow_factories(),
                app_factory=lambda config, logger: UnknownPersonImportApp(config, logger),
                step_runner=step_runner,
                action_policy=action_policy,
                runtime_options=runtime_options,
            ).run()

            step_events = [
                json.loads(line)
                for line in (artifacts.logs_dir / "steps.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(events, ["open_person_info_page"])
        self.assertEqual(len(result.evidence["business_results"]), 1)
        self.assertEqual(step_events[-1]["result_matrix"]["matrix_step"], "personnel_import")
        self.assertEqual(step_events[-1]["result_matrix"]["outcome"], "unknown")

    def _job_runtime(self, root: Path):
        artifacts = ArtifactStore(root / "artifacts").for_job("202605-001")
        artifacts.initialize()
        manifest = JobManifest(
            job_id="202605-001",
            idempotency_key="company-tax-period-flow-v1",
            company_name="ExampleCo",
            credit_code="91440300ABCDEF1234",
            tax_period="2026-05",
            person_action="import_file",
            run_mode="execute_no_send",
            submit_enabled=False,
            files={
                "person_info": ManifestFile(path=Path("person.xlsx"), sha256="a" * 64),
                "salary_income": ManifestFile(path=Path("salary.xlsx"), sha256="b" * 64),
            },
        )
        observability = JobObservability(
            artifacts=artifacts,
            context=JobLogContext(
                job_id=manifest.job_id,
                idempotency_key=manifest.idempotency_key,
                run_mode=manifest.run_mode,
                workflow="combined_tax_workflow",
                step="start",
                attempt=1,
                correlation_id="corr-0",
            ),
        )
        action_policy = ActionPolicy(
            run_mode=manifest.run_mode,
            job_id=manifest.job_id,
            audit_logger=ActionAuditLogger(artifacts.logs_dir / "actions.jsonl"),
        )
        runtime_options = WorkflowRuntimeOptions(
            run_mode=manifest.run_mode,
            allow_skip_personal_pension=manifest.allow_skip_personal_pension,
        )
        return artifacts, JobStepRunner(
            manifest=manifest,
            artifacts=artifacts,
            observability=observability,
        ), action_policy, runtime_options

    def _workflow_factories(self):
        return [
            lambda config, logger, step_runner=None, runtime_options=None: ImportPersonInfoWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
            lambda config, logger, step_runner=None, runtime_options=None: UpdateSpecialDeductionWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
            lambda config, logger, step_runner=None, runtime_options=None: ImportSalaryIncomeWorkflow(
                config,
                logger,
                step_runner=step_runner,
                runtime_options=runtime_options,
            ),
        ]


class UnknownPersonImportShell:
    def __init__(self, events):
        self.events = events

    def open_person_info_page(self):
        self.events.append("open_person_info_page")
        return UnknownPersonImportPage()

    def open_special_deduction_page(self):
        self.events.append("open_special_deduction_page")
        return SimpleNamespace()

    def open_comprehensive_income_page(self):
        self.events.append("open_comprehensive_income_page")
        return SimpleNamespace()


class UnknownPersonImportPage:
    def step(self, _name, **_data):
        from contextlib import nullcontext

        return nullcontext()

    def close_message_dialog_if_present(self):
        return StepResult(ok=True, name="message_dialog", status="none")

    def click_import_button(self):
        return StepResult(ok=True, name="click_import_button", status="clicked")

    def choose_import_file_option(self):
        return StepResult(
            ok=True,
            name="choose_import_file_option",
            status="selected",
            evidence={"dialog": {"hwnd": 1}},
        )

    def choose_person_file(self, path, _dropdown_result):
        return StepResult(
            ok=True,
            name="choose_person_file",
            status="submitted",
            evidence={"file_path": str(path)},
        )

    def read_import_result(self):
        return StepResult(
            ok=False,
            name="wait_import_result",
            status="unknown",
            error="Personnel import result was not recognized",
            error_type="UNKNOWN_RESULT",
            error_code="person_import_result_unknown",
            side_effect_started=True,
            side_effect_committed=True,
        )


if __name__ == "__main__":
    unittest.main()
