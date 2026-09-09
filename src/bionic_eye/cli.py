"""Installable CLI for the desktop viewer, image processing, and emulator tools."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

from . import BionicEyeController, ViewSettings, __version__
from .errors import BionicEyeError, ProtocolError
from .firmware import verify_package
from .protocol import MAX_MESSAGE_BYTES, ReferenceDevice
from .vision import demo_frame, load_image


def _view_arguments(parser):
    parser.add_argument("--profile", type=Path, help="Load a saved JSON view profile")
    parser.add_argument("--zoom", type=float, help="Digital zoom from 1 to 8")
    for flag in ("low-light", "auto-contrast", "enhance", "edges", "segmentation", "phosphene"):
        parser.add_argument(f"--{flag}", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--overlay", help="On-screen text (120 printable characters maximum)")


def _settings(args):
    settings = ViewSettings.load(args.profile) if args.profile else ViewSettings()
    updates = {key: getattr(args, key) for key in ("zoom", "low_light", "auto_contrast", "enhance", "edges",
                                                  "segmentation", "phosphene", "overlay")
               if getattr(args, key) is not None}
    return settings.updated(**updates)


def build_parser():
    parser = argparse.ArgumentParser(description="Bionic Eye software research tools. No implant integration or clinical validation.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    gui = commands.add_parser("gui", help="Open the local desktop vision studio")
    _view_arguments(gui)
    gui.add_argument("--data-dir", type=Path, default=Path.home()/".bionic-eye")
    source = gui.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, help="Explicit camera index (e.g. 0)")
    source.add_argument("--image", type=Path)
    source.add_argument("--video", type=Path)
    gui.add_argument("--hand-model", type=Path, help="Opt in to hand control with a local .task model")
    gui.add_argument("--voice-model", type=Path, help="Opt in to microphone control with a local Vosk model directory")
    demo = commands.add_parser("demo", help="Process a generated scene without a camera or display")
    _view_arguments(demo)
    demo.add_argument("--output", type=Path, required=True)
    image = commands.add_parser("process", help="Process a local image into a PNG")
    _view_arguments(image)
    image.add_argument("input", type=Path)
    image.add_argument("--output", type=Path, required=True)
    commands.add_parser("diagnostics", help="Report actual simulator state and unavailable telemetry")
    commands.add_parser("emulator", help="Serve the reference NDJSON protocol on stdin/stdout")
    device = commands.add_parser("device", help="Connect explicitly to a compatible bench emulator")
    device.add_argument("--transport", choices=("serial", "usb"), required=True)
    device.add_argument("--port")
    device.add_argument("--baudrate", type=int, default=115200)
    device.add_argument("--timeout", type=float, default=1.0)
    for name in ("vendor-id", "product-id", "endpoint-out", "endpoint-in"):
        device.add_argument(f"--{name}", type=lambda value: int(value, 0))
    device.add_argument("--interface", type=int, default=0)
    verify = commands.add_parser("firmware-verify", help="Verify an offline signed package; never flash a device")
    verify.add_argument("--image", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--signature", type=Path, required=True)
    verify.add_argument("--public-key", type=Path, required=True)
    verify.add_argument("--product", required=True, help="Expected product, obtained independently of the package")
    verify.add_argument("--current-version", type=int, required=True)
    return parser


def _print(result):
    print(json.dumps(result, indent=2, allow_nan=False))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "emulator":
            device = ReferenceDevice()
            while True:
                raw = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
                if not raw:
                    return 0
                sys.stdout.buffer.write(device.handle(raw))
                sys.stdout.buffer.flush()
        if args.command == "firmware-verify":
            _print(verify_package(args.image, args.manifest, args.signature, args.public_key,
                                  args.product, args.current_version).to_dict())
            return 0
        if args.command == "device":
            from .transports import SerialTransport, USBTransport
            if args.transport == "serial":
                if not args.port:
                    parser.error("serial requires --port")
                transport = SerialTransport(args.port, args.baudrate, args.timeout)
            else:
                if any(getattr(args, name) is None for name in ("vendor_id", "product_id", "endpoint_out", "endpoint_in")):
                    parser.error("USB requires --vendor-id, --product-id, --endpoint-out, --endpoint-in")
                transport = USBTransport(args.vendor_id, args.product_id, args.endpoint_out,
                                         args.endpoint_in, args.interface, args.timeout)
            with BionicEyeController(transport=transport) as controller:
                _print(controller.system_diagnostics())
            return 0
        if args.command == "diagnostics":
            with BionicEyeController() as controller:
                _print({"diagnostics": controller.system_diagnostics(), "battery": controller.check_battery()})
            return 0
        with ExitStack() as stack:
            audit = None
            if args.command == "gui":
                from .audit import AuditLog
                args.data_dir.mkdir(parents=True, exist_ok=True)
                audit = stack.enter_context(AuditLog(args.data_dir / "events.sqlite3"))
            controller = stack.enter_context(BionicEyeController(settings=_settings(args), audit=audit))
            if args.command in ("process", "demo"):
                frame = demo_frame() if args.command == "demo" else load_image(args.input)
                controller.process_frame(frame)
                path = controller.capture_photo(args.output)
                _print({"output": str(path), "diagnostics": controller.system_diagnostics()})
            elif args.command == "gui":
                try:
                    from .gui import run_gui
                except ImportError as exc:
                    raise BionicEyeError("The desktop viewer needs Tk; install your operating system's Python Tk package.") from exc
                from .sources import CameraSource, DemoSource, ImageSource
                factory = DemoSource
                if args.camera is not None:
                    factory = lambda: CameraSource(args.camera)
                elif args.image is not None:
                    factory = lambda: ImageSource(args.image)
                elif args.video is not None:
                    factory = lambda: CameraSource(args.video)
                run_gui(controller, args.data_dir, source_factory=factory,
                        hand_model=args.hand_model, voice_model=args.voice_model)
        return 0
    except (BionicEyeError, ProtocolError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
