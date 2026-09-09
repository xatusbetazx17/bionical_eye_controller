"""Local image sources with explicit failure reporting and resource cleanup."""

from pathlib import Path
from .errors import BionicEyeError, UnsupportedFeature
from .vision import demo_frame, load_image, rgb_image


class DemoSource:
    name = "Synthetic demonstration"

    def __init__(self):
        self._index = 0

    def read(self):
        frame = demo_frame(self._index)
        self._index += 1
        return frame

    def close(self):
        pass


class ImageSource:
    name = "Local image"

    def __init__(self, path):
        self._image = load_image(path)

    def read(self):
        return self._image.copy()

    def close(self):
        self._image.close()


class CameraSource:
    def __init__(self, source=0):
        if type(source) is int:
            if source < 0:
                raise ValueError("Camera index must be non-negative.")
            self.name = f"Camera {source}"
        else:
            source = str(Path(source))
            if not Path(source).is_file():
                raise ValueError("Video input must be an existing local file.")
            self.name = "Local video"
        try:
            import cv2
        except ImportError as exc:
            raise UnsupportedFeature("Install camera support first: python -m pip install '.[camera]'") from exc
        self._cv2 = cv2
        self._capture = cv2.VideoCapture(source)
        if not self._capture.isOpened():
            self.close()
            raise BionicEyeError("Camera/video could not be opened. Check permissions and the selected source.")
        if type(source) is int:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self):
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise BionicEyeError("Camera frame unavailable or end of video reached; source stopped.")
        return rgb_image(self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB))

    def close(self):
        self._capture.release()
