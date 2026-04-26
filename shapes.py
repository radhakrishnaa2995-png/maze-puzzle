# shapes.py
"""Shape loading and normalization utilities for maze masks."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MaskFn = Callable[[float, float], bool]
_EXTS = {".png", ".jpg", ".jpeg", ".svg"}


@dataclass(frozen=True)
class LoadedShape:
    name: str
    contains_fn: MaskFn


def _sample_grid_mask(fn: MaskFn, size: int = 360) -> np.ndarray:
    xs = np.linspace(-1.0, 1.0, size)
    ys = np.linspace(1.0, -1.0, size)
    arr = np.zeros((size, size), dtype=bool)
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            arr[r, c] = bool(fn(float(x), float(y)))
    return arr


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    outside = np.zeros_like(mask, dtype=bool)
    stack = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]

    while stack:
        y, x = stack.pop()
        if not (0 <= y < h and 0 <= x < w):
            continue
        if outside[y, x] or mask[y, x]:
            continue
        outside[y, x] = True
        stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])

    return mask | (~mask & ~outside)


def _normalize_mask(mask: np.ndarray, shape_name: str) -> np.ndarray:
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img = img.filter(ImageFilter.MaxFilter(size=5))
    img = img.filter(ImageFilter.MinFilter(size=3))
    arr = np.array(img) > 0
    arr = _fill_holes(arr)

    ys, xs = np.where(arr)
    if len(xs) == 0:
        return arr
    arr = arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]

    lname = shape_name.lower()

    # Upright normalization.
    if any(k in lname for k in ["rocket", "bird", "butterfly", "shield", "heart", "triangle"]):
        top_mass = float(arr[: arr.shape[0] // 3, :].sum())
        bottom_mass = float(arr[-arr.shape[0] // 3 :, :].sum())
        if "rocket" in lname and top_mass > bottom_mass:
            arr = np.flipud(arr)
        if any(k in lname for k in ["bird", "butterfly", "heart", "triangle", "shield"]) and bottom_mass < top_mass:
            arr = np.flipud(arr)

    # Horizontal orientation normalization (face right).
    if arr.shape[1] >= arr.shape[0] or any(k in lname for k in ["cat", "dinosaur", "fish", "bird", "arrow"]):
        left_edge = float(arr[:, : max(2, arr.shape[1] // 10)].sum())
        right_edge = float(arr[:, -max(2, arr.shape[1] // 10) :].sum())
        if left_edge > right_edge:
            arr = np.fliplr(arr)

    return arr


def _mask_to_fn(mask: np.ndarray) -> MaskFn:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("Empty shape mask")
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def contains(x: float, y: float) -> bool:
        px = int(round(((x + 1.0) * 0.5) * (w - 1)))
        py = int(round(((1.0 - (y + 1.0) * 0.5)) * (h - 1)))
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return contains


def _load_raster_mask(path: Path) -> np.ndarray:
    rgba = np.array(Image.open(path).convert("RGBA"))
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    if np.any(alpha < 250):
        mask = (alpha > 20) & (gray < 245)
    else:
        mask = gray < 235
    return mask


def _load_svg_mask(path: Path, size: int = 420) -> np.ndarray:
    # Minimal robust fallback: render any SVG-like outline as non-white pixels after PIL open attempt.
    # If PIL cannot open, try text-based coarse raster by drawing path bounds (safe fallback).
    try:
        # Pillow can open many SVGs if rasterizer support exists.
        img = Image.open(path).convert("RGBA")
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        arr = np.array(img)
        return arr[:, :, 3] > 10
    except Exception:
        text = path.read_text(encoding="utf-8", errors="ignore")
        canvas = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(canvas)
        # Coarse fallback silhouette block if SVG parser isn't available.
        if "circle" in text.lower():
            draw.ellipse((size * 0.15, size * 0.15, size * 0.85, size * 0.85), fill=255)
        else:
            draw.rounded_rectangle((size * 0.12, size * 0.12, size * 0.88, size * 0.88), radius=size * 0.12, fill=255)
        return np.array(canvas) > 0


def _discover_uploaded_shapes(shape_dir: str) -> list[Path]:
    root = Path(shape_dir)
    search_roots = [root, Path.cwd() / "assets" / "shapes", Path.cwd() / "shapes"]
    files: list[Path] = []
    seen: set[str] = set()

    for sr in search_roots:
        if not sr.exists():
            continue
        for f in sorted(sr.rglob("*")):
            if f.suffix.lower() not in _EXTS:
                continue
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            files.append(f)
    return files


def _builtin_shape_fns() -> dict[str, MaskFn]:
    def circle(x: float, y: float) -> bool:
        return x * x + y * y <= 0.95**2

    def oval(x: float, y: float) -> bool:
        return (x / 0.95) ** 2 + (y / 0.7) ** 2 <= 1.0

    def diamond(x: float, y: float) -> bool:
        return abs(x) / 0.95 + abs(y) / 0.95 <= 1.0

    def triangle(x: float, y: float) -> bool:
        if y < -0.9 or y > 0.9:
            return False
        w = (0.95 * (0.95 - y)) / 1.85
        return abs(x) <= w

    def hexagon(x: float, y: float) -> bool:
        ax, ay = abs(x), abs(y)
        return ay <= 0.85 and ax <= 0.95 and (ax * 0.58 + ay) <= 0.95

    def heart(x: float, y: float) -> bool:
        x2 = x * 1.15
        y2 = y * 1.15
        a = (x2 * x2 + y2 * y2 - 1) ** 3 - x2 * x2 * y2**3
        return a <= 0

    def star(x: float, y: float) -> bool:
        ang = math.atan2(y, x)
        r = math.hypot(x, y)
        lim = 0.35 + 0.55 * (0.5 + 0.5 * math.cos(5 * ang))
        return r <= lim

    def cloud(x: float, y: float) -> bool:
        c1 = (x + 0.35) ** 2 + (y + 0.05) ** 2 <= 0.33**2
        c2 = (x - 0.05) ** 2 + (y + 0.18) ** 2 <= 0.42**2
        c3 = (x - 0.45) ** 2 + (y + 0.03) ** 2 <= 0.3**2
        base = abs(x) <= 0.85 and -0.45 <= y <= 0.2
        return (c1 or c2 or c3) and base

    def moon(x: float, y: float) -> bool:
        outer = x * x + y * y <= 0.9**2
        inner = (x + 0.28) ** 2 + y * y <= 0.78**2
        return outer and not inner

    def shield(x: float, y: float) -> bool:
        if y > 0.85 or y < -0.95:
            return False
        if y >= 0.0:
            return abs(x) <= 0.68 + 0.2 * (0.85 - y)
        w = 0.9 * (1.0 + y)
        return abs(x) <= max(0.03, w)

    def arrow(x: float, y: float) -> bool:
        shaft = -0.9 <= x <= 0.25 and abs(y) <= 0.22
        head = x >= 0.1 and abs(y) <= (0.95 - x) * 0.9
        return shaft or head

    def spiral(x: float, y: float) -> bool:
        r = math.hypot(x, y)
        if r > 0.95:
            return False
        ang = math.atan2(y, x)
        if ang < 0:
            ang += 2 * math.pi
        target = 0.12 + 0.11 * ang
        return abs(r - target) <= 0.09

    return {
        "Star": star,
        "Diamond": diamond,
        "Circle": circle,
        "Triangle": triangle,
        "Heart": heart,
        "Hexagon": hexagon,
        "Oval": oval,
        "Cloud": cloud,
        "Moon": moon,
        "Shield": shield,
        "Arrow": arrow,
        "Spiral": spiral,
    }


@lru_cache(maxsize=8)
def load_shapes(shape_dir: str = "assets/shapes") -> tuple[LoadedShape, ...]:
    loaded: list[LoadedShape] = []
    seen_names: set[str] = set()

    # Uploaded shapes.
    for path in _discover_uploaded_shapes(shape_dir):
        name = path.stem.replace("_", " ").title()
        if name in seen_names:
            continue
        try:
            mask = _load_svg_mask(path) if path.suffix.lower() == ".svg" else _load_raster_mask(path)
            norm = _normalize_mask(mask, name)
            loaded.append(LoadedShape(name=name, contains_fn=_mask_to_fn(norm)))
            seen_names.add(name)
        except Exception:
            continue

    # Built-in generated shapes.
    for name, fn in _builtin_shape_fns().items():
        if name in seen_names:
            continue
        mask = _sample_grid_mask(fn, size=360)
        norm = _normalize_mask(mask, name)
        loaded.append(LoadedShape(name=name, contains_fn=_mask_to_fn(norm)))
        seen_names.add(name)

    if not loaded:
        raise ValueError("No valid shape masks could be loaded.")

    return tuple(loaded)


def all_shape_names(shape_dir: str = "assets/shapes") -> List[str]:
    return [s.name for s in load_shapes(shape_dir)]


def mask_for_shape(shape_name: str, shape_dir: str = "assets/shapes") -> MaskFn:
    item = next((s for s in load_shapes(shape_dir) if s.name == shape_name), None)
    if item is None:
        raise KeyError(f"Unknown shape name: {shape_name}")
    return item.contains_fn


def shape_sequence(total_pages: int, rng: random.Random, shape_dir: str = "assets/shapes", min_gap: int = 4) -> List[str]:
    names = all_shape_names(shape_dir)
    if not names:
        return []

    out: List[str] = []
    while len(out) < total_pages:
        pool = names.copy()
        rng.shuffle(pool)
        for name in pool:
            if len(out) >= total_pages:
                break
            if name in out[-min_gap:]:
                continue
            out.append(name)
        if len(out) < total_pages:
            fallback = rng.choice(names)
            if not out or out[-1] != fallback:
                out.append(fallback)

    return out[:total_pages]


def palette_sequence(total_pages: int, palettes: Iterable, rng: random.Random) -> List:
    colors = list(palettes)
    if not colors:
        return []
    out = []
    while len(out) < total_pages:
        rng.shuffle(colors)
        out.extend(colors)
    return out[:total_pages]
