# Integration guide

## Reusable components

`bionic_eye` contains image transforms, validated display settings, a stateful emulator, transport interfaces, bounded diagnostic history, optional local inputs, and offline firmware-package verification. `LICENSE` is MIT and retains the original copyright.

Install from a reviewed commit or build a wheel. Record the commit, wheel digest, Python version and resolved dependencies in downstream builds. Version 0.1.0 is an alpha API; pin a reviewed version. Optional packages and separately obtained models have their own licenses and platform requirements.

## Image processing

`ViewSettings` is immutable and validates numeric ranges, booleans, colors, overlays and unknown fields. `BionicEyeController.configure()` checks the emulator acknowledgment before changing local settings. A lock serializes frame and configuration operations.

Use context managers to release resources. The SDK audit log defaults to memory; pass `AuditLog(path)` for persistence and close that supplied log yourself. The latest 1,000 events are retained. Images, overlay contents and audio are not logged. Diagnostics expose the current settings to the caller, so do not publish private diagnostic contents.

```python
from PIL import ImageOps
from bionic_eye import BionicEyeController

with BionicEyeController() as eye:
    eye.register_processor("invert_display", ImageOps.invert)
    eye.run_custom_function("invert_display")
    # eye.process_frame(rgb_frame) invokes the registered callable.
```

Processors are trusted Python code running with the application's privileges, not sandboxed plugins. They receive a Pillow RGB image and must return an RGB image or uint8 array of the same size. Exceptions or invalid output halt processing. Reset clears the active processor. An independently validated AI inference implementation can use this hook; this repository supplies no trained enhancement/detection model.

## Bench connections

The `Transport` interface has `exchange(request: bytes) -> bytes` and `close()`. The supplied USB and serial implementations write actual bytes for the [reference v1 protocol](PROTOCOL.md). They are not medical-device drivers. Serial can carry bytes over an already configured laboratory radio link, but this code neither pairs nor secures a radio.

The client requires `simulation: true`, `device_type: bench-emulator`, and expected capabilities. That declaration distinguishes modes but **is not authentication**. There is no cryptographic peer authentication or encryption. Use an isolated laboratory connection, not a patient-device network.

Firmware verification is separate from transport. A signature alone does not prove compatibility or safe installation; see [FIRMWARE.md](FIRMWARE.md).

## Remaining manufacturer work

No implant hardware, electrode geometry, electrical specification, patient calibration, stimulation limits, implant firmware, vendor SDK or clinical dataset was supplied. A sight-restoring implant integration cannot be completed or validated from these files alone.

A manufacturer must establish the intended use and target population, design and characterize compatible hardware and interfaces, independently review encoding and fault handling, collect appropriate engineering/biological evidence, evaluate usability and cybersecurity, and follow the applicable clinical/regulatory process. No numerical stimulation settings are supplied; this software should not be connected to people or animals.

In the United States, significant-risk device studies require FDA and institutional review board approval before initiation; implants can fall into this category. Consult the [FDA IDE approval process](https://www.fda.gov/medical-devices/investigational-device-exemption-ide/ide-approval-process). This guide is not a compliance determination or approval application.

Open software can support collaboration. This branch establishes no timeline for an affordable, available or clinically effective implant.
