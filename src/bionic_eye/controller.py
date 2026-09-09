"""Reusable controller with acknowledged settings and latched local failures."""

from collections import deque
from pathlib import Path
import threading
import time
import uuid

from .audit import AuditLog
from .config import ViewSettings
from .errors import BionicEyeError, DeviceError, HaltedError, ProtocolError, UnsupportedFeature
from .protocol import DeviceClient
from .transports import SimulatorTransport
from .vision import process, rgb_image


class BionicEyeController:
    def __init__(self, transport=None, settings=None, audit=None):
        self._lock = threading.RLock()
        self._client = DeviceClient(transport if transport is not None else SimulatorTransport())
        self._audit = audit if audit is not None else AuditLog()
        self._owns_audit = audit is None
        self.settings = ViewSettings()
        self._halted = False
        self._fault = None
        self._closed = False
        self._latest = None
        self._latest_time = None
        self._timings = deque(maxlen=120)
        self._frames = 0
        self._processors = {}
        self._active_processor = None
        try:
            self.configure(**(settings or ViewSettings()).to_dict())
        except Exception:
            self.close()
            raise

    def _ready(self):
        if self._closed:
            raise HaltedError("Controller is closed.")
        if self._halted or self._fault:
            raise HaltedError("Processing is stopped. Reset explicitly, or reconnect after a transport failure.")

    def _request(self, operation, params=None):
        try:
            result = self._client.request(operation, params)
            if result.get("simulation") is not True:
                raise ProtocolError("Peer omitted the required simulation status.")
            return result
        except DeviceError as exc:
            self._fault = type(exc).__name__
            self._halted = True
            self._latest = None
            self._audit.record(operation, "failed", {"error_type": type(exc).__name__})
            raise

    def configure(self, **changes):
        with self._lock:
            self._ready()
            proposed = self.settings.updated(**changes)
            result = self._request("view.configure", proposed.to_dict())
            if result.get("settings") != proposed.to_dict():
                self._fault, self._halted, self._latest = "settings_ack_mismatch", True, None
                self._audit.record("view.configure", "failed", {"error_type": self._fault})
                raise ProtocolError("Device did not acknowledge the exact requested settings.")
            self.settings = proposed
            self._latest = None
            self._audit.record("view.configure", "acknowledged", {"fields": sorted(changes)})
            return self.settings

    def process_frame(self, frame):
        with self._lock:
            self._ready()
            started = time.perf_counter()
            try:
                output = process(frame, self.settings)
                if self._active_processor is not None:
                    expected = output.size
                    output = rgb_image(self._processors[self._active_processor](output.copy()))
                    if output.size != expected:
                        raise ValueError("Custom processor must preserve image dimensions.")
                self._latest = output.copy()
                self._latest_time = time.monotonic()
                self._frames += 1
                self._timings.append((time.perf_counter() - started) * 1000)
                return output
            except Exception as exc:
                self._latest = None
                self._fault, self._halted = "frame_processing_failed", True
                self._audit.record("process_frame", "failed", {"error_type": type(exc).__name__})
                raise

    def capture_photo(self, path):
        with self._lock:
            self._ready()
            if self._latest is None or time.monotonic() - self._latest_time > 2:
                raise BionicEyeError("No fresh processed frame is available; capture a frame first.")
            path = Path(path)
            if path.suffix.lower() != ".png":
                raise ValueError("Photo output must use the .png extension.")
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation never overwrites an existing photograph.
            with path.open("xb") as output:
                try:
                    self._latest.save(output, format="PNG")
                except Exception:
                    output.close()
                    path.unlink(missing_ok=True)
                    raise
            self._audit.record("capture_photo", "saved")
            return path

    def capture_to_directory(self, directory):
        return self.capture_photo(Path(directory) / f"capture-{time.time_ns()}-{uuid.uuid4().hex[:8]}.png")

    def halt(self):
        with self._lock:
            self._halted, self._latest = True, None
            acknowledged = False
            if not self._closed:
                try:
                    acknowledged = self._request("halt").get("halted") is True
                except (DeviceError, UnsupportedFeature):
                    pass
                self._audit.record("halt", "local_stopped", {"emulator_acknowledged": acknowledged})
            return {"local_stopped": True, "emulator_acknowledged": acknowledged,
                    "physical_device_stop_confirmed": False}

    def reset(self):
        with self._lock:
            if self._closed:
                raise HaltedError("A closed controller must be recreated.")
            response = self._request("reset")
            defaults = ViewSettings()
            if response.get("halted") is not False or response.get("settings") != defaults.to_dict():
                self._fault, self._halted, self._latest = "reset_ack_mismatch", True, None
                raise ProtocolError("Reset acknowledgment does not contain default settings.")
            self.settings = defaults
            self._fault, self._halted, self._latest = None, False, None
            self._active_processor = None
            self._audit.record("reset", "acknowledged")

    def system_diagnostics(self):
        with self._lock:
            peer, error = None, None
            if not self._closed:
                try:
                    peer = self._request("diagnostics")
                except (DeviceError, UnsupportedFeature) as exc:
                    error = str(exc)
            timings = sorted(self._timings)
            return {"mode": "software-research", "simulation": True, "closed": self._closed,
                    "halted": self._halted, "fault": self._fault, "frames_processed": self._frames,
                    "latency_ms_mean": sum(timings)/len(timings) if timings else None,
                    "latency_ms_p95": timings[min(len(timings)-1, int(len(timings)*.95))] if timings else None,
                    "settings": self.settings.to_dict(), "processor": self._active_processor,
                    "device": peer, "device_error": error, "clinical_validation": False}

    def check_battery(self):
        with self._lock:
            if self._closed:
                raise HaltedError("Controller is closed.")
            result = self._request("battery")
            if result.get("percent") is not None or result.get("source") != "unavailable":
                raise ProtocolError("Reference emulator cannot report physical battery telemetry.")
            return result

    def history(self, limit=20):
        return self._audit.recent(limit)

    def register_processor(self, name, processor):
        """Register trusted Python code explicitly; no code strings or dynamic imports."""
        if not isinstance(name, str) or not name.isidentifier() or not callable(processor):
            raise ValueError("A processor needs an identifier and a callable(image) -> image.")
        with self._lock:
            self._ready()
            if name in self._processors:
                raise ValueError("Processor name already registered.")
            self._processors[name] = processor

    def run_custom_function(self, name):
        with self._lock:
            self._ready()
            if name not in self._processors:
                raise UnsupportedFeature("Register a trusted image processor by name first. Code strings are never executed.")
            self._active_processor = name
            self._latest = None
            self._audit.record("processor.select", "selected", {"name": name})

    def change_iris_color(self, color):
        return self.configure(iris_color=color)

    def set_zoom_level(self, level):
        return self.configure(zoom=level)

    def enable_night_vision(self, enable=True):
        """Compatibility name for digital low-light enhancement; no night sensor."""
        return self.configure(low_light=enable)

    def activate_AR_overlay(self, overlay_data):
        """Two-dimensional text overlay; no world tracking or optical projection."""
        return self.configure(overlay=overlay_data)

    def set_eye_appearance(self, appearance):
        return self.configure(appearance=appearance)

    def auto_contrast(self, enable=True):
        return self.configure(auto_contrast=enable)

    def scene_segmentation(self, enable=True):
        """Brightness segmentation only, not semantic recognition or navigation."""
        return self.configure(segmentation=enable)

    def ai_enhance_vision(self, processor_name=None):
        if processor_name is None:
            raise UnsupportedFeature("No AI model is bundled. Register and select a validated image processor explicitly.")
        return self.run_custom_function(processor_name)

    def enable_infrared(self, enable=True):
        raise UnsupportedFeature("Infrared requires a suitable sensor and its documented driver; RGB images cannot supply it.")

    def update_firmware(self, update_method="online"):
        raise UnsupportedFeature("No vendor updater is supplied. Use firmware-verify for offline package verification; it never flashes a device.")

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                self.halt()
            finally:
                self._closed, self._latest = True, None
                try:
                    self._client.close()
                finally:
                    if self._owns_audit:
                        self._audit.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
