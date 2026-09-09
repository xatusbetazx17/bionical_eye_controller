"""Validated display settings. These are not implant stimulation parameters."""

from dataclasses import asdict, dataclass, fields, replace
import json
import math
from pathlib import Path
import re
import os
import tempfile

APPEARANCES = ("Default", "Sharingan", "Mangekyou Sharingan", "Sage Mode", "Tenseigan", "Rinnegan")


@dataclass(frozen=True)
class ViewSettings:
    zoom: float = 1.0
    low_light: bool = False
    auto_contrast: bool = False
    enhance: bool = False
    edges: bool = False
    segmentation: bool = False
    phosphene: bool = False
    overlay: str = ""
    iris_color: str = "#40C9B0"
    appearance: str = "Default"

    def __post_init__(self):
        if (type(self.zoom) not in (int, float) or not math.isfinite(self.zoom)
                or not 1 <= self.zoom <= 8):
            raise ValueError("Digital zoom must be a finite number between 1 and 8.")
        for key in ("low_light", "auto_contrast", "enhance", "edges", "segmentation", "phosphene"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be true or false.")
        if (not isinstance(self.overlay, str) or len(self.overlay) > 120
                or any(not c.isprintable() for c in self.overlay)):
            raise ValueError("Overlay must contain at most 120 printable characters.")
        if not isinstance(self.iris_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", self.iris_color):
            raise ValueError("Iris color must be a six-digit hex color such as #40C9B0.")
        if self.appearance not in APPEARANCES:
            raise ValueError(f"Unknown appearance. Choose from {', '.join(APPEARANCES)}.")

    def updated(self, **changes):
        return replace(self, **changes)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Settings must be a JSON object.")
        unknown = data.keys() - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        return cls(**data)

    @classmethod
    def load(cls, path):
        with Path(path).open("rb") as handle:
            raw = handle.read(16_385)
        if len(raw) > 16_384:
            raise ValueError("Settings file is too large.")
        data = json.loads(raw)
        if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] != 1:
            raise ValueError("Unsupported settings schema.")
        if set(data) != {"schema", "view"}:
            raise ValueError("Settings file requires exactly schema and view.")
        return cls.from_dict(data["view"])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".view-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"schema": 1, "view": self.to_dict()}, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
