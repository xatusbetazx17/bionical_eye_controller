class BionicEyeError(Exception):
    """An expected operation failure that can be shown to the user."""


class UnsupportedFeature(BionicEyeError):
    """No implementation or compatible device is available for this operation."""


class DeviceError(BionicEyeError):
    """A device rejected a request or communication failed."""


class ProtocolError(DeviceError):
    """Malformed, oversized, or mismatched protocol message."""


class HaltedError(BionicEyeError):
    """Processing has stopped; explicit reset is required."""
