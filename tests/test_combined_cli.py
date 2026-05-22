import unittest
from pathlib import Path
from unittest.mock import patch

from tax_rpa.config.person_import import PersonImportConfig
from tax_rpa.runtime.result import WorkflowResult


class CombinedCliTests(unittest.TestCase):
    def test_run_workflow_builds_complete_business_sequence(self):
        from tax_rpa.cli.run_tax_workflow import run_workflow

        captured = {}

        class FakeCombinedWorkflow:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def run(self):
                return WorkflowResult(ok=True, name="combined", status="done")

        with patch("tax_rpa.cli.run_tax_workflow.CombinedTaxWorkflow", FakeCombinedWorkflow):
            summary = run_workflow(
                PersonImportConfig(person_info_file=Path("persons.xlsx")),
                logger=None,
                reset=True,
            )

        self.assertEqual(summary["status"], "done")
        self.assertTrue(captured["reset"])
        self.assertEqual(len(captured["workflow_factories"]), 3)


if __name__ == "__main__":
    unittest.main()
