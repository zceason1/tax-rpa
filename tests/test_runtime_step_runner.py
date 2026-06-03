import unittest
from types import SimpleNamespace

from tax_rpa.runtime.result import StepResult
from tax_rpa.runtime.step_runner import DirectStepRunner
from tax_rpa.runtime.workflow_options import WorkflowRuntimeOptions


class DirectStepRunnerTests(unittest.TestCase):
    def test_run_step_executes_operation_without_job_dependencies(self):
        calls = []
        runner = DirectStepRunner()

        result = runner.run_step(
            workflow="sample_workflow",
            step="sample.step",
            operation=lambda: calls.append("ran")
            or StepResult(ok=True, name="sample.step", status="ok"),
            matrix_step="sample_matrix",
            side_effect_step=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ok")
        self.assertEqual(calls, ["ran"])

    def test_workflow_options_default_from_dry_run_config(self):
        dry_run_options = WorkflowRuntimeOptions.from_config(SimpleNamespace(dry_run=True))
        execute_options = WorkflowRuntimeOptions.from_config(SimpleNamespace(dry_run=False))

        self.assertEqual(dry_run_options.run_mode, "inspect_only")
        self.assertEqual(execute_options.run_mode, "execute_no_send")
        self.assertFalse(execute_options.allow_skip_personal_pension)

    def test_workflow_options_can_carry_manifest_derived_business_flags(self):
        options = WorkflowRuntimeOptions(
            run_mode="execute_no_send",
            allow_skip_personal_pension=True,
        )

        self.assertEqual(options.run_mode, "execute_no_send")
        self.assertTrue(options.allow_skip_personal_pension)


if __name__ == "__main__":
    unittest.main()
