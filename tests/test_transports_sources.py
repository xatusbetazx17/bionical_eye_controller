import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from bionic_eye import BionicEyeController, BionicEyeError, DeviceError, ProtocolError
from bionic_eye.protocol import ReferenceDevice
from bionic_eye.sources import CameraSource, DemoSource, ImageSource
from bionic_eye.transports import SerialTransport, USBTransport
from bionic_eye.vision import demo_frame


class FakeSerial:
    def __init__(self, **kwargs):
        self.closed = False
        self.device = ReferenceDevice()
        self.short_write = False
        self.truncate = False

    def open(self):
        pass

    def write(self, raw):
        self.reply = self.device.handle(raw)
        return 1 if self.short_write else len(raw)

    def read_until(self, delimiter, size):
        return self.reply[:-1] if self.truncate else self.reply

    def close(self):
        self.closed = True


class SerialTests(unittest.TestCase):
    def setUp(self):
        module = types.ModuleType("serial")
        module.Serial = FakeSerial
        self.patcher = patch.dict(sys.modules, {"serial": module})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_acknowledged_serial_byte_exchange(self):
        transport = SerialTransport("COM3")
        stream = transport._stream
        with BionicEyeController(transport=transport) as controller:
            controller.configure(zoom=4)
            self.assertEqual(controller.system_diagnostics()["device"]["settings"]["zoom"], 4)
        self.assertTrue(stream.closed)

    def test_partial_write_and_missing_newline_close_transport(self):
        for attribute in ("short_write", "truncate"):
            with self.subTest(attribute=attribute):
                transport = SerialTransport("COM3")
                controller = BionicEyeController(transport=transport)
                setattr(transport._stream, attribute, True)
                with self.assertRaises(DeviceError):
                    controller.configure(zoom=2)
                self.assertTrue(transport._stream.closed)
                controller.close()

    def test_no_remote_urls_or_unbounded_timeouts(self):
        for port, timeout in (("socket://host:1", 1), ("", 1), ("COM3", 0), ("COM3", float("nan"))):
            with self.subTest(port=port, timeout=timeout), self.assertRaises(ValueError):
                SerialTransport(port, timeout=timeout)


class FakeUSB:
    def __init__(self):
        self.device = ReferenceDevice()
        self.short_write = False

    def get_active_configuration(self):
        endpoints = [types.SimpleNamespace(bEndpointAddress=address, bmAttributes=2, wMaxPacketSize=64)
                     for address in (1, 129)]
        return {(0, 0): endpoints}

    def write(self, endpoint, raw, timeout):
        self.reply = self.device.handle(raw)
        return 1 if self.short_write else len(raw)

    def read(self, endpoint, size, timeout):
        result, self.reply = self.reply[:size], self.reply[size:]
        return result


class USBTests(unittest.TestCase):
    def setUp(self):
        package, core, util = [types.ModuleType(name) for name in ("usb", "usb.core", "usb.util")]
        self.device = FakeUSB()
        self.events = []
        core.find = lambda **kwargs: self.device
        util.claim_interface = lambda *args: self.events.append("claim")
        util.release_interface = lambda *args: self.events.append("release")
        util.dispose_resources = lambda *args: self.events.append("dispose")
        package.core, package.util = core, util
        self.patcher = patch.dict(sys.modules, {"usb": package, "usb.core": core, "usb.util": util})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_real_byte_writes_and_fragmented_reads(self):
        with BionicEyeController(transport=USBTransport(1, 2, 1, 129)) as controller:
            controller.configure(edges=True)
            self.assertTrue(controller.system_diagnostics()["device"]["settings"]["edges"])
        self.assertEqual(self.events, ["claim", "release", "dispose"])

    def test_missing_endpoint_rejected_and_resources_disposed(self):
        with self.assertRaises(DeviceError):
            USBTransport(1, 2, 2, 129)
        self.assertEqual(self.events, ["dispose"])

    def test_partial_write_closes_resources(self):
        transport = USBTransport(1, 2, 1, 129)
        with BionicEyeController(transport=transport) as controller:
            self.device.short_write = True
            with self.assertRaises(DeviceError):
                controller.configure(edges=True)
        self.assertEqual(self.events, ["claim", "release", "dispose"])

    def test_oversized_reply_rejected(self):
        transport = USBTransport(1, 2, 1, 129)
        self.device.write = lambda endpoint, raw, timeout: len(raw)
        self.device.reply = b"x"*16_500
        with self.assertRaises(ProtocolError):
            transport.exchange(b"test\n")
        self.assertIn("dispose", self.events)


class SourceTests(unittest.TestCase):
    def test_demo_moves_and_local_image_is_copied(self):
        source = DemoSource()
        self.assertNotEqual(source.read().tobytes(), source.read().tobytes())
        source.close()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.png"
            demo_frame().save(path)
            source = ImageSource(path)
            frame = source.read()
            frame.putpixel((0, 0), (255, 0, 0))
            self.assertNotEqual(frame.getpixel((0, 0)), source.read().getpixel((0, 0)))
            source.close()

    def test_camera_failure_releases_resources(self):
        events = []
        module = types.ModuleType("cv2")
        capture = types.SimpleNamespace(isOpened=lambda: False, release=lambda: events.append("release"))
        module.VideoCapture = lambda source: capture
        with patch.dict(sys.modules, {"cv2": module}), self.assertRaises(BionicEyeError):
            CameraSource(0)
        self.assertEqual(events, ["release"])

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "Optional OpenCV package is not installed")
    def test_video_file_processing_and_end_of_stream(self):
        import cv2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
            self.assertTrue(writer.isOpened())
            for _ in range(3):
                writer.write(np.full((48, 64, 3), (10, 40, 200), np.uint8))
            writer.release()
            source = CameraSource(path)
            try:
                for _ in range(3):
                    image = source.read()
                    self.assertGreater(image.getpixel((16, 16))[0], 150)  # BGR converted to RGB.
                with self.assertRaises(BionicEyeError):
                    source.read()
            finally:
                source.close()


@unittest.skipUnless(os.name == "posix" and importlib.util.find_spec("serial"), "POSIX and optional pyserial required")
class SerialIntegrationTests(unittest.TestCase):
    def test_os_pseudoterminal_roundtrip(self):
        import pty
        import select
        import threading
        import tty
        master, slave = pty.openpty()
        tty.setraw(slave)
        stop = threading.Event()
        device = ReferenceDevice()

        def serve():
            buffer = b""
            while not stop.is_set():
                if not select.select([master], [], [], .05)[0]:
                    continue
                buffer += os.read(master, 4096)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    os.write(master, device.handle(line+b"\n"))

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with BionicEyeController(transport=SerialTransport(os.ttyname(slave))) as controller:
                controller.configure(zoom=2, overlay="serial roundtrip")
                self.assertEqual(controller.system_diagnostics()["device"]["settings"]["zoom"], 2)
        finally:
            stop.set()
            thread.join(timeout=1)
            os.close(master)
            os.close(slave)
