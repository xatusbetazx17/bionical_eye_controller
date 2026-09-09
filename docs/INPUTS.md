# Optional local controls

Mouse and keyboard require no speech or hand packages. A normal launch opens neither camera nor microphone. `--camera` or the Camera button opens the selected camera. `--voice-model` explicitly enables microphone access.

## Hand pointer

```bash
python -m pip install '.[camera,hands]'
python -m bionic_eye gui --camera 0 --hand-model models/hand_landmarker.task
```

Obtain a compatible model from the [official MediaPipe Hand Landmarker documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker). The adapter uses the [Tasks Python API](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python), VIDEO mode and increasing timestamps. It reuses a model instance and closes it on exit.

The index fingertip controls a mirrored pointer across the window. Hold over a view toggle, Halt or Reset for 1.2 seconds. The dwell latch fires once until you leave the target; tracking loss resets it. This is hand pointing, not eye tracking or patient calibration. Missing optional models leave mouse/keyboard controls available.

## Voice

```bash
python -m pip install '.[voice]'
python -m bionic_eye gui --voice-model models/vosk-model-small-en-us
```

Extract a compatible model locally; see [Vosk installation](https://alphacephei.com/vosk/install) and its [model catalog](https://alphacephei.com/vosk/models). PortAudio may need OS installation. Speech stays local, audio is not saved, and no models download automatically. Review model licenses before redistribution.

| Whole phrase | Action |
| --- | --- |
| `eye stop` / `eye reset` | Halt / reset local view |
| `eye capture` | Save a fresh processed PNG |
| `eye zoom in` / `eye zoom out` | Change digital zoom by 0.5× |
| `eye night on` / `eye night off` | Toggle low-light processing |
| `eye contrast on` / `eye contrast off` | Toggle automatic contrast |
| `eye edges on` / `eye edges off` | Toggle edge view |
| `eye enhance on` / `eye enhance off` | Toggle denoise/sharpen filters |
| `eye preview on` / `eye preview off` | Toggle the brightness-dot display |

Only final recognition results matching a whole phrase trigger actions. Unknown phrases do nothing. No firmware, stimulation or code-execution speech commands exist. Microphone overflow stops voice input and reports failure. Actual recognition/tracking accuracy and input hardware remain to be tested on the target system.
