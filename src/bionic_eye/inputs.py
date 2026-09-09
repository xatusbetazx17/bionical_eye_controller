"""Optional, explicitly enabled local voice and hand controls."""

import json
import math
from pathlib import Path
import queue
import threading

import numpy as np

from .errors import UnsupportedFeature


def parse_voice(text):
    """Require the whole phrase and wake word; never interpret arbitrary speech/code."""
    normalized = " ".join(text.lower().split())
    commands = {
        "eye stop": ("stop", None), "eye reset": ("reset", None),
        "eye capture": ("capture", None), "eye zoom in": ("zoom_in", None),
        "eye zoom out": ("zoom_out", None),
        "eye night on": ("low_light", True), "eye night off": ("low_light", False),
        "eye contrast on": ("auto_contrast", True), "eye contrast off": ("auto_contrast", False),
        "eye edges on": ("edges", True), "eye edges off": ("edges", False),
        "eye enhance on": ("enhance", True), "eye enhance off": ("enhance", False),
        "eye preview on": ("phosphene", True), "eye preview off": ("phosphene", False),
    }
    return commands.get(normalized)


class DwellSelector:
    """Trigger once per continuous visit, reset on tracking loss or leaving a target."""
    def __init__(self, seconds=1.2):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Dwell time must be a positive finite number.")
        self.seconds = seconds
        self.target = None
        self.started = None
        self.fired = False

    def update(self, target, now):
        if not math.isfinite(now):
            raise ValueError("Dwell timestamp must be finite.")
        if target is None or target != self.target or (self.started is not None and now < self.started):
            self.target, self.started, self.fired = target, now, False
            return None
        if not self.fired and now - self.started >= self.seconds:
            self.fired = True
            return target
        return None

    def progress(self, now):
        if self.target is None or self.started is None:
            return 0.0
        return min(1.0, max(0.0, (now - self.started) / self.seconds))


class HandPointer:
    """MediaPipe Tasks API with a user-supplied Hand Landmarker model."""
    def __init__(self, model_path):
        if not Path(model_path).is_file():
            raise ValueError("Provide a local MediaPipe Hand Landmarker .task model.")
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise UnsupportedFeature("Install the hands extra before enabling hand control.") from exc
        self._mp = mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=1)
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._timestamp = -1

    def locate(self, image, timestamp_ms):
        self._timestamp = max(self._timestamp + 1, int(timestamp_ms))
        # Mirrored input makes movement behave like a mirror for menu selection.
        pixels = np.ascontiguousarray(np.asarray(image.convert("RGB"))[:, ::-1])
        result = self._landmarker.detect_for_video(
            self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=pixels), self._timestamp)
        if not result.hand_landmarks:
            return None
        finger = result.hand_landmarks[0][8]
        if not (math.isfinite(finger.x) and math.isfinite(finger.y)):
            return None
        return max(0.0, min(1.0, finger.x)), max(0.0, min(1.0, finger.y))

    def close(self):
        self._landmarker.close()


class VoiceListener:
    """Vosk recognition uses a local model. Audio never goes to a web service."""
    def __init__(self, model_path, on_command, on_error):
        if not Path(model_path).is_dir():
            raise ValueError("Provide a local Vosk model directory.")
        try:
            import vosk
            import sounddevice
        except ImportError as exc:
            raise UnsupportedFeature("Install the voice extra and system PortAudio before enabling voice control.") from exc
        self._recognizer = vosk.KaldiRecognizer(vosk.Model(str(model_path)), 16000)
        self._sounddevice = sounddevice
        self._on_command, self._on_error = on_command, on_error
        self._stop = threading.Event()
        self._audio = queue.Queue(maxsize=8)
        self._thread = None
        self._overflow = threading.Event()

    def _callback(self, data, frames, timing, status):
        if status:
            self._overflow.set()
            return
        try:
            self._audio.put_nowait(bytes(data))
        except queue.Full:
            self._overflow.set()

    def start(self):
        if self._thread is not None:
            raise ValueError("Voice listener is already started.")
        self._thread = threading.Thread(target=self._run, name="bionic-eye-voice", daemon=True)
        self._thread.start()

    def _run(self):
        try:
            with self._sounddevice.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16",
                                                  channels=1, callback=self._callback):
                while not self._stop.is_set():
                    if self._overflow.is_set():
                        raise RuntimeError("Microphone buffer overflow; voice control stopped.")
                    try:
                        data = self._audio.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if self._recognizer.AcceptWaveform(data):
                        command = parse_voice(json.loads(self._recognizer.Result()).get("text", ""))
                        if command is not None and not self._stop.is_set():
                            self._on_command(command)
        except Exception as exc:
            if not self._stop.is_set():
                self._on_error(str(exc))

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
