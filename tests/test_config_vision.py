import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from bionic_eye import ViewSettings
from bionic_eye.config import APPEARANCES
from bionic_eye.vision import demo_frame, load_image, process, render_iris, rgb_image


class SettingsTests(unittest.TestCase):
    def test_invalid_values_rejected(self):
        for settings in ({"zoom": True}, {"zoom": 0}, {"zoom": 8.1}, {"zoom": float("nan")},
                         {"zoom": float("inf")}, {"zoom": "2"}, {"edges": 1}, {"low_light": "false"},
                         {"overlay": "a\ncommand"}, {"overlay": "x"*121}, {"overlay": None},
                         {"iris_color": "red"}, {"iris_color": "#12345G"}, {"appearance": "Unknown"}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                ViewSettings(**settings)

    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValueError):
            ViewSettings.from_dict({"stimulation_current": 2})
        with self.assertRaises(ValueError):
            ViewSettings.from_dict([])

    def test_immutable_settings_and_atomic_profile_roundtrip(self):
        original = ViewSettings()
        changed = original.updated(zoom=3, edges=True, overlay="Prueba español")
        self.assertEqual(original.zoom, 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"profile.json"
            changed.save(path)
            self.assertEqual(ViewSettings.load(path), changed)
            original.save(path)
            self.assertEqual(ViewSettings.load(path), original)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_profile_schema_and_size_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"profile.json"
            for raw in (json.dumps({"schema": True, "view": {}}), "{}", "[]", "x"*16_385,
                        json.dumps({"schema": 1, "view": {"zoom": float("nan")}})):
                with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                    path.write_text(raw)
                    ViewSettings.load(path)


class VisionTests(unittest.TestCase):
    def test_default_pixels_unchanged_and_no_input_alias(self):
        source = demo_frame()
        result = process(source, ViewSettings())
        self.assertEqual(source.tobytes(), result.tobytes())
        result.putpixel((0, 0), (255, 0, 0))
        self.assertNotEqual(source.getpixel((0, 0)), result.getpixel((0, 0)))

    def test_digital_zoom_crops_center(self):
        pixels = np.zeros((100, 100, 3), dtype=np.uint8)
        pixels[25:75, 25:75] = (200, 100, 50)
        result = np.asarray(process(pixels, ViewSettings(zoom=2)))
        self.assertTrue(np.all(result == (200, 100, 50)))

    def test_low_light_brightens_but_cannot_recover_black(self):
        source = Image.new("RGB", (32, 32), (25, 25, 25))
        self.assertGreater(process(source, ViewSettings(low_light=True)).getpixel((16, 16))[0], 25)
        black = Image.new("RGB", (32, 32))
        self.assertEqual(process(black, ViewSettings(low_light=True)).getbbox(), None)

    def test_auto_contrast_expands_luminance(self):
        source = np.tile(np.arange(100, 150, dtype=np.uint8), (50, 1))
        source = np.repeat(source[..., None], 3, axis=2)
        result = np.asarray(process(source, ViewSettings(auto_contrast=True)))
        self.assertGreater(int(result.max())-int(result.min()), 150)

    def test_all_transforms_produce_real_distinct_images(self):
        source = demo_frame(size=(320, 240))
        for key in ("low_light", "auto_contrast", "enhance", "edges", "segmentation", "phosphene"):
            with self.subTest(transform=key):
                result = process(source, ViewSettings(**{key: True}))
                self.assertEqual(result.size, source.size)
                self.assertEqual(result.mode, "RGB")
                self.assertNotEqual(result.tobytes(), source.tobytes())
        result = process(source, ViewSettings(zoom=2, low_light=True, auto_contrast=True,
                                               enhance=True, edges=True, segmentation=True,
                                               phosphene=True, overlay="All transforms"))
        self.assertEqual(result.size, source.size)

    def test_overlay_is_rendered_and_unicode_accepted(self):
        source = Image.new("RGB", (320, 240))
        result = process(source, ViewSettings(overlay="Vision • español"))
        self.assertNotEqual(source.tobytes(), result.tobytes())

    def test_iris_variants_are_digital_distinct_previews(self):
        previews = {render_iris(ViewSettings(appearance=name)).tobytes() for name in APPEARANCES}
        self.assertEqual(len(previews), len(APPEARANCES))
        self.assertNotEqual(render_iris(ViewSettings()).tobytes(),
                            render_iris(ViewSettings(iris_color="#FF0000")).tobytes())

    def test_invalid_frames_rejected(self):
        for frame in (None, np.zeros((2, 2)), np.zeros((2, 2, 4), np.uint8),
                      np.zeros((0, 2, 3), np.uint8), Image.new("1", (4097, 4097))):
            with self.subTest(kind=type(frame).__name__), self.assertRaises(ValueError):
                rgb_image(frame)

    def test_local_image_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.png"
            demo_frame().save(path)
            self.assertEqual(load_image(path).size, (640, 480))
