# Bionic Eye Controller

An open-source desktop application and Python SDK for camera-based vision processing and reference device emulation.

**Status: executable research software, version 0.1.0.** This project provides working image processing and a bench emulator. It does **not** contain an implant, a neural stimulation implementation, or evidence that it restores sight. It has no clinical validation and is not ready for patient use.

This development branch turns the code previously embedded in the README into an installable, tested package. The [original concept](docs/original-concept.md) is retained as historical material; its embedded script should not be run.

## Try it

Use Python 3.10 or newer; Python 3.10 and 3.12 are the CI targets. A camera is optional.

```bash
git clone --branch codex/working-research-platform https://github.com/xatusbetazx17/bionical_eye_controller.git
cd bionical_eye_controller
python -m venv .venv
```

Activate the environment:

```bash
# Linux / macOS
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

If PowerShell disallows activation, use `.\.venv\Scripts\python.exe` in place of `python`; changing your execution policy is not necessary.

```bash
python -m pip install .
python -m bionic_eye demo --output demo.png --low-light --zoom 2
python -m bionic_eye gui
```

`demo.png` contains real processed pixels. Existing output files are never overwritten. The desktop app initially displays a moving synthetic scene and opens neither a camera nor a microphone automatically. Importing the package never installs dependencies or changes system packages.

The desktop viewer requires Tk and a graphical display. On Debian/Ubuntu the OS package is `python3-tk`; Python installations on Windows/macOS may include Tk. On a headless machine use the CLI instead.

### Camera and local video

```bash
python -m pip install '.[camera]'
python -m bionic_eye gui --camera 0
python -m bionic_eye gui --video recording.mp4
python -m bionic_eye process input.jpg --output enhanced.png --auto-contrast --enhance
```

Camera permissions, drivers and codecs depend on the operating system. A failed source stops the view and reports the error; select a working source and press **Reset view** to resume. **Esc** halts processing, **Ctrl+R** resets settings, and **Ctrl+S** captures a fresh frame. Captures and a bounded diagnostic log default to `~/.bionic-eye/`; override with `gui --data-dir PATH`.

## Features and exact boundaries

| Original concept | Implemented in this branch | Limitation |
| --- | --- | --- |
| Zoom | Center-crop digital zoom, 1–8× | Optical zoom requires a controllable lens |
| Night vision | Visible-light gamma enhancement | Cannot see in complete darkness or recover absent sensor detail |
| Auto contrast | Luminance histogram stretching | No clinical effectiveness claim |
| Enhanced vision | Median denoising and sharpening | These filters are not AI |
| Scene segmentation | Otsu brightness segmentation and edge view | No semantic recognition or navigation guarantee |
| AR overlay | Rendered on-screen text | No spatial tracking or optical projection |
| Iris color / appearance | Digital artwork with six presets | No physical or biological iris control |
| Photo capture | Actual PNG files with freshness and overwrite checks | Camera acquisition needs the optional package |
| Hand menu | Optional MediaPipe finger pointer and dwell latch | Requires a local Hand Landmarker model and suitable input |
| Voice commands | Optional local Vosk recognition | Requires a local speech model, microphone and PortAudio |
| Custom functions / AI | Explicit registration of trusted image processors | No AI model is bundled; arbitrary code strings are rejected |
| USB / wireless | Real USB bulk and serial byte transports for the bench protocol | No vendor implant protocol, radio discovery, BLE pairing or wireless security |
| Diagnostics / battery | Current state, measured processing timings, explicit unavailable battery telemetry | No invented physical readings or device-health certification |
| Firmware update | Offline signature, product, version, size and digest verification | No online updater, bootloader or flashing |
| Infrared | Explicit unsupported-feature error | Requires a suitable sensor and driver |
| Vision restoration | Illustrative 32×24 brightness-dot preview | No validated perception model, neural encoding or restored sight |

**Halt view** stops local processing and attempts to halt the emulator. It does not assert that a physical medical device stopped. Connections are explicit, require a compatible emulator handshake, have bounded messages/timeouts, and do not silently fall back or retry uncertain writes.

## Python SDK

```python
from bionic_eye import BionicEyeController, ViewSettings
from bionic_eye.vision import load_image

with BionicEyeController(settings=ViewSettings(zoom=2, auto_contrast=True)) as eye:
    processed = eye.process_frame(load_image("scene.png"))
    print(eye.capture_photo("processed-scene.png"))
    print(eye.system_diagnostics())
```

Frames are Pillow images or `H × W × 3` NumPy `uint8` arrays in **RGB** order, up to 16 megapixels. Settings are validated and committed locally only after an exact acknowledgment. Processing/communication failures invalidate the latest frame and latch a stopped state.

See the runnable [SDK example](examples/sdk_demo.py), [integration guide](docs/INTEGRATION.md), [protocol](docs/PROTOCOL.md), [optional inputs](docs/INPUTS.md), and [firmware format](docs/FIRMWARE.md).

## Verify

```bash
python -m pip install '.[dev,camera,hardware]'
python -m unittest discover -s tests -v
python -m build
```

Checks cover image output, captures, invalid settings, acknowledgments, disconnects, signature tampering, unavailable features, serial pseudo-terminals, video files, CLI subprocesses and desktop interactions when a display exists. GitHub Actions also exercises the built wheel outside the checkout. See [validation scope](docs/VALIDATION.md) and [development status](docs/DEVELOPMENT_STATUS.md).

## Reuse by companies and researchers

The original [MIT license](LICENSE) is unchanged. It permits commercial use, modification, distribution and sale, with the required notices retained. This branch adds no noncommercial restriction. The software is provided without warranty; see the [MIT license text](https://opensource.org/license/mit).

Companies can reuse these components in their engineering work. The license does not supply hardware designs, third-party model rights, clinical evidence or medical-device authorization. The [integration guide](docs/INTEGRATION.md) identifies what a manufacturer must still develop and validate.

Created by **Marcelo Collado / xatusbetazx17**. Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
