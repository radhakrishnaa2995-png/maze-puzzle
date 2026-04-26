# shapes.py
"""Shape loading utilities for uploaded assets in assets/shapes."""

from __future__ import annotations

import random
from collections import deque
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
    q = deque()

    for x in range(w):
        if not mask[0, x]:
            visited[0, x] = True
            q.append((0, x))
        if not mask[h - 1, x]:
            visited[h - 1, x] = True
            q.append((h - 1, x))
    for y in range(h):
        if not mask[y, 0]:
            visited[y, 0] = True
            q.append((y, 0))
        if not mask[y, w - 1]:
            visited[y, w - 1] = True
            q.append((y, w - 1))

    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    return mask | ((~mask) & (~visited))


def _preprocess_outline(mask: np.ndarray) -> np.ndarray:
    # Preserve orientation. Only strengthen thin outlines and fill interiors.
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img = img.filter(ImageFilter.MaxFilter(size=5))  # thicken lines
    img = img.filter(ImageFilter.MaxFilter(size=5))  # close small gaps
    img = img.filter(ImageFilter.MinFilter(size=3))

    arr = np.array(img) > 0
    arr = _fill_holes(arr)

    ys, xs = np.where(arr)
    if len(xs) == 0:
        return arr
    return arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _raster_mask(path: Path) -> np.ndarray:
    # 1. open, 2. grayscale, 3-4 detect dark object + remove white bg
    img = Image.open(path).convert("RGBA")
    rgba = np.array(img)
    alpha = rgba[:, :, 3]

    gray = np.array(img.convert("L"), dtype=np.uint8)

    # Dark foreground for line-art; transparent regions excluded.
    foreground = (gray < 235) & (alpha > 8)

    # If image has no transparency and weak contrast, use adaptive threshold fallback.
    if foreground.sum() < max(20, gray.size // 500):
        cutoff = int(np.percentile(gray, 75))
        foreground = gray < min(245, cutoff)

    return _preprocess_outline(foreground)


def _svg_mask(path: Path, size: int = 512) -> np.ndarray:
    # Attempt rasterization via Pillow plugin support.
    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        rgba = np.array(img)
        gray = np.array(img.convert("L"), dtype=np.uint8)
        alpha = rgba[:, :, 3]
        foreground = (gray < 235) & (alpha > 8)
        if foreground.sum() > max(20, gray.size // 500):
            return _preprocess_outline(foreground)
    except Exception:
        pass

    # Lightweight fallback for unsupported SVG decoding.
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    canvas = Image.new("L", (size, size), 0)
    from PIL import ImageDraw

    d = ImageDraw.Draw(canvas)
    if "circle" in text:
        d.ellipse((size * 0.12, size * 0.12, size * 0.88, size * 0.88), fill=255)
    else:
        d.rounded_rectangle((size * 0.14, size * 0.14, size * 0.86, size * 0.86), radius=size * 0.08, fill=255)
    return _preprocess_outline(np.array(canvas) > 0)


def _mask_to_fn(mask: np.ndarray) -> MaskFn:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("Empty mask")
    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        px = int(round(((x + 1.0) * 0.5) * (w - 1)))
        py = int(round((1.0 - ((y + 1.0) * 0.5)) * (h - 1)))
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return fn


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _shape_files(shape_dir: str) -> list[Path]:
    root = Path(shape_dir)
    if not root.exists():
        return []

    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or _is_hidden(p):
            continue
        if p.suffix.lower() in _ALLOWED_EXT:
            files.append(p)
    return files


@lru_cache(maxsize=8)
def load_shapes(shape_dir: str = "assets/shapes") -> tuple[LoadedShape, ...]:
    files = _shape_files(shape_dir)
    loaded: list[LoadedShape] = []

    for path in files:
        name = path.stem.replace("_", " ").title()
        try:
            raw = _svg_mask(path) if path.suffix.lower() == ".svg" else _raster_mask(path)
            loaded.append(LoadedShape(name=name, contains_fn=_mask_to_fn(raw)))
            print(f"Loaded {path.name}")
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
