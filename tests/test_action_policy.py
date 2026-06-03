import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.runtime.action_policy import (
    ActionAuditLogger,
    ActionDeniedError,
    ActionPolicy,
)


class ActionPolicyTests(unittest.TestCase):
    def test_inspect_only_denies_file_submit_actions(self):
        policy = ActionPolicy(run_mode="inspect_only")

        decision = policy.before_action(
            label="open file",
            action_type="file_submit",
            context={"step_name": "file_dialog.choose_file"},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error_type, "ACTION_DENIED")
        self.assertEqual(decision.error_code, "run_mode_denied")

    def test_execute_no_send_allows_data_change_but_denies_high_risk_submit(self):
        policy = ActionPolicy(run_mode="execute_no_send")

        import_decision = policy.before_action(
            label="导入",
            action_type="data_change",
            context={"step_name": "person_info.import"},
        )
        submit_decision = policy.before_action(
            label="发送申报",
            action_type="data_change",
            context={"step_name": "declaration.submit"},
        )

        self.assertTrue(import_decision.allowed)
        self.assertFalse(submit_decision.allowed)
        self.assertEqual(submit_decision.error_type, "SUBMIT_NOT_AUTHORIZED")
        self.assertEqual(submit_decision.error_code, "submit_not_authorized")

    def test_require_allowed_raises_for_denied_actions(self):
        policy = ActionPolicy(run_mode="inspect_only")

        with self.assertRaises(ActionDeniedError) as cm:
            policy.require_allowed(
                label="导入",
                action_type="data_change",
                context={"step_name": "toolbar.click_button"},
            )

        self.assertEqual(cm.exception.decision.error_code, "run_mode_denied")

    def test_denied_high_risk_click_writes_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "actions.jsonl"
            policy = ActionPolicy(
                run_mode="execute_no_send",
                job_id="202605-001",
                audit_logger=ActionAuditLogger(audit_path),
            )

            decision = policy.before_action(
                label="发送申报",
                action_type="data_change",
                context={"step_name": "declaration.submit"},
            )

            events = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertFalse(decision.allowed)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["job_id"], "202605-001")
        self.assertEqual(events[0]["label"], "发送申报")
        self.assertEqual(events[0]["decision"], "denied")
        self.assertEqual(events[0]["error_type"], "SUBMIT_NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
