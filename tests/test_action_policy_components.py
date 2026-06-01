import unittest
from pathlib import Path
from types import SimpleNamespace

from tax_rpa.components.content_text import ContentTextComponent
from tax_rpa.components.file_dialog import FileDialogComponent
from tax_rpa.components.toolbar import ToolbarComponent
from tax_rpa.jobs.action_policy import ActionPolicy
from tax_rpa.pages.shared.dialogs import PageDialogMixin
from tax_rpa.runtime.context import RpaContext


class FakeLogger:
    def __init__(self) -> None:
        self.events = []

    def log(self, step, status, **data):
        self.events.append(("log", step, status, data))

    def screenshot(self, name, rect):
        self.events.append(("screenshot", name, rect))
        return f"{name}.png"


class FakeOcr:
    def __init__(self) -> None:
        self.clicks = []

    def click_text(self, rect, text, logger, min_score, dry_run, artifact_name):
        self.clicks.append((rect, text, min_score, dry_run, artifact_name))
        return {"label": text}


class FakeMouse:
    def __init__(self) -> None:
        self.clicked = []

    def click(self, point):
        self.clicked.append(point)
        return {"point": point}


class ActionPolicyComponentTests(unittest.TestCase):
    def test_toolbar_blocks_high_risk_label_before_ocr_click(self):
        ocr = FakeOcr()
        component = ToolbarComponent(
            content_rect=[0, 0, 100, 100],
            logger=FakeLogger(),
            min_score=0.35,
            dry_run=False,
            ocr=ocr,
            action_policy=ActionPolicy(run_mode="execute_no_send"),
        )

        result = component.click_button("发送申报")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "SUBMIT_NOT_AUTHORIZED")
        self.assertEqual(ocr.clicks, [])

    def test_content_text_blocks_data_change_in_inspect_only_before_ocr_click(self):
        ocr = FakeOcr()
        component = ContentTextComponent(
            content_rect=[0, 0, 100, 100],
            logger=FakeLogger(),
            min_score=0.35,
            dry_run=False,
            ocr=ocr,
            action_policy=ActionPolicy(run_mode="inspect_only"),
        )

        result = component.click_text("导入")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "run_mode_denied")
        self.assertEqual(ocr.clicks, [])

    def test_file_dialog_blocks_submit_in_inspect_only_before_setting_file(self):
        calls = []

        class FakeWin32:
            def collect_children(self, _hwnd):
                calls.append("collect_children")
                return []

            def find_largest_edit_control(self, _hwnd):
                calls.append("find_largest_edit_control")
                return None

            def find_button_by_labels(self, _children, _labels):
                calls.append("find_button_by_labels")
                return None

        component = FileDialogComponent(
            dialog={"hwnd": 40, "rect": [0, 0, 100, 100]},
            logger=FakeLogger(),
            dry_run=False,
            mouse=FakeMouse(),
            win32=FakeWin32(),
            action_policy=ActionPolicy(run_mode="inspect_only"),
        )

        result = component.choose_file(Path("person.xlsx"))

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "run_mode_denied")
        self.assertEqual(calls, [])

    def test_page_dialog_mixin_passes_context_action_policy_to_default_dialog_component(self):
        class FakeMessageDialog:
            def __init__(self, *_args, **kwargs):
                self.action_policy = kwargs["action_policy"]

            def close_with_action(self, _action):
                return SimpleNamespace(ok=True, evidence={"policy": self.action_policy})

        class Page(PageDialogMixin):
            def __init__(self, context):
                self.context = context
                self.hwnd = 100
                self.win32 = SimpleNamespace(set_foreground=lambda _hwnd: None)
                self.message_dialog = None

        policy = ActionPolicy(run_mode="inspect_only")
        context = RpaContext(
            config=SimpleNamespace(dry_run=True),
            logger=FakeLogger(),
            main_window={"pid": 1, "hwnd": 100},
            action_policy=policy,
        )

        from unittest.mock import patch

        with patch("tax_rpa.pages.shared.dialogs.MessageDialogComponent", FakeMessageDialog):
            result = Page(context).close_message_dialog_if_present("cancel")

        self.assertIs(result.evidence["policy"], policy)


if __name__ == "__main__":
    unittest.main()
