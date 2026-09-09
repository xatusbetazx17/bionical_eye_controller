"""Explicit bench connections. No device scans, automatic fallback, or retries."""

import math
import time
from typing import Protocol

from .errors import DeviceError, ProtocolError, UnsupportedFeature
from .protocol import MAX_MESSAGE_BYTES, ReferenceDevice


class Transport(Protocol):
    def exchange(self, request: bytes) -> bytes: ...
    def close(self) -> None: ...


def _timeout(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 30:
        raise ValueError("Timeout must be a finite number greater than 0 and at most 30 seconds.")
    return float(value)


class SimulatorTransport:
    def __init__(self, device=None):
        self.device = device or ReferenceDevice()
        self.closed = False

    def exchange(self, request):
        if self.closed:
            raise DeviceError("Simulator connection is closed.")
        return self.device.handle(request)

    def close(self):
        self.closed = True


class SerialTransport:
    """Newline-delimited JSON over an explicitly selected serial bench port."""

    def __init__(self, port, baudrate=115200, timeout=1.0):
        timeout = _timeout(timeout)
        if not isinstance(port, str) or not port or "://" in port:
            raise ValueError("Provide an explicit local serial port, such as COM3 or /dev/ttyACM0.")
        if type(baudrate) is not int or not 1200 <= baudrate <= 4_000_000:
            raise ValueError("Baud rate must be between 1200 and 4000000.")
        try:
            import serial
        except ImportError as exc:
            raise UnsupportedFeature("Install the hardware extra to use serial: pip install '.[hardware]'") from exc
        self._stream = serial.Serial(port=None, baudrate=baudrate, timeout=timeout, write_timeout=timeout)
        try:
            self._stream.port = port
            self._stream.dtr = False
            self._stream.rts = False
            self._stream.open()
        except Exception as exc:
            self._stream.close()
            raise DeviceError(f"Cannot open serial port {port}: {exc}") from exc

    def exchange(self, request):
        try:
            if self._stream.write(request) != len(request):
                raise DeviceError("Incomplete serial write; command outcome is unknown.")
            reply = self._stream.read_until(b"\n", MAX_MESSAGE_BYTES + 1)
            if not reply.endswith(b"\n") or len(reply) > MAX_MESSAGE_BYTES:
                raise ProtocolError("Serial response timed out, was incomplete, or exceeded 16 KiB.")
            return reply
        except Exception as exc:
            self.close()
            if isinstance(exc, DeviceError):
                raise
            raise DeviceError(f"Serial exchange failed: {exc}") from exc

    def close(self):
        self._stream.close()


class USBTransport:
    """Bulk USB bench transport requiring exact device/interface/endpoint identifiers."""

    def __init__(self, vendor_id, product_id, endpoint_out, endpoint_in, interface=0, timeout=1.0):
        self._timeout = _timeout(timeout)
        for name, value in (("vendor_id", vendor_id), ("product_id", product_id)):
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError(f"{name} must be between 1 and 65535.")
        if (type(endpoint_out) is not int or not 1 <= endpoint_out <= 15
                or type(endpoint_in) is not int or not 129 <= endpoint_in <= 143
                or type(interface) is not int or not 0 <= interface <= 255):
            raise ValueError("Specify a bulk OUT endpoint 1..15, IN endpoint 129..143, and interface 0..255.")
        try:
            import usb.core
            import usb.util
        except ImportError as exc:
            raise UnsupportedFeature("Install the hardware extra and the system libusb driver for USB.") from exc
        self._util = usb.util
        self._device = None
        self._claimed = False
        self._interface = interface
        self._out, self._in = endpoint_out, endpoint_in
        try:
            self._device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
            if self._device is None:
                raise DeviceError("The explicitly selected USB bench device was not found.")
            descriptor = self._device.get_active_configuration()[(interface, 0)]
            endpoints = {e.bEndpointAddress: e for e in descriptor}
            for address in (endpoint_out, endpoint_in):
                if address not in endpoints or endpoints[address].bmAttributes & 3 != 2:
                    raise DeviceError("The selected interface does not have those bulk endpoints.")
            self._read_size = max(64, endpoints[endpoint_in].wMaxPacketSize)
            usb.util.claim_interface(self._device, interface)
            self._claimed = True
        except Exception as exc:
            self.close()
            if isinstance(exc, DeviceError):
                raise
            raise DeviceError(f"Cannot open USB bench device: {exc}") from exc

    def exchange(self, request):
        if self._device is None:
            raise DeviceError("USB connection is closed.")
        deadline = time.monotonic() + self._timeout
        try:
            if self._device.write(self._out, request, timeout=max(1, int(self._timeout * 1000))) != len(request):
                raise DeviceError("Incomplete USB write; command outcome is unknown.")
            reply = bytearray()
            while b"\n" not in reply:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DeviceError("USB response timed out; command outcome is unknown.")
                reply.extend(self._device.read(self._in, self._read_size,
                                               timeout=max(1, int(remaining * 1000))))
                if len(reply) > MAX_MESSAGE_BYTES:
                    raise ProtocolError("USB response exceeds 16 KiB.")
            return bytes(reply)
        except Exception as exc:
            self.close()
            if isinstance(exc, DeviceError):
                raise
            raise DeviceError(f"USB exchange failed: {exc}") from exc

    def close(self):
        device, self._device = self._device, None
        if device is not None:
            try:
                if self._claimed:
                    self._util.release_interface(device, self._interface)
            finally:
                self._util.dispose_resources(device)
                self._claimed = False
