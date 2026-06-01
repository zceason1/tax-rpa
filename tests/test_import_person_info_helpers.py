import unittest

from tax_rpa.components.import_result import classify_import_result
from tax_rpa.components.left_nav import should_try_home_card_fallback
from tax_rpa.components.message_dialog import is_blocking_dialog
from tax_rpa.drivers.mouse_driver import point_near
from tax_rpa.drivers.ocr_driver import find_best_ocr_match
from tax_rpa.drivers.win32_driver import find_button_by_labels


IMPORT_TEXT = "\u5bfc\u5165"
IMPORT_FILE_TEXT = "\u5bfc\u5165\u6587\u4ef6"
STANDARD_TEMPLATE_IMPORT_TEXT = "\u6807\u51c6\u6a21\u677f\u5bfc\u5165"
PERSON_INFO_PAGE_TEXT = "\u4eba\u5458\u4fe1\u606f\u91c7\u96c6"
SUCCESS_TEXT = "\u5bfc\u5165\u6210\u529f"
FAILURE_TEXT = "\u5bfc\u5165\u5931\u8d25"
EMPTY_ID_TEXT = "\u8eab\u4efd\u8bc1\u53f7\u7801\u4e0d\u80fd\u4e3a\u7a7a"
UNKNOWN_PROMPT_TEXT = "\u8bf7\u9009\u62e9\u8981\u5bfc\u5165\u7684\u6587\u4ef6"
CORRECT_INFO_TEXT = "\u4fe1\u606f\u6b63\u786e(1)"
SUBMIT_DATA_TEXT = "\u63d0\u4ea4\u6570\u636e"
ALL_SUBMITTED_SUCCESS_TEXT = "\u4fe1\u606f\u5df2\u5168\u90e8\u63d0\u4ea4\u6210\u529f"
ERROR_GUIDANCE_TEXT = (
    "\u9519\u8bef\u6570\u636e\u60a8\u53ef\u76f4\u63a5\u5728\u672c\u5730\u539f\u6587\u4ef6"
    "\u4fee\u6539\u540e\uff0c\u70b9\u51fb\u3010\u91cd\u65b0\u6821\u9a8c\u672c\u5730\u6587\u4ef6\u3011\u3002"
)
COMPLETE_TEXT = "\u5b8c\u6210"
MAIN_WINDOW_TITLE = "\u81ea\u7136\u4eba\u7535\u5b50\u7a0e\u52a1\u5c40\uff08\u6263\u7f34\u7aef\uff09"
CANCEL_TEXT = "\u53d6\u6d88"
OPEN_TEXT = "\u6253\u5f00"


