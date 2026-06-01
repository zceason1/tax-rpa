import json
import tempfile
import unittest
from pathlib import Path

from tax_rpa.jobs.artifact_store import ArtifactStore
from tax_rpa.jobs.state_store import StateStore, StateTransitionError


class StateStoreTests(unittest.TestCase):
    def test_initialize_writes_received_state_and_transition_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            store = StateStore(artifacts.root)

            record = store.initialize("202605-001")

            self.assertEqual(record.state, "received")
            state_data = json.loads((artifacts.root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state_data["job_id"], "202605-001")
            self.assertEqual(state_data["state"], "received")
            transitions = (artifacts.logs_dir / "state_transitions.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(transitions), 1)
            self.assertEqual(json.loads(transitions[0])["to_state"], "received")

    def test_valid_transitions_update_state_and_append_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            store = StateStore(artifacts.root)
            store.initialize("202605-001")

            store.transition("validating", current_step="manifest")
            record = store.transition("queued")

            self.assertEqual(record.state, "queued")
            state_data = json.loads((artifacts.root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state_data["state"], "queued")
            transitions = (artifacts.logs_dir / "state_transitions.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                [json.loads(line)["to_state"] for line in transitions],
                ["received", "validating", "queued"],
            )

    def test_invalid_transition_is_rejected_without_overwriting_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = ArtifactStore(Path(temp_dir)).for_job("202605-001")
            artifacts.initialize()
            store = StateStore(artifacts.root)
            store.initialize("202605-001")

            with self.assertRaises(StateTransitionError):
                store.transition("running")

            state_data = json.loads((artifacts.root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state_data["state"], "received")


if __name__ == "__main__":
    unittest.main()
