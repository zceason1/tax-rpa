import unittest

from tax_rpa.components.import_result import classify_import_result
from tax_rpa.components.left_nav import should_try_home_card_fallback
from tax_rpa.components.message_dialog import is_blocking_dialog
from tax_rpa.drivers.mouse_driver import point_near
from tax_rpa.drivers.ocr_driver import find_best_ocr_match
from tax_rpa.drivers.win32_driver import find_button_by_labels


class ImportPersonInfoHelperTests(unittest.TestCase):
    def test_find_best_ocr_match_returns_highest_valid_match(self):
        rows = [
            {
                "text": "导入",
                "score": 0.30,
                "box": [[10, 10], [40, 10], [40, 30], [10, 30]],
            },
            {
                "text": "标准模板导入",
                "score": 0.88,
                "box": [[20, 20], [130, 20], [130, 45], [20, 45]],
            },
        ]

        match = find_best_ocr_match(rows, "标准模板导入", (200, 100), 0.35)

        self.assertIsNotNone(match)
        self.assertEqual(match["text"], "标准模板导入")

    def test_find_best_ocr_match_prefers_full_text_over_higher_scored_fragment(self):
        rows = [
            {
                "text": "人员信息采集",
                "score": 0.98,
                "box": [[10, 10], [130, 10], [130, 35], [10, 35]],
            },
            {
                "text": "息采集",
                "score": 0.999,
                "box": [[220, 80], [280, 80], [280, 105], [220, 105]],
            },
        ]

        match = find_best_ocr_match(rows, "人员信息采集", (400, 200), 0.35)

        self.assertIsNotNone(match)
        self.assertEqual(match["text"], "人员信息采集")

    def test_find_best_ocr_match_ignores_outside_image_box(self):
        rows = [
            {
                "text": "导入",
                "score": 0.99,
                "box": [[210, 10], [250, 10], [250, 30], [210, 30]],
            }
        ]

        match = find_best_ocr_match(rows, "导入", (200, 100), 0.35)

        self.assertIsNone(match)

    def test_classify_import_result_success(self):
        result = classify_import_result(["导入成功", "共导入 3 条人员信息"])

        self.assertEqual(result, "success")

    def test_classify_import_result_failure(self):
        result = classify_import_result(["导入失败", "身份证号码不能为空"])

        self.assertEqual(result, "failed")

    def test_classify_import_result_unknown(self):
        result = classify_import_result(["请选择要导入的文件"])

        self.assertEqual(result, "unknown")

    def test_should_try_home_card_fallback_when_person_card_exists_without_import_button(self):
        page_match = {"text": "人员信息采集", "score": 0.99}

        self.assertTrue(should_try_home_card_fallback(page_match, None))

    def test_should_not_try_home_card_fallback_when_import_button_exists(self):
        page_match = {"text": "人员信息采集", "score": 0.99}
        import_match = {"text": "导入", "score": 0.99}

        self.assertFalse(should_try_home_card_fallback(page_match, import_match))

    def test_is_blocking_dialog_detects_rich_message_dialog(self):
        window = {"class": "Tfrm_MsgDlgRich", "title": "frm_MsgDlgRich", "area": 10000}

        self.assertTrue(is_blocking_dialog(window))

    def test_is_blocking_dialog_ignores_main_window(self):
        window = {"class": "Tfrm_MainFrame", "title": "自然人电子税务局（扣缴端）", "area": 100000}

        self.assertFalse(is_blocking_dialog(window))

    def test_point_near_allows_small_cursor_rounding_difference(self):
        self.assertTrue(point_near([494, 380], [495, 381], tolerance=2))
        self.assertFalse(point_near([494, 380], [504, 380], tolerance=2))

    def test_find_button_by_labels_returns_visible_matching_button(self):
        children = [
            {"class": "Button", "title": "取消", "visible": True, "rect": [1, 1, 10, 10]},
            {"class": "Button", "title": "打开(&O)", "visible": True, "rect": [2, 2, 20, 20]},
        ]

        button = find_button_by_labels(children, ("打开", "Open"))

        self.assertIsNotNone(button)
        self.assertEqual(button["title"], "打开(&O)")


if __name__ == "__main__":
    unittest.main()
