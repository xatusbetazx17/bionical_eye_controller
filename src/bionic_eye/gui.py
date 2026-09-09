"""Desktop viewer. Camera processing stays off the Tk event thread."""

import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import ImageOps, ImageTk

from .config import APPEARANCES, ViewSettings
from .errors import BionicEyeError, HaltedError
from .inputs import DwellSelector, HandPointer, VoiceListener
from .sources import CameraSource, DemoSource, ImageSource
from .vision import render_iris


class VisionStudio:
    def __init__(self, root, controller, data_dir, source_factory=DemoSource,
                 hand_model=None, voice_model=None):
        self.root, self.controller = root, controller
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._stop, self._paused = threading.Event(), threading.Event()
        self._frames = queue.Queue(maxsize=1)
        self._events = queue.Queue(maxsize=32)
        self._sources = queue.Queue(maxsize=1)
        self._generation = 0
        self._source_pending = True
        self._source_factory = source_factory
        self._hand_model, self._voice_model = hand_model, voice_model
        self._dwell = DwellSelector()
        self._voice = None
        self._closed = False
        self._dwell_buttons = []
        self._build()
        self._worker_thread = threading.Thread(target=self._worker, name="bionic-eye-frames", daemon=True)
        self._worker_thread.start()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda event: self._action("stop"))
        self.root.bind("<Control-r>", lambda event: self._action("reset"))
        self.root.bind("<Control-s>", lambda event: self._action("capture"))
        self._poll_id = self.root.after(30, self._poll)

    def _build(self):
        root = self.root
        root.title("Bionic Eye • Vision Studio")
        root.geometry("1180x860")
        root.minsize(1040, 800)
        root.configure(bg="#101923")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#101923")
        style.configure("TLabel", background="#101923", foreground="#E4EEF5", font=("Arial", 11))
        style.configure("Muted.TLabel", foreground="#A8BECF", font=("Arial", 10))
        style.configure("Title.TLabel", font=("Arial", 22, "bold"))
        style.configure("TButton", font=("Arial", 10), padding=(10, 7))
        style.configure("TCheckbutton", background="#101923", foreground="#E4EEF5", padding=(2, 5))
        style.map("TCheckbutton", background=[("active", "#253847")], foreground=[("active", "white")])
        style.configure("TScale", background="#101923")
        header = ttk.Frame(root, padding=(22, 16))
        header.pack(fill="x")
        ttk.Label(header, text="BIONIC EYE", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="VISION STUDIO  /  SOFTWARE SIMULATOR", style="Muted.TLabel").pack(side="right")
        ttk.Label(root, text="Local image research • No implant is connected • No clinical validation",
                  style="Muted.TLabel", padding=(22, 0, 22, 12)).pack(anchor="w")
        content = ttk.Frame(root, padding=(22, 0, 22, 0))
        content.pack(fill="both", expand=True)
        sidebar = ttk.Frame(content, width=275)
        sidebar.pack(side="left", fill="y", padx=(0, 20))
        self._sidebar = sidebar
        ttk.Label(sidebar, text="View controls", font=("Arial", 15, "bold")).pack(anchor="w", pady=(0, 10))
        self.zoom = tk.DoubleVar(value=self.controller.settings.zoom)
        self.zoom_text = tk.StringVar(value="Digital zoom · 1.0×")
        ttk.Label(sidebar, textvariable=self.zoom_text).pack(anchor="w")
        ttk.Scale(sidebar, from_=1, to=8, variable=self.zoom,
                  command=self._zoom_changed, length=265).pack(fill="x", pady=(6, 6))
        self.toggles = {}
        for key, title in (("low_light", "Low-light enhancement"), ("auto_contrast", "Automatic contrast"),
                           ("enhance", "Denoise + sharpen"), ("edges", "Edge view"),
                           ("segmentation", "Brightness segmentation"), ("phosphene", "Dot-grid preview")):
            variable = tk.BooleanVar(value=getattr(self.controller.settings, key))
            self.toggles[key] = variable
            widget = ttk.Checkbutton(sidebar, text=title, variable=variable,
                                     command=lambda k=key: self._set(k, self.toggles[k].get()))
            widget.pack(anchor="w")
            self._dwell_buttons.append(widget)
        ttk.Label(sidebar, text="On-screen overlay", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        self.overlay = tk.StringVar(value=self.controller.settings.overlay)
        ttk.Entry(sidebar, textvariable=self.overlay, width=30).pack(fill="x")
        ttk.Button(sidebar, text="Apply overlay", command=lambda: self._set("overlay", self.overlay.get())).pack(fill="x", pady=(5, 12))
        ttk.Label(sidebar, text="Digital iris preview", style="Muted.TLabel").pack(anchor="w")
        self.appearance = tk.StringVar(value=self.controller.settings.appearance)
        combo = ttk.Combobox(sidebar, values=APPEARANCES, textvariable=self.appearance, state="readonly", width=27)
        combo.pack(fill="x", pady=(5, 4))
        combo.bind("<<ComboboxSelected>>", lambda event: self._set("appearance", self.appearance.get()))
        self.iris = ttk.Label(sidebar)
        self.iris.pack(pady=4)
        ttk.Button(sidebar, text="Choose iris color…", command=self._choose_color).pack(fill="x")
        profiles = ttk.Frame(sidebar)
        profiles.pack(fill="x", pady=(12, 4))
        ttk.Button(profiles, text="Save profile", command=self._save_profile).pack(side="left", expand=True, fill="x")
        ttk.Button(profiles, text="Load profile", command=self._load_profile).pack(side="right", expand=True, fill="x", padx=(5, 0))
        ttk.Label(sidebar, text="Battery: no physical telemetry", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        self._preview_panel = ttk.Frame(content)
        self._preview_panel.pack(side="left", fill="both", expand=True)
        toolbar = ttk.Frame(self._preview_panel)
        toolbar.pack(fill="x", pady=(0, 12))
        for title, callback in (("Demo", lambda: self._switch(DemoSource)), ("Camera…", self._camera),
                                ("Image…", self._image), ("Video…", self._video),
                                ("Capture", lambda: self._action("capture"))):
            widget = ttk.Button(toolbar, text=title, command=callback)
            widget.pack(side="left", padx=(0, 6))
        self.source_text = tk.StringVar(value="Opening source…")
        ttk.Label(self._preview_panel, textvariable=self.source_text, style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        self.preview = ttk.Label(self._preview_panel, text="Opening view…", anchor="center")
        self.preview.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Choose a source and adjust the view. Esc halts; Ctrl+R resets; Ctrl+S captures.")
        ttk.Label(self._preview_panel, textvariable=self.status, wraplength=720, style="Muted.TLabel").pack(fill="x", pady=(12, 8))
        actions = ttk.Frame(self._preview_panel)
        actions.pack(fill="x", pady=(6, 12))
        halt = tk.Button(actions, text="■  HALT VIEW", command=lambda: self._action("stop"),
                         bg="#BA404C", fg="white", font=("Arial", 11, "bold"), padx=14, pady=9)
        halt.pack(side="left", padx=(0, 8))
        reset = ttk.Button(actions, text="Reset view", command=lambda: self._action("reset"))
        reset.pack(side="left", padx=(0, 8))
        self._dwell_buttons.extend([halt, reset])
        ttk.Button(actions, text="Diagnostics", command=self._diagnostics).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Features & limits", command=self._limits).pack(side="left")
        self.pointer = tk.Label(root, text="●", font=("Arial", 20), fg="#40C9B0", bg="#101923")
        self._sync()

    def _sync(self):
        settings = self.controller.settings
        self.zoom.set(settings.zoom)
        self.zoom_text.set(f"Digital zoom · {settings.zoom:.1f}×")
        for key, variable in self.toggles.items():
            variable.set(getattr(settings, key))
        self.appearance.set(settings.appearance)
        self.overlay.set(settings.overlay)
        self._iris_photo = ImageTk.PhotoImage(render_iris(settings, 104), master=self.root)
        self.iris.configure(image=self._iris_photo)

    def _set(self, key, value):
        try:
            self.controller.configure(**{key: value})
            self.status.set("View settings applied.")
        except (BionicEyeError, ValueError, OSError) as exc:
            self.status.set(str(exc))
        self._sync()

    def _zoom_changed(self, value):
        zoom = round(float(value), 1)
        if zoom != self.controller.settings.zoom:
            self._set("zoom", zoom)

    def _choose_color(self):
        color = colorchooser.askcolor(self.controller.settings.iris_color, parent=self.root)[1]
        if color:
            self._set("iris_color", color)

    def _switch(self, factory):
        self._generation += 1
        self._source_pending = True
        self.preview.configure(image="", text="Opening selected source…")
        self.source_text.set("Opening selected source…")
        self._replace_queue(self._sources, (self._generation, factory))

    def _camera(self):
        index = simpledialog.askinteger("Camera", "Camera index (usually 0):", initialvalue=0, minvalue=0, parent=self.root)
        if index is not None:
            self._switch(lambda: CameraSource(index))

    def _image(self):
        path = filedialog.askopenfilename(title="Choose a local image", parent=self.root,
                                          filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All files", "*")])
        if path:
            self._switch(lambda: ImageSource(path))

    def _video(self):
        path = filedialog.askopenfilename(title="Choose a local video", parent=self.root)
        if path:
            self._switch(lambda: CameraSource(path))

    def _save_profile(self):
        path = filedialog.asksaveasfilename(title="Save view profile", defaultextension=".json", parent=self.root)
        if path:
            try:
                self.controller.settings.save(path)
                self.status.set("Profile saved.")
            except OSError as exc:
                self.status.set(str(exc))

    def _load_profile(self):
        path = filedialog.askopenfilename(title="Load view profile", filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                self.controller.configure(**ViewSettings.load(path).to_dict())
                self._sync()
                self.status.set("Profile loaded.")
            except (BionicEyeError, ValueError, OSError) as exc:
                self.status.set(str(exc))

    def _diagnostics(self):
        result = self.controller.system_diagnostics()
        window = tk.Toplevel(self.root)
        window.title("Software diagnostics")
        text = tk.Text(window, width=88, height=32, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(result, indent=2))
        text.configure(state="disabled")

    def _limits(self):
        messagebox.showinfo("Features & limits",
            "This viewer processes camera, video, and image pixels on this computer.\n\n"
            "Digital zoom crops pixels. Low-light mode brightens visible-light images. "
            "Segmentation separates brightness regions. The iris is artwork; the dot grid is illustrative.\n\n"
            "Infrared, optical zoom, physical iris control, and neural stimulation require hardware that is not supplied. "
            "No AI vision model is bundled; the SDK accepts explicitly registered processors.\n\n"
            "Firmware verification is available through the firmware-verify command. "
            "It verifies local signed packages and never installs them.\n\n"
            "This is not a vision-restoring implant or an approved medical device.", parent=self.root)

    def _action(self, action, value=None):
        try:
            if action == "stop":
                self._paused.set()
                self.controller.halt()
                self.preview.configure(image="", text="VIEW HALTED")
                self.status.set("Local view halted. Reset to continue; no physical device stop is asserted.")
            elif action == "reset":
                self.controller.reset()
                self._paused.clear()
                self._sync()
                self.status.set("Defaults restored. Choose another source if the previous source ended.")
            elif action == "capture":
                if self._source_pending:
                    raise BionicEyeError("Wait for the selected source to produce a frame.")
                path = self.controller.capture_to_directory(self.data_dir / "captures")
                self.status.set(f"Photo saved: {path}")
            elif action in ("zoom_in", "zoom_out"):
                self._set("zoom", min(8, max(1, self.controller.settings.zoom + (0.5 if action == "zoom_in" else -0.5))))
            elif action in self.toggles:
                self._set(action, value)
        except (BionicEyeError, ValueError, OSError) as exc:
            self.status.set(str(exc))

    @staticmethod
    def _replace_queue(target, item):
        try:
            target.put_nowait(item)
        except queue.Full:
            try:
                target.get_nowait()
            except queue.Empty:
                pass
            target.put_nowait(item)

    def _event(self, kind, value):
        self._replace_queue(self._events, (kind, value))

    def _worker(self):
        source, hands = None, None
        generation = 0
        try:
            if self._hand_model:
                try:
                    hands = HandPointer(self._hand_model)
                except Exception as exc:
                    self._event("input_error", f"Hand control: {exc}")
            if self._voice_model:
                try:
                    self._voice = VoiceListener(self._voice_model,
                                                 lambda value: self._event("voice", value),
                                                 lambda value: self._event("input_error", value))
                    self._voice.start()
                except Exception as exc:
                    self._event("input_error", f"Voice control: {exc}")
            try:
                source = self._source_factory()
            except Exception as exc:
                self._paused.set()
                self._event("source_error", str(exc))
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    generation, factory = self._sources.get_nowait()
                except queue.Empty:
                    factory = None
                if factory is not None:
                    if source is not None:
                        source.close()
                        source = None
                    try:
                        source = factory()
                    except Exception as exc:
                        self._paused.set()
                        self._event("source_error", str(exc))
                if source is not None and (not self._paused.is_set() or hands is not None):
                    try:
                        frame = source.read()
                        pointer = hands.locate(frame, int(started * 1000)) if hands else None
                        if not self._paused.is_set():
                            output = self.controller.process_frame(frame)
                            self._replace_queue(self._frames, (generation, output, source.name,
                                                               (time.monotonic()-started)*1000))
                        if hands:
                            self._event("pointer", pointer)
                    except HaltedError:
                        self._paused.set()
                    except Exception as exc:
                        self._paused.set()
                        source.close()
                        source = None
                        self._event("source_error", str(exc))
                self._stop.wait(max(.001, 1/24 - (time.monotonic()-started)))
        except Exception as exc:
            self._paused.set()
            self._event("source_error", str(exc))
        finally:
            if source is not None:
                source.close()
            if hands is not None:
                hands.close()
            if self._voice is not None:
                self._voice.close()

    def _hand_control(self, pointer):
        now, target = time.monotonic(), None
        if pointer is None:
            self.pointer.place_forget()
        else:
            x, y = pointer[0]*self.root.winfo_width(), pointer[1]*self.root.winfo_height()
            self.pointer.place(x=x, y=y, anchor="center")
            for widget in self._dwell_buttons:
                left = widget.winfo_rootx() - self.root.winfo_rootx()
                top = widget.winfo_rooty() - self.root.winfo_rooty()
                if left <= x < left+widget.winfo_width() and top <= y < top+widget.winfo_height():
                    target = widget
                    break
        selected = self._dwell.update(target, now)
        if selected is not None:
            selected.invoke()

    def _poll(self):
        if self._closed:
            return
        for _ in range(32):
            try:
                kind, value = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "voice":
                self._action(*value)
            elif kind == "pointer":
                self._hand_control(value)
            elif kind == "source_error":
                self.controller.halt()
                self._source_pending = True
                self.preview.configure(image="", text="SOURCE STOPPED")
                self.status.set(value)
            else:
                self.status.set(f"Optional input stopped: {value}")
        try:
            generation, frame, name, elapsed = self._frames.get_nowait()
        except queue.Empty:
            pass
        else:
            if generation == self._generation and not self._paused.is_set():
                self._source_pending = False
                self.source_text.set(f"{name}  •  {frame.width} × {frame.height}  •  latest frame {elapsed:.1f} ms")
                size = (max(1, self.preview.winfo_width()), max(1, self.preview.winfo_height()))
                image = ImageOps.contain(frame, size)
                self._photo = ImageTk.PhotoImage(image, master=self.root)
                self.preview.configure(image=self._photo, text="")
        self._poll_id = self.root.after(30, self._poll)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        self.root.after_cancel(self._poll_id)
        self._worker_thread.join(timeout=1)
        self.controller.close()
        self.root.destroy()


def run_gui(controller, data_dir, **options):
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise BionicEyeError("A desktop display and Tk are required. On a server, use 'bionic-eye demo --output demo.png'.") from exc
    try:
        VisionStudio(root, controller, data_dir, **options)
        root.mainloop()
    finally:
        try:
            if root.winfo_exists():
                root.destroy()
        except tk.TclError:
            pass
