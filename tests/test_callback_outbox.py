import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tax_rpa.jobs.artifact_store import ArtifactStore
from tax_rpa.jobs.callback_outbox import (
    CallbackOutbox,
    CallbackTransportResponse,
)


class CallbackOutboxTests(unittest.TestCase):
    def test_delivered_callback_writes_log_and_hmac_signature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            calls = []

            def transport(url, payload, headers, timeout_seconds):
                calls.append((url, payload, headers, timeout_seconds))
                return CallbackTransportResponse(status_code=204, body="ok")

            outbox = CallbackOutbox(
                artifacts=artifacts,
                callback_url="https://middle-platform.example/jobs/callback",
                callback_secret="top-secret",
                transport=transport,
            )

            result = outbox.deliver(self._payload())

            events = [
                json.loads(line)
                for line in (artifacts.logs_dir / "callbacks.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(result.callback_state, "delivered")
        self.assertIsNone(result.outbox_record_path)
        self.assertEqual(calls[0][0], "https://middle-platform.example/jobs/callback")
        self.assertEqual(calls[0][1]["job_id"], "202605-001")
        self.assertEqual(calls[0][3], 10)
        self.assertIn("X-Tax-Rpa-Signature", calls[0][2])
        self.assertNotIn("top-secret", json.dumps(events, ensure_ascii=False))
        self.assertEqual(events[-1]["event"], "callback_attempt")
        self.assertEqual(events[-1]["status"], "delivered")
        self.assertEqual(events[-1]["http_status"], 204)

    def test_failed_callback_creates_pending_outbox_record_without_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()

            def transport(_url, _payload, _headers, _timeout_seconds):
                return CallbackTransportResponse(status_code=503, body="unavailable")

            outbox = CallbackOutbox(
                artifacts=artifacts,
                callback_url="https://middle-platform.example/jobs/callback",
                callback_secret="top-secret",
                transport=transport,
            )

            result = outbox.deliver(self._payload())
            record = json.loads(
                (artifacts.root / result.outbox_record_path).read_text(encoding="utf-8")
            )
            events = [
                json.loads(line)
                for line in (artifacts.logs_dir / "callbacks.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(result.callback_state, "pending")
        self.assertEqual(result.outbox_record_path, "callback_outbox.json")
        self.assertEqual(record["callback_state"], "pending")
        self.assertEqual(record["attempt_count"], 1)
        self.assertEqual(record["last_http_status"], 503)
        self.assertEqual(record["payload"]["idempotency_key"], "company-tax-period-flow-v1")
        self.assertNotIn("top-secret", json.dumps(record, ensure_ascii=False))
        self.assertEqual(events[-1]["status"], "pending")

    def test_retry_moves_old_pending_record_to_dead_letter(self):
        now = datetime(2026, 5, 24, 8, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()

            def transport(_url, _payload, _headers, _timeout_seconds):
                return CallbackTransportResponse(status_code=500, body="still failing")

            outbox = CallbackOutbox(
                artifacts=artifacts,
                callback_url="https://middle-platform.example/jobs/callback",
                transport=transport,
                dead_letter_after=timedelta(seconds=1),
                now=lambda: now,
            )
            pending = outbox.deliver(self._payload())

            retry_outbox = CallbackOutbox(
                artifacts=artifacts,
                callback_url="https://middle-platform.example/jobs/callback",
                transport=transport,
                dead_letter_after=timedelta(seconds=1),
                now=lambda: now + timedelta(seconds=2),
            )
            result = retry_outbox.retry_due(pending.outbox_record_path)

            record = json.loads(
                (artifacts.root / pending.outbox_record_path).read_text(encoding="utf-8")
            )

        self.assertEqual(result.callback_state, "dead_letter")
        self.assertEqual(record["callback_state"], "dead_letter")
        self.assertEqual(record["attempt_count"], 2)

    def _payload(self):
        return {
            "job_id": "202605-001",
            "idempotency_key": "company-tax-period-flow-v1",
            "state": "succeeded",
            "business_status": "ready_to_submit_not_sent",
            "error": None,
            "summary_path": "summary.json",
            "artifact_manifest_path": "artifact_manifest.json",
        }


if __name__ == "__main__":
    unittest.main()
