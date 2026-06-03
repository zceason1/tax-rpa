import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.artifact_store import ArtifactStore
from tax_rpa.jobs.manifest import JobManifest, ManifestFile
from tax_rpa.jobs.observability import JobLogContext, JobObservability
from tax_rpa.jobs.workflow_step_runner import JobStepRunner
from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.result_matrix import classify_step_result


def make_manifest() -> JobManifest:
    return JobManifest(
        job_id="202605-001",
        idempotency_key="company-tax-period-flow-v1",
        company_name="ExampleCo",
        credit_code="91440300ABCDEF1234",
        tax_period="2026-05",
        person_action="import_file",
        run_mode="execute_no_send",
        submit_enabled=False,
        files={
            "person_info": ManifestFile(path=Path("input/person.xlsx"), sha256="a" * 64),
            "salary_income": ManifestFile(path=Path("input/salary.xlsx"), sha256="b" * 64),
        },
    )


class JobStepRunnerTests(unittest.TestCase):
    def test_classifies_import_success_failure_and_unknown(self):
        success = classify_step_result(
            "personnel_import",
            StepResult(ok=True, name="wait_import_result", status="success"),
        )
        failed = classify_step_result(
            "personnel_import",
            StepResult(
                ok=False,
                name="wait_import_result",
                status="failed",
                error_type="IMPORT_FAILED",
                error_code="person_import_failed",
            ),
        )
        unknown = classify_step_result(
            "salary_income_import",
            StepResult(
                ok=False,
                name="salary_income.wait_import_result",
                status="unknown",
                error_type="UNKNOWN_RESULT",
                error_code="salary_income_import_result_unknown",
            ),
        )

        self.assertEqual(success["outcome"], "success")
        self.assertEqual(failed["outcome"], "failure")
        self.assertEqual(failed["error_type"], "IMPORT_FAILED")
        self.assertEqual(unknown["outcome"], "unknown")
        self.assertEqual(unknown["error_type"], "UNKNOWN_RESULT")

    def test_run_step_writes_step_journal_side_effect_markers_and_result_matrix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            manifest = make_manifest()
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
            runner = JobStepRunner(
                manifest=manifest,
                artifacts=artifacts,
                observability=observability,
            )

            result = runner.run_step(
                workflow="import_person_info_workflow",
                step="person_info.import_person_file",
                matrix_step="personnel_import",
                side_effect_step=True,
                operation=lambda: StepResult(
                    ok=True,
                    name="person_info.import_person_file",
                    status="success",
                    side_effect_started=True,
                    side_effect_committed=True,
                ),
            )

            journal = [
                json.loads(line)
                for line in (artifacts.logs_dir / "step_journal.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            steps = [
                json.loads(line)
                for line in (artifacts.logs_dir / "steps.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertTrue(result.ok)
        self.assertEqual(
            [item["event"] for item in journal],
            [
                "step_start",
                "side_effect_started",
                "side_effect_committed",
                "step_result",
            ],
        )
        self.assertTrue(journal[1]["side_effect_expected"])
        self.assertEqual(steps[-1]["result_matrix"]["matrix_step"], "personnel_import")
        self.assertEqual(steps[-1]["result_matrix"]["outcome"], "success")
        self.assertEqual(steps[-1]["status"], "success")


if __name__ == "__main__":
    unittest.main()
