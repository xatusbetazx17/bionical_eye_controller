import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image

from bionic_eye import BionicEyeController, ViewSettings
from bionic_eye.protocol import decode_message, encode_message


class CLITests(unittest.TestCase):
    def run_cli(self, *args, **kwargs):
        return subprocess.run([sys.executable, "-m", "bionic_eye", *args],
                              capture_output=True, timeout=15, **kwargs)

    def test_camera_free_demo_and_image_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory)/"demo.png", Path(directory)/"processed.png"
            result = self.run_cli("demo", "--output", str(first), "--low-light")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["diagnostics"]["frames_processed"], 1)
            result = self.run_cli("process", str(first), "--output", str(second), "--zoom", "2", "--edges")
            self.assertEqual(result.returncode, 0, result.stderr)
            with Image.open(first) as original, Image.open(second) as processed:
                self.assertEqual(original.size, processed.size)
                self.assertNotEqual(original.tobytes(), processed.tobytes())

    def test_bad_input_and_existing_output_return_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"output.png"
            path.write_bytes(b"preserve me")
            for args in (("demo", "--output", str(path)),
                         ("demo", "--output", str(path), "--zoom", "nan"),
                         ("process", "missing-input.png", "--output", str(path))):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"Error:", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertEqual(path.read_bytes(), b"preserve me")

    def test_profile_flags_can_disable_saved_feature(self):
        with tempfile.TemporaryDirectory() as directory:
            profile, output = Path(directory)/"profile.json", Path(directory)/"output.png"
            ViewSettings(edges=True, zoom=2).save(profile)
            result = self.run_cli("demo", "--profile", str(profile), "--no-edges", "--output", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            view = json.loads(result.stdout)["diagnostics"]["settings"]
            self.assertFalse(view["edges"])
            self.assertEqual(view["zoom"], 2)

    def test_stdio_emulator_roundtrip(self):
        messages = b"".join(encode_message(dict(protocol=1, id=str(i), operation=operation, params=params))
                             for i, (operation, params) in enumerate((
                                 ("hello", {}), ("view.configure", {"zoom": 3}), ("diagnostics", {}))))
        result = self.run_cli("emulator", input=messages)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [decode_message(line+b"\n") for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        self.assertEqual(responses[2]["result"]["settings"]["zoom"], 3)
        self.assertEqual([response["id"] for response in responses], ["0", "1", "2"])

    def test_emulator_rejects_malformed_input_without_hanging(self):
        result = self.run_cli("emulator", input=b"x"*16_500)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")

    def test_diagnostics_has_no_invented_readings(self):
        result = self.run_cli("diagnostics")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIsNone(report["battery"]["percent"])
        self.assertEqual(report["diagnostics"]["frames_processed"], 0)
        self.assertFalse(report["diagnostics"]["clinical_validation"])

    @unittest.skipIf(os.environ.get("DISPLAY") or sys.platform != "linux", "Only a display-free Linux environment")
    def test_headless_gui_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli("gui", "--data-dir", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"desktop display", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)


class GUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except (ImportError, Exception) as exc:
            raise unittest.SkipTest(f"Desktop Tk display unavailable: {exc}")

    def setUp(self):
        import tkinter as tk
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = tk.Tk()
        self.controller = BionicEyeController()
        self.studio = None

    def tearDown(self):
        if self.studio:
            self.studio.close()
        else:
            self.controller.close()
            self.root.destroy()

    def wait_until(self, condition):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            self.root.update()
            if condition():
                return
            time.sleep(.01)
        self.fail("Desktop state did not reach the expected condition within five seconds.")

    def start(self, **kwargs):
        from bionic_eye.gui import VisionStudio
        self.studio = VisionStudio(self.root, self.controller, self.directory.name, **kwargs)

    def test_gui_capture_controls_halt_and_reset(self):
        self.start()
        self.wait_until(lambda: not self.studio._source_pending)
        self.studio._set("low_light", True)
        self.wait_until(lambda: self.controller._latest is not None)
        self.studio._action("capture")
        self.assertEqual(len(list(Path(self.directory.name).glob("captures/*.png"))), 1)
        self.studio._action("stop")
        self.assertTrue(self.controller.system_diagnostics()["halted"])
        self.studio._action("reset")
        self.assertFalse(self.controller.settings.low_light)
        self.wait_until(lambda: self.controller._latest is not None)
        # Layout must remain usable at the documented minimum window size.
        self.root.geometry("1040x800")
        self.root.update()
        self.assertLessEqual(self.studio._sidebar.winfo_y()+self.studio._sidebar.winfo_height(), self.root.winfo_height())

    def test_initial_source_failure_can_recover(self):
        from bionic_eye.sources import DemoSource

        def unavailable():
            raise OSError("Unavailable test camera")

        self.start(source_factory=unavailable)
        self.wait_until(lambda: "Unavailable test camera" in self.studio.status.get())
        self.studio._switch(DemoSource)
        self.studio._action("reset")
        self.wait_until(lambda: not self.studio._source_pending)
        self.assertGreater(self.controller.system_diagnostics()["frames_processed"], 0)

    def test_optional_model_failure_keeps_viewer_usable(self):
        self.start(hand_model="/nonexistent/hand.task", voice_model="/nonexistent/voice")
        self.wait_until(lambda: not self.studio._source_pending)
        self.assertFalse(self.controller.system_diagnostics()["halted"])
