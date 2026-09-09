"""Run after installation: python examples/sdk_demo.py /tmp/my-demo.png"""

import argparse
import json
from PIL import ImageOps
from bionic_eye import BionicEyeController, ViewSettings
from bionic_eye.vision import demo_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="New PNG file to create")
    args = parser.parse_args()
    with BionicEyeController(settings=ViewSettings(zoom=1.5, auto_contrast=True)) as eye:
        eye.register_processor("invert", ImageOps.invert)
        eye.run_custom_function("invert")
        eye.process_frame(demo_frame())
        print(eye.capture_photo(args.output))
        print(json.dumps(eye.system_diagnostics(), indent=2))


if __name__ == "__main__":
    main()
