import unittest
from pathlib import Path

from tax_rpa.app.tax_client_app import TaxClientApp
from tax_rpa.config.person_import import PersonImportConfig


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    def log(self, name, status, **data):
        self.events.append((name, status, data))


class FakeWin32:
    def __init__(self, pids):
        self.pids = pids
        self.killed = []
        self.configured = []

    def configure_base_process_name(self, process_name):
        self.configured.append(process_name)

    def find_process_ids(self, process_name):
        return list(self.pids)

    def terminate_processes(self, pids, timeout_seconds, logger):
        self.killed.extend(pids)
        self.pids = []
        return {"terminated": pids, "alive": [], "timeout_seconds": timeout_seconds}


class ResetAppTests(unittest.TestCase):
    def test_reset_terminates_existing_client_processes(self):
        logger = FakeLogger()
        win32 = FakeWin32([100, 101])
        app = TaxClientApp(
            PersonImportConfig(person_info_file=Path("persons.xlsx"), process_name="client.exe"),
            logger,
            win32=win32,
        )

        result = app.reset()

        self.assertTrue(result.ok)
        self.assertEqual(win32.configured, ["client.exe"])
        self.assertEqual(win32.killed, [100, 101])
        self.assertEqual(result.status, "terminated")

    def test_reset_is_ok_when_client_is_not_running(self):
        logger = FakeLogger()
        win32 = FakeWin32([])
        app = TaxClientApp(
            PersonImportConfig(person_info_file=Path("persons.xlsx"), process_name="client.exe"),
            logger,
            win32=win32,
        )

        result = app.reset()

        self.assertTrue(result.ok)
        self.assertEqual(win32.killed, [])
        self.assertEqual(result.status, "not_running")


if __name__ == "__main__":
    unittest.main()
