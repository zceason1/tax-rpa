import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.manifest import JobManifest
from tax_rpa.jobs.submit_authorization import SubmitAuthorization
from tax_rpa.runtime.action_policy import ActionAuditLogger, ActionPolicy


def manifest(**overrides) -> JobManifest:
    data = {
        "job_id": "202605-001",
        "idempotency_key": "company-tax-period-flow-v1",
        "company_name": "ExampleCo",
        "credit_code": "91440300ABCDEF1234",
        "tax_period": "2026-05",
        "person_action": "import_file",
        "run_mode": "submit",
        "submit_enabled": True,
        "files": {
            "person_info": {"path": "input/person.xlsx", "sha256": "a" * 64},
            "salary_income": {"path": "input/salary.xlsx", "sha256": "b" * 64},
        },
    }
    data.update(overrides)
    return JobManifest.from_dict(data)


def write_switch(path: Path, enabled: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "enabled": enabled,
                "approved_by": "tax-owner",
                "approved_at": "2026-05-24T14:45:00+08:00",
            }
        ),
        encoding="utf-8",
    )


class SubmitAuthorizationTests(unittest.TestCase):
    def test_missing_production_switch_denies_fail_closed_and_audits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "actions.jsonl"
            result = SubmitAuthorization(
                production_switch_path=Path(temp_dir) / "missing.json",
                cli_submit=True,
                windows_user="runner",
                audit_logger=ActionAuditLogger(audit_path),
            ).authorize(manifest(), step_name="declaration.submit", label="发送申报")
            events = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertFalse(result.allowed)
        self.assertEqual(result.error_type, "SUBMIT_NOT_AUTHORIZED")
        self.assertIn("production_switch", result.missing_gates)
        self.assertEqual(events[0]["decision"], "denied")

    def test_execute_no_send_manifest_denies_even_with_other_gates_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_path = Path(temp_dir) / "production_submit_enabled.json"
            write_switch(switch_path)

            result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=True,
                windows_user="runner",
            ).authorize(
                manifest(run_mode="execute_no_send"),
                step_name="declaration.submit",
                label="发送申报",
            )

        self.assertFalse(result.allowed)
        self.assertIn("manifest.run_mode", result.missing_gates)

    def test_submit_enabled_false_denies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_path = Path(temp_dir) / "production_submit_enabled.json"
            write_switch(switch_path)

            result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=True,
                windows_user="runner",
            ).authorize(
                manifest(submit_enabled=False),
                step_name="declaration.submit",
                label="发送申报",
            )

        self.assertFalse(result.allowed)
        self.assertIn("manifest.submit_enabled", result.missing_gates)

    def test_cli_submit_false_denies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_path = Path(temp_dir) / "production_submit_enabled.json"
            write_switch(switch_path)

            result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=False,
                windows_user="runner",
            ).authorize(manifest(), step_name="declaration.submit", label="发送申报")

        self.assertFalse(result.allowed)
        self.assertIn("cli_submit", result.missing_gates)

    def test_all_gates_pass_issue_one_time_permit_consumed_by_action_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_path = Path(temp_dir) / "production_submit_enabled.json"
            write_switch(switch_path)
            auth_result = SubmitAuthorization(
                production_switch_path=switch_path,
                cli_submit=True,
                windows_user="runner",
            ).authorize(manifest(), step_name="declaration.submit", label="发送申报")
            policy = ActionPolicy(run_mode="submit", job_id="202605-001")

            first = policy.before_action(
                label="发送申报",
                action_type="data_change",
                context={"job_id": "202605-001", "step_name": "declaration.submit"},
                permit=auth_result.permit,
            )
            second = policy.before_action(
                label="发送申报",
                action_type="data_change",
                context={"job_id": "202605-001", "step_name": "declaration.submit"},
                permit=auth_result.permit,
            )

        self.assertTrue(auth_result.allowed)
        self.assertIsNotNone(auth_result.permit)
        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.error_type, "SUBMIT_NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