class ImportPersonInfoHelperTests(unittest.TestCase):
    def test_find_best_ocr_match_returns_highest_valid_match(self):
        rows = [
            {
                "text": IMPORT_TEXT,
                "score": 0.30,
                "box": [[10, 10], [40, 10], [40, 30], [10, 30]],
            },
            {
                "text": STANDARD_TEMPLATE_IMPORT_TEXT,
                "score": 0.88,
                "box": [[20, 20], [130, 20], [130, 45], [20, 45]],
            },
        ]

        match = find_best_ocr_match(rows, STANDARD_TEMPLATE_IMPORT_TEXT, (200, 100), 0.35)

        self.assertIsNotNone(match)
        self.assertEqual(match["text"], STANDARD_TEMPLATE_IMPORT_TEXT)

    def test_find_best_ocr_match_prefers_full_text_over_higher_scored_fragment(self):
        rows = [
            {
                "text": PERSON_INFO_PAGE_TEXT,
                "score": 0.98,
                "box": [[10, 10], [130, 10], [130, 35], [10, 35]],
            },
            {
                "text": "\u606f\u91c7\u96c6",
                "score": 0.999,
                "box": [[220, 80], [280, 80], [280, 105], [220, 105]],
            },
        ]

        match = find_best_ocr_match(rows, PERSON_INFO_PAGE_TEXT, (400, 200), 0.35)

        self.assertIsNotNone(match)
        self.assertEqual(match["text"], PERSON_INFO_PAGE_TEXT)

    def test_find_best_ocr_match_ignores_outside_image_box(self):
        rows = [
            {
                "text": IMPORT_TEXT,
                "score": 0.99,
                "box": [[210, 10], [250, 10], [250, 30], [210, 30]],
            }
        ]

        match = find_best_ocr_match(rows, IMPORT_TEXT, (200, 100), 0.35)

        self.assertIsNone(match)

    def test_find_best_ocr_match_does_not_treat_short_generic_text_as_long_menu_option(self):
        rows = [
            {
                "text": IMPORT_TEXT,
                "score": 0.99,
                "box": [[10, 10], [60, 10], [60, 35], [10, 35]],
            }
        ]

        match = find_best_ocr_match(rows, IMPORT_FILE_TEXT, (200, 100), 0.35)

        self.assertIsNone(match)

    def test_classify_import_result_success(self):
        result = classify_import_result([SUCCESS_TEXT, "\u5171\u5bfc\u5165 3 \u6761\u4eba\u5458\u4fe1\u606f"])

        self.assertEqual(result, "success")

    def test_classify_import_result_all_submitted_success(self):
        result = classify_import_result([ALL_SUBMITTED_SUCCESS_TEXT, "\u786e\u5b9a"])

        self.assertEqual(result, "success")

    def test_classify_import_result_success_overrides_stale_submit_container(self):
        result = classify_import_result(
            [
                CORRECT_INFO_TEXT,
                SUBMIT_DATA_TEXT,
                ERROR_GUIDANCE_TEXT,
                ALL_SUBMITTED_SUCCESS_TEXT,
                COMPLETE_TEXT,
            ]
        )

        self.assertEqual(result, "success")

    def test_classify_import_result_failure(self):
        result = classify_import_result([FAILURE_TEXT, EMPTY_ID_TEXT])

        self.assertEqual(result, "failed")

    def test_classify_import_result_ready_to_submit(self):
        result = classify_import_result(
            [
                CORRECT_INFO_TEXT,
                SUBMIT_DATA_TEXT,
                ERROR_GUIDANCE_TEXT,
            ]
        )

        self.assertEqual(result, "ready_to_submit")

    def test_classify_import_result_unknown(self):
        result = classify_import_result([UNKNOWN_PROMPT_TEXT])

        self.assertEqual(result, "unknown")

    def test_should_try_home_card_fallback_when_person_card_exists_without_import_button(self):
        page_match = {"text": PERSON_INFO_PAGE_TEXT, "score": 0.99}

        self.assertTrue(should_try_home_card_fallback(page_match, None))

    def test_should_not_try_home_card_fallback_when_import_button_exists(self):
        page_match = {"text": PERSON_INFO_PAGE_TEXT, "score": 0.99}
        import_match = {"text": IMPORT_TEXT, "score": 0.99}

        self.assertFalse(should_try_home_card_fallback(page_match, import_match))

    def test_is_blocking_dialog_detects_rich_message_dialog(self):
        window = {"class": "Tfrm_MsgDlgRich", "title": "frm_MsgDlgRich", "area": 10000}

        self.assertTrue(is_blocking_dialog(window))

    def test_is_blocking_dialog_ignores_main_window(self):
        window = {"class": "Tfrm_MainFrame", "title": MAIN_WINDOW_TITLE, "area": 100000}

        self.assertFalse(is_blocking_dialog(window))

    def test_point_near_allows_small_cursor_rounding_difference(self):
        self.assertTrue(point_near([494, 380], [495, 381], tolerance=2))
        self.assertFalse(point_near([494, 380], [504, 380], tolerance=2))

    def test_find_button_by_labels_returns_visible_matching_button(self):
        children = [
            {"class": "Button", "title": CANCEL_TEXT, "visible": True, "rect": [1, 1, 10, 10]},
            {"class": "Button", "title": f"{OPEN_TEXT}(&O)", "visible": True, "rect": [2, 2, 20, 20]},
        ]

        button = find_button_by_labels(children, (OPEN_TEXT, "Open"))

        self.assertIsNotNone(button)
        self.assertEqual(button["title"], f"{OPEN_TEXT}(&O)")


if __name__ == "__main__":
    unittest.main()
