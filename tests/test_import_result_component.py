import unittest
from types import SimpleNamespace

from tax_rpa.pages.person_info.components.import_result import ImportResultComponent


class FakeLogger:
    def screenshot(self, *_args, **_kwargs):
        return "screenshot.png"

    def log(self, *_args, **_kwargs):
        pass


class FixedImportResultComponent(ImportResultComponent):
    def __init__(self, status):
        super().__init__(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(dry_run=False, result_timeout_seconds=1),
            allowed_pids={1},
        )
        self.fixed_status = status

    def wait_for_import_result(self):
        return {"status": self.fixed_status, "source": "test"}


class ImportResultComponentTests(unittest.TestCase):
    def test_success_result_is_ok(self):
        result = FixedImportResultComponent("success").read_result()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "success")
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def test_failed_result_is_not_ok(self):
        result = FixedImportResultComponent("failed").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_type, "IMPORT_FAILED")
        self.assertEqual(result.error_code, "person_import_failed")
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def test_unknown_result_is_not_ok(self):
        result = FixedImportResultComponent("unknown").read_result()

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_type, "UNKNOWN_RESULT")
        self.assertEqual(result.error_code, "person_import_result_unknown")
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def test_ready_to_submit_result_is_ok(self):
        result = FixedImportResultComponent("ready_to_submit").read_result()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ready_to_submit")
        self.assertIsNone(result.error_type)
        self.assertIsNone(result.error_code)
        self.assertTrue(result.side_effect_started)
        self.assertTrue(result.side_effect_committed)
        self.assertFalse(result.retry_allowed)

    def test_wait_for_import_result_accepts_success_rich_dialog(self):
        class FakeWin32:
            def collect_top_windows(self):
                return [
                    {
                        "hwnd": 200,
                        "pid": 1,
                        "class": "Tfrm_MsgDlgRich",
                        "title": "提示信息",
                        "area": 12000,
                        "rect": [0, 0, 200, 120],
                    }
                ]

            def collect_window_texts(self, hwnd):
                self.last_hwnd = hwnd
                return ["信息已全部提交成功", "确定"]

        component = ImportResultComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(dry_run=False, result_timeout_seconds=1),
            allowed_pids={1},
            win32=FakeWin32(),
        )

        result = component.wait_for_import_result()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "dialog")


if __name__ == "__main__":
    unittest.main()
