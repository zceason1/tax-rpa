import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.import_dropdown import ImportDropdownComponent
from tax_rpa.components.left_nav import LeftNavComponent
from tax_rpa.components.message_dialog import MessageDialogComponent, close_blocking_dialogs
from tax_rpa.components.toolbar import ToolbarComponent


class FakeLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, step, status, **data):
        self.events.append(("log", step, status, data))

    def screenshot(self, name, rect):
        self.events.append(("screenshot", name, rect))
        return f"{name}.png"

    def write_json(self, name, data):
        self.events.append(("write_json", name, data))
        return name


class FakeMouse:
    def __init__(self) -> None:
        self.clicked = []

    def click(self, point):
        self.clicked.append(point)
        return {"requested": point, "actual": point}


class FakeOcr:
    def __init__(self) -> None:
        self.clicks = []

    def click_text(self, rect, text, logger, min_score, dry_run, artifact_name):
        self.clicks.append((rect, text, min_score, dry_run, artifact_name))
        return {"click": [rect[0], rect[1]], "label": text}


class DriverBoundaryTests(unittest.TestCase):
    def test_launch_client_uses_shell_execute_for_shortcuts(self):
        from tax_rpa.drivers.win32_driver import Win32Driver

        logger = FakeLogger()
        shell_execute = Mock(return_value=33)

        with patch("tax_rpa.drivers.win32_driver.ShellExecuteW", shell_execute):
            result = Win32Driver().launch_client(Path("C:/client/自然人电子税务局.lnk"), logger)

        self.assertIsNone(result)
        shell_execute.assert_called_once()
        self.assertEqual(shell_execute.call_args.args[1], "open")
        self.assertEqual(shell_execute.call_args.args[2], "C:\\client\\自然人电子税务局.lnk")

    def test_import_dropdown_uses_injected_win32_for_existing_file_dialog(self):
        calls = []

        class FakeWin32:
            def find_file_dialog(self, timeout_seconds, allowed_pids=None):
                calls.append(("find_file_dialog", timeout_seconds, allowed_pids))
                return {"hwnd": 20, "pid": 10, "rect": [1, 2, 3, 4]}

        component = ImportDropdownComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(import_timeout_seconds=10, ocr_score_threshold=0.35, dry_run=True),
            allowed_pids={10},
            win32=FakeWin32(),
        )

        result = component.choose_item("导入文件")

        self.assertTrue(result.ok)
        self.assertEqual(result.evidence["dialog"]["hwnd"], 20)
        self.assertEqual(calls, [("find_file_dialog", 3, {10})])

    def test_file_dialog_uses_injected_win32_and_mouse(self):
        calls = []

        class FakeWin32:
            def collect_children(self, hwnd):
                calls.append(("collect_children", hwnd))
                return [{"class": "Button", "title": "打开", "visible": True, "rect": [10, 20, 30, 40]}]

            def find_largest_edit_control(self, dialog_hwnd):
                calls.append(("find_largest_edit_control", dialog_hwnd))
                return {"hwnd": 30, "class": "Edit", "rect": [1, 2, 3, 4]}

            def find_button_by_labels(self, children, labels):
                calls.append(("find_button_by_labels", tuple(labels)))
                return children[0]

            def set_foreground(self, hwnd):
                calls.append(("set_foreground", hwnd))

            def set_window_text(self, hwnd, text):
                calls.append(("set_window_text", hwnd, text))

            def rect_center(self, rect):
                calls.append(("rect_center", rect))
                return [20, 30]

            def wait_for_dialog_closed(self, hwnd, timeout_seconds):
                calls.append(("wait_for_dialog_closed", hwnd, timeout_seconds))
                return True

        mouse = FakeMouse()
        component = FileDialogComponent(
            dialog={"hwnd": 40, "rect": [0, 0, 100, 100]},
            logger=FakeLogger(),
            dry_run=False,
            mouse=mouse,
            win32=FakeWin32(),
        )

        result = component.choose_file(Path("persons.xlsx"))

        self.assertTrue(result.ok)
        self.assertEqual(mouse.clicked, [[20, 30]])
        self.assertIn(("set_window_text", 30, "persons.xlsx"), calls)
        self.assertIn(("wait_for_dialog_closed", 40, 30), calls)

    def test_left_nav_uses_injected_win32_for_window_geometry(self):
        calls = []

        class FakeWin32:
            def get_rect(self, hwnd):
                calls.append(("get_rect", hwnd))
                return [0, 0, 1000, 800]

            def collect_children(self, hwnd):
                calls.append(("collect_children", hwnd))
                return [{"rect": [0, 100, 160, 780]}]

        class FakeRegion:
            def detect_left_nav_rect(self, rect, children):
                calls.append(("detect_left_nav_rect", rect, children))
                return [0, 100, 160, 780], {"source": "fake"}

        ocr = FakeOcr()
        component = LeftNavComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=True, window_timeout_seconds=1),
            ocr=ocr,
            region=FakeRegion(),
            win32=FakeWin32(),
        )

        result = component.open_page("人员信息采集")

        self.assertTrue(result.ok)
        self.assertEqual(calls[0], ("get_rect", 100))
        self.assertEqual(calls[1], ("collect_children", 100))
        self.assertEqual(ocr.clicks[0][0], [0, 100, 160, 780])

    def test_left_nav_clicks_even_when_workflow_is_dry_run(self):
        class FakeWin32:
            def get_rect(self, _hwnd):
                return [0, 0, 1000, 800]

            def collect_children(self, _hwnd):
                return [{"rect": [0, 100, 160, 780]}]

        class FakeRegion:
            def detect_left_nav_rect(self, _rect, _children):
                return [0, 100, 160, 780], {"source": "fake"}

        ocr = FakeOcr()
        component = LeftNavComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=True, window_timeout_seconds=1),
            ocr=ocr,
            region=FakeRegion(),
            win32=FakeWin32(),
        )

        result = component.open_page("人员信息采集")

        self.assertTrue(result.ok)
        self.assertFalse(ocr.clicks[0][3])

    def test_left_nav_clicks_menu_when_initial_ready_check_is_false(self):
        class FakeWin32:
            def get_rect(self, _hwnd):
                return [0, 0, 1000, 800]

            def collect_children(self, _hwnd):
                return [{"rect": [0, 100, 160, 780]}]

        class FakeRegion:
            def detect_left_nav_rect(self, _rect, _children):
                return [0, 100, 160, 780], {"source": "fake"}

        ready_checks = []

        def ready_check():
            ready_checks.append("check")
            return len(ready_checks) >= 2

        ocr = FakeOcr()
        component = LeftNavComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(ocr_score_threshold=0.35, dry_run=True, window_timeout_seconds=1),
            ocr=ocr,
            region=FakeRegion(),
            win32=FakeWin32(),
        )

        result = component.open_page("专项附加扣除信息采集", ready_check=ready_check)

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "navigated")
        self.assertEqual(len(ocr.clicks), 1)
        self.assertEqual(ocr.clicks[0][1], "专项附加扣除信息采集")

    def test_toolbar_clicks_even_when_workflow_is_dry_run(self):
        ocr = FakeOcr()
        component = ToolbarComponent(
            content_rect=[10, 20, 300, 80],
            logger=FakeLogger(),
            min_score=0.35,
            dry_run=True,
            ocr=ocr,
        )

        result = component.click_button("导入")

        self.assertTrue(result.ok)
        self.assertFalse(ocr.clicks[0][3])

    def test_import_dropdown_clicks_option_even_when_workflow_is_dry_run(self):
        calls = []

        class FakeWin32:
            def __init__(self):
                self.find_calls = 0

            def find_file_dialog(self, timeout_seconds, allowed_pids=None):
                calls.append(("find_file_dialog", timeout_seconds, allowed_pids))
                self.find_calls += 1
                if self.find_calls >= 3:
                    return {"hwnd": 20, "pid": 10, "rect": [1, 2, 3, 4]}
                return None

            def get_rect(self, hwnd):
                calls.append(("get_rect", hwnd))
                return [0, 0, 800, 600]

        ocr = FakeOcr()
        component = ImportDropdownComponent(
            hwnd=100,
            logger=FakeLogger(),
            config=SimpleNamespace(import_timeout_seconds=10, ocr_score_threshold=0.35, dry_run=True),
            allowed_pids={10},
            ocr=ocr,
            win32=FakeWin32(),
        )

        result = component.choose_item("导入文件")

        self.assertTrue(result.ok)
        self.assertFalse(ocr.clicks[0][3])

    def test_message_dialog_uses_injected_win32_for_dialog_collection(self):
        calls = []

        class FakeWin32:
            def collect_top_windows(self):
                calls.append(("collect_top_windows",))
                return [
                    {
                        "hwnd": 200,
                        "pid": 10,
                        "class": "Tfrm_MsgDlgRich",
                        "title": "message",
                        "area": 12000,
                    }
                ]

            def collect_window_texts(self, hwnd):
                calls.append(("collect_window_texts", hwnd))
                return ["message"]

        component = MessageDialogComponent(
            allowed_pids={10},
            logger=FakeLogger(),
            dry_run=True,
            win32=FakeWin32(),
        )

        result = component.close_if_present()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "none")
        self.assertEqual(calls, [("collect_top_windows",), ("collect_window_texts", 200)])

    def test_message_dialog_clicks_confirm_button_when_requested(self):
        calls = []

        class FakeWin32:
            def __init__(self):
                self.top_calls = 0

            def collect_top_windows(self):
                self.top_calls += 1
                if self.top_calls > 1:
                    return []
                return [
                    {
                        "hwnd": 200,
                        "pid": 10,
                        "class": "Tfrm_MsgDlgRich",
                        "title": "message",
                        "area": 12000,
                        "rect": [0, 0, 200, 120],
                    }
                ]

            def collect_window_texts(self, hwnd):
                calls.append(("collect_window_texts", hwnd))
                return ["message"]

            def collect_children(self, hwnd):
                calls.append(("collect_children", hwnd))
                return [
                    {"hwnd": 31, "class": "Button", "title": "取消", "visible": True, "rect": [1, 1, 21, 21]},
                    {"hwnd": 32, "class": "Button", "title": "确定", "visible": True, "rect": [30, 1, 50, 21]},
                ]

            def set_foreground(self, hwnd):
                calls.append(("set_foreground", hwnd))

            def find_button_by_labels(self, children, labels):
                calls.append(("find_button_by_labels", tuple(labels)))
                for child in children:
                    if child["title"] in labels:
                        return child
                return None

            def rect_center(self, rect):
                return [40, 10]

        mouse = FakeMouse()

        closed = close_blocking_dialogs(
            allowed_pids={10},
            logger=FakeLogger(),
            dry_run=False,
            action="confirm",
            mouse=mouse,
            win32=FakeWin32(),
        )

        self.assertEqual(len(closed), 1)
        self.assertEqual(mouse.clicked, [[40, 10]])
        self.assertIn(("find_button_by_labels", ("确定", "确认", "是", "OK", "Yes")), calls)

    def test_message_dialog_clicks_cancel_button_when_requested(self):
        calls = []

        class FakeWin32:
            def __init__(self):
                self.top_calls = 0

            def collect_top_windows(self):
                self.top_calls += 1
                if self.top_calls > 1:
                    return []
                return [
                    {
                        "hwnd": 200,
                        "pid": 10,
                        "class": "Tfrm_MsgDlgRich",
                        "title": "message",
                        "area": 12000,
                        "rect": [0, 0, 200, 120],
                    }
                ]

            def collect_window_texts(self, hwnd):
                return ["message"]

            def collect_children(self, hwnd):
                return [
                    {"hwnd": 31, "class": "Button", "title": "取消", "visible": True, "rect": [1, 1, 21, 21]},
                    {"hwnd": 32, "class": "Button", "title": "确定", "visible": True, "rect": [30, 1, 50, 21]},
                ]

            def set_foreground(self, hwnd):
                calls.append(("set_foreground", hwnd))

            def find_button_by_labels(self, children, labels):
                calls.append(("find_button_by_labels", tuple(labels)))
                for child in children:
                    if child["title"] in labels:
                        return child
                return None

            def rect_center(self, rect):
                return [10, 10]

        mouse = FakeMouse()

        closed = close_blocking_dialogs(
            allowed_pids={10},
            logger=FakeLogger(),
            dry_run=False,
            action="cancel",
            mouse=mouse,
            win32=FakeWin32(),
        )

        self.assertEqual(len(closed), 1)
        self.assertEqual(mouse.clicked, [[10, 10]])
        self.assertIn(("find_button_by_labels", ("取消", "否", "关闭", "Cancel", "No")), calls)


if __name__ == "__main__":
    unittest.main()
