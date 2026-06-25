import unittest
from unittest.mock import patch

from tax_rpa.drivers import win32_driver

psutil = win32_driver.psutil
Win32Driver = win32_driver.Win32Driver


class FakeLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, name, status, **data):
        self.events.append((name, status, data))


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class Win32DriverProcessTerminationTests(unittest.TestCase):
    def test_terminate_processes_treats_access_denied_wait_as_gone_when_pid_disappeared(self):
        process = FakeProcess(15140)
        logger = FakeLogger()

        with (
            patch("tax_rpa.drivers.win32_driver.psutil.Process", return_value=process),
            patch(
                "tax_rpa.drivers.win32_driver.psutil.wait_procs",
                side_effect=psutil.AccessDenied(pid=15140, name="EPPortalITS.exe"),
            ),
            patch("tax_rpa.drivers.win32_driver.psutil.pid_exists", return_value=False),
        ):
            result = Win32Driver().terminate_processes([15140], 1, logger)

        self.assertTrue(process.terminated)
        self.assertEqual(result["terminated"], [15140])
        self.assertEqual(result["alive"], [])
        self.assertEqual(logger.events[-1][0:2], ("terminate_processes", "ok"))

    def test_terminate_processes_rechecks_alive_pids_before_reporting_failure(self):
        process = FakeProcess(20808)
        logger = FakeLogger()

        with (
            patch("tax_rpa.drivers.win32_driver.psutil.Process", return_value=process),
            patch(
                "tax_rpa.drivers.win32_driver.psutil.wait_procs",
                side_effect=[([], [process]), ([], [process])],
            ),
            patch("tax_rpa.drivers.win32_driver.psutil.pid_exists", return_value=False),
        ):
            result = Win32Driver().terminate_processes([20808], 60, logger)

        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(result["terminated"], [20808])
        self.assertEqual(result["alive"], [])
        self.assertEqual(logger.events[-1][0:2], ("terminate_processes", "ok"))


if __name__ == "__main__":
    unittest.main()
