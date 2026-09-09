"""Actual RGB image transforms; no physiological model or stimulation output."""

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import ViewSettings

MAX_PIXELS = 16_777_216


def rgb_image(frame):
    if isinstance(frame, np.ndarray):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Array frames must be H x W x 3 uint8 in RGB order.")
        if not frame.shape[0] or not frame.shape[1] or frame.shape[0] * frame.shape[1] > MAX_PIXELS:
            raise ValueError("Frame dimensions are empty or exceed 16 megapixels.")
        frame = Image.fromarray(frame)
    if not isinstance(frame, Image.Image):
        raise ValueError("Expected a Pillow image or an RGB uint8 NumPy array.")
    if min(frame.size) < 1 or frame.width * frame.height > MAX_PIXELS:
        raise ValueError("Frame dimensions are empty or exceed 16 megapixels.")
    return frame.convert("RGB").copy()


def load_image(path):
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Image exceeds the 16 megapixel processing limit.")
        return rgb_image(ImageOps.exif_transpose(image))


def segment_brightness(image):
    """Otsu foreground/background thresholding, not semantic object recognition."""
    gray = np.asarray(ImageOps.grayscale(image))
    histogram = np.bincount(gray.ravel(), minlength=256).astype(float)
    probability = histogram / histogram.sum()
    weight = np.cumsum(probability)
    mean = np.cumsum(probability * np.arange(256))
    denominator = weight * (1 - weight)
    variance = np.divide((mean[-1] * weight - mean) ** 2, denominator,
                         out=np.zeros(256), where=denominator > 0)
    mask = gray > int(np.argmax(variance))
    output = np.asarray(image).copy()
    output[mask] = (output[mask].astype(np.uint16) + np.array([30, 220, 140])) // 2
    return Image.fromarray(output.astype(np.uint8))


def phosphene_preview(image, columns=32, rows=24):
    """A coarse dot display only. It does not predict an implant user's perception."""
    output = Image.new("RGB", image.size)
    samples = np.asarray(image.convert("L").resize((columns, rows), Image.Resampling.BOX))
    draw = ImageDraw.Draw(output)
    cell_w, cell_h = image.width / columns, image.height / rows
    for y in range(rows):
        for x in range(columns):
            intensity = int(samples[y, x])
            cx, cy = (x + 0.5) * cell_w, (y + 0.5) * cell_h
            radius = min(cell_w, cell_h) * 0.36
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                         fill=(intensity,) * 3)
    return output


def process(frame, settings: ViewSettings):
    output = rgb_image(frame)
    width, height = output.size
    if settings.zoom != 1:
        crop_w, crop_h = max(1, round(width / settings.zoom)), max(1, round(height / settings.zoom))
        left, top = (width - crop_w) // 2, (height - crop_h) // 2
        output = output.crop((left, top, left + crop_w, top + crop_h)).resize(
            (width, height), Image.Resampling.BICUBIC)
    if settings.low_light:
        lut = [round(255 * (i / 255) ** 0.55) for i in range(256)]
        output = output.point(lut * 3)
    if settings.auto_contrast:
        y, cb, cr = output.convert("YCbCr").split()
        output = Image.merge("YCbCr", (ImageOps.autocontrast(y, cutoff=1), cb, cr)).convert("RGB")
    if settings.enhance:
        output = output.filter(ImageFilter.MedianFilter(3)).filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))
    if settings.segmentation:
        output = segment_brightness(output)
    if settings.edges:
        output = ImageOps.autocontrast(output.convert("L").filter(ImageFilter.FIND_EDGES)).convert("RGB")
    if settings.phosphene:
        output = phosphene_preview(output)
    if settings.overlay:
        draw = ImageDraw.Draw(output)
        # Pixel-measured wrapping keeps the complete overlay visible at small sizes.
        lines, line = [], ""
        for char in settings.overlay:
            if draw.textlength(line + char) > max(8, width - 16):
                lines.append(line)
                line = ""
            line += char
        lines.append(line)
        block_height = 8 + 14 * len(lines)
        draw.rectangle((0, 0, width, block_height), fill="#101E2A")
        for index, text in enumerate(lines):
            draw.text((8, 4 + 14 * index), text, fill="white")
    return output


def render_iris(settings, size=144):
    """Digital artwork rendered in the UI; never changes a biological/physical iris."""
    image = Image.new("RGB", (size, size), "#0B1520")
    draw = ImageDraw.Draw(image)
    c, radius = size / 2, size * 0.43
    draw.ellipse((c - radius, c - radius, c + radius, c + radius), fill=settings.iris_color)
    spokes = 72 if settings.appearance == "Default" else 36
    for index in range(spokes):
        angle = 2 * math.pi * index / spokes
        draw.line((c + radius * .35 * math.cos(angle), c + radius * .35 * math.sin(angle),
                   c + radius * .94 * math.cos(angle), c + radius * .94 * math.sin(angle)),
                  fill="#174A50", width=max(1, size // 100))
    if settings.appearance in ("Rinnegan", "Tenseigan"):
        for proportion in (.48, .66, .84):
            r = radius * proportion
            draw.ellipse((c - r, c - r, c + r, c + r), outline="#101820", width=2)
        if settings.appearance == "Tenseigan":
            for index in range(8):
                angle = index * math.pi / 4
                draw.line((c, c, c + radius*.9*math.cos(angle), c + radius*.9*math.sin(angle)),
                          fill="#C6FFFF", width=2)
    elif settings.appearance != "Default":
        count = {"Sharingan": 3, "Mangekyou Sharingan": 6, "Sage Mode": 2}[settings.appearance]
        for index in range(count):
            angle = index * 2 * math.pi / count
            x, y = c + radius * .6 * math.cos(angle), c + radius * .6 * math.sin(angle)
            r = radius * .13
            draw.ellipse((x-r, y-r, x+r, y+r), fill="#101820")
    r = radius * .32
    draw.ellipse((c-r, c-r, c+r, c+r), fill="#02070D")
    draw.ellipse((c-radius*.38, c-radius*.43, c-radius*.15, c-radius*.2), fill="#DFFFF8")
    return image


def demo_frame(index=0, size=(640, 480)):
    """Deterministic moving test scene generated locally; no external assets."""
    w, h = size
    image = Image.new("RGB", size, "#14293A")
    draw = ImageDraw.Draw(image)
    for x in range(w):
        gray = 12 + int(75 * x / max(1, w - 1))
        draw.line((x, 0, x, h), fill=(gray // 2, gray, min(255, gray + 25)))
    draw.rectangle((w*.15, h*.2, w*.4, h*.75), fill="#A7C6CF")
    draw.rectangle((w*.22, h*.32, w*.34, h*.58), fill="#243B50")
    x = int(w * (.68 + .1 * math.sin(index / 15)))
    draw.ellipse((x-w*.1, h*.3, x+w*.1, h*.57), fill="#F3AA58")
    for i in range(5):
        draw.line((w*.5, h*(.69+i*.025), w*.86, h*(.69+i*.025)), fill="white", width=1+i)
    draw.text((16, h - 30), "SYNTHETIC SCENE | SOFTWARE SIMULATOR", fill="white")
    return image
