import unittest
from unittest.mock import patch

from tax_rpa.drivers.mouse_driver import MouseDriver


class MouseDriverTests(unittest.TestCase):
    def test_move_to_retries_set_cursor_pos_until_cursor_reaches_target(self):
        positions = [[100, 100], [100, 100], [300, 400]]
        set_calls = []

        def fake_set_cursor_pos(x, y):
            set_calls.append([x, y])
            return True

        def fake_get_cursor_point():
            if positions:
                return positions.pop(0)
            return [300, 400]

        with (
            patch("tax_rpa.drivers.mouse_driver.MouseSetCursorPos", fake_set_cursor_pos),
            patch("tax_rpa.drivers.mouse_driver.get_cursor_point", fake_get_cursor_point),
            patch("tax_rpa.drivers.mouse_driver.time.sleep", lambda _seconds: None),
        ):
            result = MouseDriver().move_to([300, 400])

        self.assertEqual(result["move_method"], "SetCursorPos")
        self.assertEqual(result["actual"], [300, 400])
        self.assertGreaterEqual(len(set_calls), 2)


if __name__ == "__main__":
    unittest.main()
