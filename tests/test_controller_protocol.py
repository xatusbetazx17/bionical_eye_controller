from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from bionic_eye import (BionicEyeController, BionicEyeError, DeviceError, HaltedError,
                        ProtocolError, UnsupportedFeature, ViewSettings)
from bionic_eye.audit import AuditLog
from bionic_eye.protocol import (DeviceClient, ReferenceDevice, decode_message, encode_message)
from bionic_eye.transports import SimulatorTransport
from bionic_eye.vision import demo_frame


class FaultTransport(SimulatorTransport):
    fault = None

    def exchange(self, raw):
        response = super().exchange(raw)
        if self.fault == "disconnect":
            raise DeviceError("Disconnected after request; acknowledgment lost.")
        message = decode_message(response)
        if self.fault == "id":
            message["id"] = "wrong"
        elif self.fault == "settings" and "settings" in message.get("result", {}):
            message["result"]["settings"]["zoom"] = 7
        elif self.fault == "real":
            message["result"]["simulation"] = False
        elif self.fault == "battery":
            message["result"].update(percent=85, source="made-up")
        return encode_message(message)


class ProtocolTests(unittest.TestCase):
    def test_stateful_request_and_duplicate_idempotency(self):
        device = ReferenceDevice()
        raw = encode_message(dict(protocol=1, id="test", operation="view.configure", params={"zoom": 2}))
        first = device.handle(raw)
        self.assertEqual(first, device.handle(raw))
        self.assertEqual(device.revision, 1)
        self.assertEqual(decode_message(first)["result"]["settings"]["zoom"], 2)

    def test_reusing_id_with_different_payload_rejected(self):
        device = ReferenceDevice()
        request = dict(protocol=1, id="test", operation="view.configure", params={"zoom": 2})
        device.handle(encode_message(request))
        request["params"]["zoom"] = 3
        with self.assertRaises(ProtocolError):
            device.handle(encode_message(request))
        self.assertEqual(device.settings.zoom, 2)

    def test_bad_envelopes_rejected(self):
        for raw in (b"{}", b"[]\n", b"\xff\n", b"{}\n{}\n", b'{"x":NaN}\n',
                    b'{"x":1,"x":2}\n', b"x"*16_385+b"\n", b"["*1100+b"\n"):
            with self.subTest(raw=raw[:40]), self.assertRaises(ProtocolError):
                decode_message(raw)
        for version in (True, 2, "1"):
            with self.subTest(version=version), self.assertRaises(ProtocolError):
                ReferenceDevice().handle(encode_message(dict(protocol=version, id="x", operation="hello", params={})))

    def test_invalid_setting_does_not_mutate_emulator(self):
        client = DeviceClient(SimulatorTransport())
        with self.assertRaises(DeviceError):
            client.request("view.configure", {"zoom": -1})
        self.assertEqual(client.request("diagnostics")["settings"]["zoom"], 1)
        client.close()

    def test_unknown_operation_and_halt(self):
        client = DeviceClient(SimulatorTransport())
        with self.assertRaises(UnsupportedFeature):
            client.request("neural_stimulation")
        client.request("halt")
        with self.assertRaises(DeviceError):
            client.request("view.configure", {"zoom": 2})
        client.request("reset")
        self.assertEqual(client.request("view.configure", {"zoom": 2})["settings"]["zoom"], 2)
        client.close()

    def test_non_simulator_handshake_rejected_and_closed(self):
        transport = FaultTransport()
        transport.fault = "real"
        with self.assertRaises(ProtocolError):
            DeviceClient(transport)
        self.assertTrue(transport.closed)

    def test_idempotency_cache_is_bounded(self):
        device = ReferenceDevice()
        for i in range(200):
            device.handle(encode_message(dict(protocol=1, id=str(i), operation="diagnostics", params={})))
        self.assertEqual(len(device._cache), 128)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.transport = FaultTransport()
        self.controller = BionicEyeController(transport=self.transport)
        self.addCleanup(self.controller.close)

    def test_local_state_changes_only_after_exact_ack(self):
        self.transport.fault = "settings"
        with self.assertRaises(ProtocolError):
            self.controller.configure(zoom=2)
        self.assertEqual(self.controller.settings.zoom, 1)
        with self.assertRaises(HaltedError):
            self.controller.process_frame(demo_frame())

    def test_lost_or_mismatched_ack_latches_halt(self):
        for fault in ("disconnect", "id", "real"):
            with self.subTest(fault=fault):
                transport = FaultTransport()
                controller = BionicEyeController(transport=transport)
                try:
                    transport.fault = fault
                    with self.assertRaises(DeviceError):
                        controller.configure(zoom=2)
                    with self.assertRaises(HaltedError):
                        controller.process_frame(demo_frame())
                    self.assertEqual(controller.settings.zoom, 1)
                    self.assertFalse(controller.halt()["physical_device_stop_confirmed"])
                finally:
                    controller.close()

    def test_invalid_input_does_not_change_settings(self):
        with self.assertRaises(ValueError):
            self.controller.configure(zoom=float("nan"))
        self.assertEqual(self.controller.settings, ViewSettings())
        self.controller.process_frame(demo_frame())

    def test_capture_writes_real_pixels_and_prevents_overwrite(self):
        expected = self.controller.process_frame(demo_frame())
        with tempfile.TemporaryDirectory() as directory:
            path = self.controller.capture_photo(Path(directory)/"actual.png")
            with Image.open(path) as actual:
                self.assertEqual(actual.tobytes(), expected.tobytes())
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                self.controller.capture_photo(path)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_stale_and_invalid_capture_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"photo.png"
            with self.assertRaises(BionicEyeError):
                self.controller.capture_photo(path)
            self.controller.process_frame(demo_frame())
            with patch("bionic_eye.controller.time.monotonic", return_value=self.controller._latest_time+3):
                with self.assertRaises(BionicEyeError):
                    self.controller.capture_photo(path)
            with self.assertRaises(ValueError):
                self.controller.capture_photo(path.with_suffix(".jpg"))
            self.assertFalse(path.exists())

    def test_halt_reset_and_closed_state(self):
        self.controller.configure(zoom=3, edges=True)
        self.controller.halt()
        with self.assertRaises(HaltedError):
            self.controller.configure(zoom=2)
        self.controller.reset()
        self.assertEqual(self.controller.settings, ViewSettings())
        self.controller.process_frame(demo_frame())
        self.controller.close()
        self.controller.close()
        self.assertTrue(self.controller.system_diagnostics()["closed"])
        with self.assertRaises(HaltedError):
            self.controller.reset()

    def test_failed_frame_cannot_be_captured(self):
        self.controller.process_frame(demo_frame())
        with self.assertRaises(ValueError):
            self.controller.process_frame(None)
        with self.assertRaises(HaltedError):
            self.controller.capture_photo("should-not-exist.png")
        self.assertEqual(self.controller.system_diagnostics()["frames_processed"], 1)

    def test_unsupported_features_never_report_success(self):
        for action in (self.controller.enable_infrared, self.controller.update_firmware,
                       self.controller.ai_enhance_vision,
                       lambda: self.controller.run_custom_function("print('not executed')")):
            with self.subTest(action=action), self.assertRaises(UnsupportedFeature):
                action()
        self.assertIsNone(self.controller.check_battery()["percent"])

    def test_custom_processor_runs_and_is_cleared_by_reset(self):
        self.controller.register_processor("blank", lambda image: Image.new("RGB", image.size))
        self.controller.ai_enhance_vision("blank")
        self.assertIsNone(self.controller.process_frame(demo_frame()).getbbox())
        self.controller.reset()
        self.assertIsNotNone(self.controller.process_frame(demo_frame()).getbbox())

    def test_custom_processor_shape_failure_halts(self):
        self.controller.register_processor("bad", lambda image: Image.new("RGB", (1, 1)))
        self.controller.run_custom_function("bad")
        with self.assertRaises(ValueError):
            self.controller.process_frame(demo_frame())
        self.assertTrue(self.controller.system_diagnostics()["halted"])

    def test_concurrent_calls_preserve_acknowledged_state(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda zoom: self.controller.configure(zoom=zoom), [1, 2, 3, 4]*8))
        state = self.controller.system_diagnostics()
        self.assertEqual(state["settings"], state["device"]["settings"])


class AuditTests(unittest.TestCase):
    def test_persistence_bounded_retention_and_parameterized_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"audit.sqlite3"
            with AuditLog(path) as log:
                for i in range(1010):
                    log.record("test", "ok", {"i": i})
                log.record("'; DROP TABLE events; --", "ok")
                self.assertEqual(len(log.recent(1000)), 1000)
            with AuditLog(path) as log:
                self.assertEqual(log.recent(1)[0]["operation"], "'; DROP TABLE events; --")
                with self.assertRaises(ValueError):
                    log.recent(1001)

    def test_no_overlay_or_images_in_controller_audit(self):
        with BionicEyeController() as controller:
            controller.configure(overlay="private scene text")
            controller.process_frame(demo_frame())
            self.assertNotIn("private scene text", json.dumps(controller.history()))
