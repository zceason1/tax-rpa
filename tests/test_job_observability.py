import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.artifact_store import ArtifactStore
from tax_rpa.jobs.observability import JobLogContext, JobObservability


class JobObservabilityTests(unittest.TestCase):
    def test_logs_screenshots_and_troubleshooting_index_are_job_relative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            screenshot_targets = []

            def grabber(path: Path) -> None:
                screenshot_targets.append(path)
                path.write_bytes(b"fake-png")

            context = JobLogContext(
                job_id="202605-001",
                idempotency_key="company-tax-period-flow-v1",
                run_mode="execute_no_send",
                workflow="fake_job",
                step="forced_failure",
                attempt=1,
                correlation_id="corr-1",
            )
            observability = JobObservability(
                artifacts=artifacts,
                context=context,
                screenshot_grabber=grabber,
            )

            observability.log_job_event("job_started", "started")
            observability.write_step_journal("step_start", "started")
            observability.log_action(
                "click_denied",
                "denied",
                label="send declaration",
                source_component="toolbar",
                denial_reason="submit_not_authorized",
            )
            ocr_json_path = observability.write_ocr_json("corr-1", {"rows": []})
            observability.log_ocr(
                "ocr_scan",
                "target_missing",
                target_text="send declaration",
                threshold=0.35,
                candidates=[],
                ocr_json_path=ocr_json_path,
            )
            observability.log_dialog(
                "popup_decision",
                "blocked",
                title="unexpected",
                text=["unexpected popup"],
                chosen_action="stop",
            )
            observability.log_window(
                "window_snapshot",
                "captured",
                active_window={"hwnd": 100, "title": "Tax Client"},
            )
            screenshot_path = observability.capture_full_screen("forced_failure")
            index_path = observability.write_troubleshooting_index(
                summary_path="summary.json",
                primary_failure_screenshot=screenshot_path,
                exported_files=["exported/report.xlsx"],
            )

            self.assertEqual(index_path, "troubleshooting_index.json")
            self.assertEqual(screenshot_targets[0].name, "forced_failure.png")
            self.assertEqual(screenshot_path, "screenshots/forced_failure.png")
            self.assertEqual(ocr_json_path, "ocr/corr-1.json")
            self.assertTrue((artifacts.root / screenshot_path).exists())
            self.assertTrue((artifacts.root / ocr_json_path).exists())

            for log_name in (
                "job_events",
                "step_journal",
                "actions",
                "ocr",
                "dialogs",
                "windows",
            ):
                event = json.loads(
                    (artifacts.logs_dir / f"{log_name}.jsonl").read_text(
                        encoding="utf-8"
                    ).splitlines()[0]
                )
                self.assertEqual(event["job_id"], "202605-001")
                self.assertEqual(event["idempotency_key"], "company-tax-period-flow-v1")
                self.assertEqual(event["run_mode"], "execute_no_send")
                self.assertEqual(event["workflow"], "fake_job")
                self.assertEqual(event["step"], "forced_failure")
                self.assertEqual(event["attempt"], 1)
                self.assertEqual(event["correlation_id"], "corr-1")
                self.assertIn("time", event)

            index = json.loads(
                (artifacts.root / "troubleshooting_index.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(index["summary"], "summary.json")
            self.assertEqual(index["state"], "state.json")
            self.assertEqual(index["primary_failure_screenshot"], screenshot_path)
            self.assertEqual(index["last_full_screen_screenshot"], screenshot_path)
            self.assertEqual(index["last_ocr_json"], ocr_json_path)
            self.assertEqual(index["latest_action_event"]["event"], "click_denied")
            self.assertEqual(index["latest_ocr_event"]["event"], "ocr_scan")
            self.assertEqual(index["latest_dialog_event"]["event"], "popup_decision")
            self.assertEqual(index["latest_window_event"]["event"], "window_snapshot")
            self.assertEqual(index["current_step_journal_entry"]["event"], "step_start")
            self.assertEqual(index["exported_files"], ["exported/report.xlsx"])

    def test_log_events_redact_sensitive_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            observability = JobObservability(
                artifacts=artifacts,
                context=JobLogContext(
                    job_id="202605-001",
                    idempotency_key="company-tax-period-flow-v1",
                    run_mode="execute_no_send",
                    workflow="fake_job",
                    step="login",
                    attempt=1,
                    correlation_id="corr-1",
                ),
            )

            observability.log_action(
                "typing",
                "started",
                label="password field",
                password="plain-text-password",
                nested={"callback_secret": "secret-value", "safe": "visible"},
            )

            event = json.loads(
                (artifacts.logs_dir / "actions.jsonl").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(event["password"], "[REDACTED]")
            self.assertEqual(event["nested"]["callback_secret"], "[REDACTED]")
            self.assertEqual(event["nested"]["safe"], "visible")


if __name__ == "__main__":
    unittest.main()
