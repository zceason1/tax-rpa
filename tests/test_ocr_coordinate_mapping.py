import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tax_rpa.drivers.ocr_driver import OcrDriver


class FakeLogger:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.events = []

    def log(self, *args, **kwargs):
        self.events.append((args, kwargs))

    def write_json(self, name, data):
        path = self.out_dir / name
        path.write_text(str(data), encoding="utf-8")
        return str(path)


class FakeMouse:
    def __init__(self) -> None:
        self.clicked = []

    def click(self, point):
        self.clicked.append(point)
        return {"requested": point, "actual": point}


class OcrCoordinateMappingTests(unittest.TestCase):
    def test_click_text_maps_physical_ocr_point_to_logical_mouse_point_when_dpi_scaled(self):
        mouse = FakeMouse()
        ocr_rows = [
            [
                [[437.0, 148.0], [559.0, 148.0], [559.0, 175.0], [437.0, 175.0]],
                "申报密码登录",
                0.999,
            ]
        ]

        def fake_grab(bbox=None):
            if bbox is None:
                return Image.new("RGB", (1920, 1080), "white")
            width = max(1, int(bbox[2] - bbox[0]))
            height = max(1, int(bbox[3] - bbox[1]))
            return Image.new("RGB", (width, height), "white")

        with tempfile.TemporaryDirectory() as temp_dir:
            logger = FakeLogger(Path(temp_dir))
            with (
                patch("tax_rpa.drivers.ocr_driver.ImageGrab.grab", fake_grab),
                patch("tax_rpa.drivers.ocr_driver.load_ocr_engine", return_value=lambda _path: ocr_rows),
                patch("tax_rpa.drivers.ocr_driver.get_mouse_screen_size", return_value=(1280, 720), create=True),
            ):
                result = OcrDriver(mouse=mouse).click_text(
                    [768, 102, 1210, 593],
                    "申报密码登录",
                    logger,
                    0.35,
                    False,
                    "login_method",
                )

        self.assertEqual(mouse.clicked, [[1100, 210]])
        self.assertEqual(result["click"], [1100, 210])
        self.assertEqual(result["image_click"], [1650, 315])


if __name__ == "__main__":
    unittest.main()
