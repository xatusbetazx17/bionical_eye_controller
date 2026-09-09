# Software validation scope

Run `python -m unittest discover -s tests -v`. Optional camera/serial checks require those packages; desktop tests require Tk and a display. GitHub Actions uses Xvfb and tests the installed wheel outside the checkout. Skipped tests are not passed validations.

| Check | Evidence | Does not establish |
| --- | --- | --- |
| Image processing | Pixel changes, color order, dimensions, input rejection | Better patient vision |
| Files/profiles | Actual contents, freshness, overwrite protection, roundtrips | Medical-record storage compliance |
| Controller/protocol | Acknowledgments, stopped states, invalid-message handling | Authenticated production communication |
| Serial | OS pseudo-terminal roundtrip with pyserial | Real implant/radio compatibility |
| USB | Fake-device byte exchange and cleanup on failure | Real USB-device compatibility |
| Video | Actual generated video reading and end-of-stream handling | Live camera permissions/drivers |
| Firmware | Signature, tampering, product and version checks | Safe device installation |
| Input logic | Exact phrase parsing, dwell, missing-model handling | Model accuracy or microphone compatibility |
| Desktop | Synthetic display, controls, capture and source recovery | Accessibility certification or every OS |
| Packaging | Source/wheel builds and standalone invocation | Certified deployment |

The initial local development run used Python 3.12 on Linux and passed 62 image, firmware, controller, protocol, CLI, video and serial tests. Desktop tests were skipped because no display was available. Refer to GitHub Actions for subsequent CI results. No physical webcam, microphone, USB device, pretrained hand/speech model or implant was validated in that initial run.

Reported processing times measure recent frames. They are not vision-restoration benchmarks or real-time guarantees. The viewer targets about 24 updates per second subject to host/source/filter performance. Model loading and camera drivers can block worker threads; this is a desktop research application, not a real-time medical controller.
