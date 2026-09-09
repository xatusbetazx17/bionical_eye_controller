# Reference bench protocol v1

This protocol belongs to the included emulator. It is not a protocol for any implant. Only display settings and emulator state are represented; no stimulation or firmware-flashing operation exists.

## Framing

One UTF-8 JSON object per newline-terminated message. Maximum: **16,384 bytes including the newline**. Duplicate keys, NaN/Infinity, invalid UTF-8, incorrect envelopes and concatenated responses are rejected. Clients generate UUID request IDs and never retry uncertain writes automatically.

Request:

```json
{"protocol":1,"id":"example-1","operation":"view.configure","params":{"zoom":2}}
```

Reply:

```json
{"protocol":1,"id":"example-1","ok":true,"result":{"settings":{"zoom":2,"low_light":false,"auto_contrast":false,"enhance":false,"edges":false,"segmentation":false,"phosphene":false,"overlay":"","iris_color":"#40C9B0","appearance":"Default"},"revision":1,"simulation":true}}
```

Error:

```json
{"protocol":1,"id":"example-2","ok":false,"error":{"code":"unsupported","message":"Unsupported operation: infrared"}}
```

IDs are nonempty strings of at most 64 characters. The emulator caches the last 128 IDs and repeats a cached reply for an identical request; reusing an ID with different content fails. This volatile cache is not an exactly-once guarantee.

## Operations

| Operation | Parameters | Result |
| --- | --- | --- |
| `hello` | `{}` | Device ID, `device_type: bench-emulator`, `simulation: true`, capabilities |
| `view.configure` | Validated settings object | Complete settings, revision, simulation status |
| `diagnostics` | `{}` | Actual emulator state; `physical_device_tested: false` |
| `battery` | `{}` | `percent: null`, `source: unavailable`, `simulation: true` |
| `halt` | `{}` | `halted: true`, `simulation: true` |
| `reset` | `{}` | Default settings, `halted: false`, `simulation: true` |

On the wire, configuration replaces all settings and defaults omitted fields. The controller merges changes locally before sending the complete object and checking the acknowledgment. Configuration is rejected while halted; diagnostics and reset remain available.

## Connections

The SDK defaults to an in-memory emulator. For a separate process:

```bash
python -m bionic_eye emulator
```

Send request lines to stdin and read replies from stdout. EOF exits. Invalid framing exits nonzero with an error on stderr. No listener or device is opened.

Inspect an explicitly configured compatible serial bench peer:

```bash
python -m bionic_eye device --transport serial --port /dev/ttyACM0 --timeout 1
```

Windows names such as `COM3` work. Remote serial URL schemes are rejected. Missing/incompatible peers fail without fallback. Opening a serial port can affect control lines on some hardware; select only your isolated bench emulator.

For USB, use `USBTransport(vendor_id, product_id, endpoint_out, endpoint_in, interface=0, timeout=1)` or `device --transport usb` with those explicit flags. Obtain identifiers from your bench specification. The implementation checks bulk endpoints in the existing active configuration, claims only the selected interface, and never detaches kernel drivers or reconfigures devices. Install libusb and OS permissions separately.

USB responses may span packets. Timeouts, oversize responses, partial writes, wrong IDs and invalid acknowledgments are errors. Communication failures halt local processing. A local stop does not prove physical de-energization; independent product fault protection is outside this reference protocol.
