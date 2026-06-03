import unittest

from tax_rpa.drivers.mouse_driver import point_near
from tax_rpa.drivers.ocr_driver import find_best_ocr_match
from tax_rpa.drivers.win32_driver import find_button_by_labels
from tax_rpa.pages.person_info.elements.import_result import classify_import_result
from tax_rpa.pages.shared.components.left_nav import should_try_home_card_fallback
from tax_rpa.pages.shared.components.message_dialog import is_blocking_dialog


IMPORT_TEXT = "导入"
IMPORT_FILE_TEXT = "导入文件"
STANDARD_TEMPLATE_IMPORT_TEXT = "标准模板导入"
PERSON_INFO_PAGE_TEXT = "人员信息采集"
SUCCESS_TEXT = "导入成功"
FAILURE_TEXT = "导入失败"
EMPTY_ID_TEXT = "身份证号码不能为空"
UNKNOWN_PROMPT_TEXT = "请选择要导入的文件"
CORRECT_INFO_TEXT = "信息正确(1)"
SUBMIT_DATA_TEXT = "提交数据"
ALL_SUBMITTED_SUCCESS_TEXT = "信息已全部提交成功"
ERROR_GUIDANCE_TEXT = (
    "错误数据您可直接在本地原文件"
    "修改后，点击【重新校验本地文件】。"
)
COMPLETE_TEXT = "完成"
MAIN_WINDOW_TITLE = "自然人电子税务局（扣缴端）"
CANCEL_TEXT = "取消"
OPEN_TEXT = "打开"


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
                "text": "息采集",
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
        result = classify_import_result([SUCCESS_TEXT, "共导入 3 条人员信息"])

        self.assertEqual(result, "success")

    def test_classify_import_result_all_submitted_success(self):
        result = classify_import_result([ALL_SUBMITTED_SUCCESS_TEXT, "确定"])

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
