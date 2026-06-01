import unittest

from tax_rpa.runtime.result import StepResult, WorkflowResult


class RuntimeResultMetadataTests(unittest.TestCase):
    def test_step_result_defaults_are_retry_safe_for_existing_callers(self):
        result = StepResult(ok=True, name="step", status="ok")

        self.assertFalse(result.side_effect_started)
        self.assertFalse(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)
        self.assertEqual(result.evidence_paths, [])
        self.assertEqual(result.ui_text, [])

    def test_workflow_result_defaults_are_retry_safe_for_existing_callers(self):
        result = WorkflowResult(ok=False, name="workflow", status="timeout")

        self.assertFalse(result.side_effect_started)
        self.assertFalse(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)


if __name__ == "__main__":
    unittest.main()
