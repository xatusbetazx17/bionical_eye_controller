"""Versioned, bounded request/acknowledgment protocol for bench emulators."""

from collections import OrderedDict
import json
import threading
import uuid

from .config import ViewSettings
from .errors import DeviceError, ProtocolError, UnsupportedFeature

VERSION = 1
MAX_MESSAGE_BYTES = 16_384
CAPABILITIES = ("view.configure", "diagnostics", "battery", "halt", "reset")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite number {value} is not allowed.")


def encode_message(message):
    try:
        raw = (json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ProtocolError("Message is not valid JSON.") from exc
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Message exceeds 16 KiB.")
    return raw


def decode_message(raw):
    if not isinstance(raw, bytes) or not raw.endswith(b"\n") or len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Expected one complete newline-terminated message of at most 16 KiB.")
    try:
        result = json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("Message is not valid, unambiguous UTF-8 JSON.") from exc
    if not isinstance(result, dict):
        raise ProtocolError("Message must be an object.")
    return result


class ReferenceDevice:
    """Stateful display emulator. No physical device or stimulation commands exist."""

    def __init__(self):
        self.settings = ViewSettings()
        self.halted = False
        self.revision = 0
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def handle(self, raw):
        with self._lock:
            return self._handle(raw)

    def _handle(self, raw):
        request = decode_message(raw)
        if (set(request) != {"protocol", "id", "operation", "params"}
                or type(request["protocol"]) is not int or request["protocol"] != VERSION
                or not isinstance(request["id"], str) or not 1 <= len(request["id"]) <= 64
                or not isinstance(request["operation"], str) or not isinstance(request["params"], dict)):
            raise ProtocolError("Invalid v1 request envelope.")
        identity = request["id"]
        canonical = encode_message(request)
        if identity in self._cache:
            original, response = self._cache[identity]
            if canonical != original:
                raise ProtocolError("Request id reused with different content.")
            return response
        try:
            result = self._execute(request["operation"], request["params"])
            reply = dict(protocol=VERSION, id=identity, ok=True, result=result)
        except (ValueError, UnsupportedFeature, DeviceError) as exc:
            reply = dict(protocol=VERSION, id=identity, ok=False,
                         error={"code": "unsupported" if isinstance(exc, UnsupportedFeature) else "rejected",
                                "message": str(exc)})
        response = encode_message(reply)
        self._cache[identity] = (canonical, response)
        if len(self._cache) > 128:
            self._cache.popitem(last=False)
        return response

    def _execute(self, operation, params):
        if operation != "view.configure" and params:
            raise ValueError("This operation takes no parameters.")
        if operation == "hello":
            return {"device_id": "bionic-eye-reference", "device_type": "bench-emulator",
                    "simulation": True, "capabilities": list(CAPABILITIES)}
        if operation == "diagnostics":
            return {"simulation": True, "halted": self.halted, "revision": self.revision,
                    "settings": self.settings.to_dict(), "physical_device_tested": False}
        if operation == "battery":
            return {"percent": None, "source": "unavailable", "simulation": True}
        if operation == "halt":
            self.halted = True
            return {"halted": True, "simulation": True}
        if operation == "reset":
            self.halted = False
            self.settings = ViewSettings()
            self.revision += 1
            return {"halted": False, "settings": self.settings.to_dict(), "simulation": True}
        if operation == "view.configure":
            if self.halted:
                raise DeviceError("Emulator halted; reset is required.")
            settings = ViewSettings.from_dict(params)
            self.settings = settings
            self.revision += 1
            return {"settings": settings.to_dict(), "revision": self.revision, "simulation": True}
        raise UnsupportedFeature(f"Unsupported operation: {operation}")


class DeviceClient:
    def __init__(self, transport):
        self.transport = transport
        self._lock = threading.Lock()
        try:
            self.identity = self.request("hello")
            capabilities = self.identity.get("capabilities")
            if (self.identity.get("simulation") is not True
                    or self.identity.get("device_type") != "bench-emulator"
                    or not isinstance(capabilities, list)
                    or not all(isinstance(item, str) for item in capabilities)
                    or not set(CAPABILITIES).issubset(capabilities)):
                raise ProtocolError("Peer is not a compatible v1 bench emulator.")
        except Exception:
            transport.close()
            raise

    def request(self, operation, params=None):
        with self._lock:
            identity = uuid.uuid4().hex
            request = dict(protocol=VERSION, id=identity, operation=operation, params=params or {})
            try:
                raw = self.transport.exchange(encode_message(request))
            except DeviceError:
                raise
            except Exception as exc:
                raise DeviceError(f"Transport exchange failed: {exc}") from exc
            response = decode_message(raw)
            if (type(response.get("protocol")) is not int or response["protocol"] != VERSION
                    or response.get("id") != identity or type(response.get("ok")) is not bool):
                raise ProtocolError("Reply version, id, or acknowledgment is invalid.")
            if not response["ok"]:
                error = response.get("error")
                if (set(response) != {"protocol", "id", "ok", "error"}
                        or not isinstance(error, dict) or not isinstance(error.get("message"), str)):
                    raise ProtocolError("Malformed error response.")
                cls = UnsupportedFeature if error.get("code") == "unsupported" else DeviceError
                raise cls(error["message"])
            if set(response) != {"protocol", "id", "ok", "result"} or not isinstance(response["result"], dict):
                raise ProtocolError("Malformed success response.")
            return response["result"]

    def close(self):
        self.transport.close()
