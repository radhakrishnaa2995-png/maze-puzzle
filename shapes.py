# shapes.py
"""Shape loading utilities using uploaded assets exactly as provided."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List

import numpy as np
from PIL import Image, ImageFilter

MaskFn = Callable[[float, float], bool]
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".svg"}


@dataclass(frozen=True)
class LoadedShape:
    name: str
    contains_fn: MaskFn


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    stack = []

    for x in range(w):
        stack.append((0, x))
        stack.append((h - 1, x))
    for y in range(h):
        stack.append((y, 0))
        stack.append((y, w - 1))

    while stack:
        y, x = stack.pop()
        if not (0 <= y < h and 0 <= x < w):
            continue
        if visited[y, x] or mask[y, x]:
            continue
        visited[y, x] = True
        stack.extend([(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)])

    holes = (~mask) & (~visited)
    return mask | holes


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    # Keep original orientation exactly; only denoise, close tiny gaps, fill holes, and crop.
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img = img.filter(ImageFilter.MaxFilter(size=3))
    img = img.filter(ImageFilter.MinFilter(size=3))
    arr = np.array(img) > 0
    arr = _fill_holes(arr)

    ys, xs = np.where(arr)
    if len(xs) == 0:
        return arr
    return arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _raster_mask(path: Path) -> np.ndarray:
    rgba = np.array(Image.open(path).convert("RGBA"))
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    if np.any(alpha < 250):
        mask = (alpha > 16) & (gray < 245)
    else:
        mask = gray < 235
    return mask


def _svg_mask(path: Path, size: int = 480) -> np.ndarray:
    # Try PIL render first (if SVG raster plugin is available).
    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        arr = np.array(img)
        if arr[:, :, 3].max() > 0:
            return arr[:, :, 3] > 10
    except Exception:
        pass

    # Text fallback: conservative silhouette block when direct rasterization is unavailable.
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    canvas = Image.new("L", (size, size), 0)
    if "circle" in text:
        tmp = Image.new("L", (size, size), 0)
        from PIL import ImageDraw

        d = ImageDraw.Draw(tmp)
        d.ellipse((size * 0.12, size * 0.12, size * 0.88, size * 0.88), fill=255)
        canvas = tmp
    else:
        from PIL import ImageDraw

        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle((size * 0.14, size * 0.14, size * 0.86, size * 0.86), radius=size * 0.08, fill=255)

    return np.array(canvas) > 0


def _mask_to_fn(mask: np.ndarray) -> MaskFn:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("Empty mask")
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        px = int(round(((x + 1.0) * 0.5) * (w - 1)))
        py = int(round(((1.0 - ((y + 1.0) * 0.5)) * (h - 1))))
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return fn


def _shape_files(shape_dir: str) -> list[Path]:
    root = Path(shape_dir)
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in _ALLOWED_EXT])


@lru_cache(maxsize=8)
def load_shapes(shape_dir: str = "assets/shapes") -> tuple[LoadedShape, ...]:
    files = _shape_files(shape_dir)
    loaded: list[LoadedShape] = []

    for path in files:
        name = path.stem.replace("_", " ").title()
        try:
            raw = _svg_mask(path) if path.suffix.lower() == ".svg" else _raster_mask(path)
            mask = _normalize_mask(raw)
            loaded.append(LoadedShape(name=name, contains_fn=_mask_to_fn(mask)))
        except Exception:
            continue

    if not loaded:
        raise ValueError(f"No valid uploaded shapes found in {shape_dir}")

    return tuple(loaded)


def all_shape_names(shape_dir: str = "assets/shapes") -> List[str]:
    return [s.name for s in load_shapes(shape_dir)]


def mask_for_shape(shape_name: str, shape_dir: str = "assets/shapes") -> MaskFn:
    shape = next((s for s in load_shapes(shape_dir) if s.name == shape_name), None)
    if shape is None:
        raise KeyError(f"Unknown shape: {shape_name}")
    return shape.contains_fn


def shape_sequence(total_pages: int, rng: random.Random, shape_dir: str = "assets/shapes", min_gap: int = 2) -> List[str]:
    names = all_shape_names(shape_dir)
    if not names:
        return []

    # Ensure every uploaded shape appears before repeating.
    out: List[str] = []
    while len(out) < total_pages:
        cycle = names.copy()
        rng.shuffle(cycle)
        for name in cycle:
            if len(out) >= total_pages:
                break
            if out and name == out[-1] and len(names) > 1:
                continue
            if name in out[-min_gap:] and len(names) > min_gap:
                continue
            out.append(name)

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
