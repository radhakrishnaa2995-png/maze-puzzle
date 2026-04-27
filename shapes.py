"""Shape loading and sequencing utilities for uploaded assets."""

from __future__ import annotations

import io
import random
import re
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
    source_file: str


def _clean_name(path: Path) -> str:
    base = path.name
    # Drop extension and extra pseudo-extensions embedded in filenames (e.g. fish.svg.png)
    base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
    base = re.sub(r"\bsvg\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[._-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base.title() if base else "Shape"


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
    """Only cleanup and crop; never rotate/mirror/invert the uploaded orientation."""
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img = img.filter(ImageFilter.MaxFilter(size=5))
    img = img.filter(ImageFilter.MinFilter(size=3))

    arr = np.array(img) > 0
    arr = _fill_holes(arr)

    ys, xs = np.where(arr)
    if len(xs) == 0:
        return arr
    return arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _raster_mask_from_image(img: Image.Image) -> np.ndarray:
    rgba_img = img.convert("RGBA")
    rgba = np.array(rgba_img)
    alpha = rgba[:, :, 3]
    gray = np.array(rgba_img.convert("L"), dtype=np.uint8)

    # Robust extraction for thin line-art on light backgrounds.
    foreground = (gray <= 245) & (alpha > 0)
    if foreground.sum() < max(24, gray.size // 600):
        cutoff = int(np.percentile(gray, 90))
        foreground = (gray <= min(252, cutoff)) & (alpha > 0)
    if foreground.sum() < max(24, gray.size // 700):
        border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        bg = int(np.median(border))
        foreground = (np.abs(gray.astype(np.int16) - bg) >= 8) & (alpha > 0)
    if foreground.sum() < max(24, gray.size // 800):
        # Final fallback: treat non-near-white pixels as foreground.
        foreground = (gray < 253) & (alpha > 0)

    return _preprocess_outline(foreground)


def _raster_mask(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return _raster_mask_from_image(img)


def _svg_mask(path: Path, size: int = 1024) -> np.ndarray:
    # Some uploads may have .svg extension but actually contain raster bytes.
    try:
        with Image.open(path) as img:
            return _raster_mask_from_image(img)
    except Exception:
        pass

    try:
        import cairosvg  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("SVG support requires cairosvg for vector SVG files") from exc

    svg_bytes = path.read_bytes()
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=size, output_height=size)
    with Image.open(io.BytesIO(png_bytes)) as img:
        return _raster_mask_from_image(img)


def _mask_to_fn(mask: np.ndarray) -> MaskFn:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError("Empty mask")

    cropped = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        px = int(round(((x + 1.0) * 0.5) * (w - 1)))
        # Keep uploaded orientation: no vertical inversion.
        py = int(round(((y + 1.0) * 0.5) * (h - 1)))
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return fn


def _safe_default_mask(size: int = 256) -> np.ndarray:
    """Guaranteed non-empty fallback mask to keep every uploaded file represented."""
    canvas = Image.new("L", (size, size), 0)
    from PIL import ImageDraw

    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((size * 0.14, size * 0.14, size * 0.86, size * 0.86), radius=size * 0.16, fill=255)
    return np.array(canvas) > 0


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


@lru_cache(maxsize=16)
def load_shapes(shape_dir: str = "assets/shapes", orientation_mode: str = "original") -> tuple[LoadedShape, ...]:
    if orientation_mode != "original":
        raise ValueError("orientation_mode must be 'original'")

    files = _shape_files(shape_dir)
    loaded: list[LoadedShape] = []
    failures: list[str] = []

    for path in files:
        try:
            raw = _svg_mask(path) if path.suffix.lower() == ".svg" else _raster_mask(path)
            if raw.sum() == 0:
                raw = _safe_default_mask()
            loaded.append(LoadedShape(name=_clean_name(path), contains_fn=_mask_to_fn(raw), source_file=path.name))
        except Exception as exc:
            failures.append(f"{path.name} ({exc})")
            # Keep file in plan with safe fallback instead of skipping it.
            fallback = _safe_default_mask()
            loaded.append(LoadedShape(name=_clean_name(path), contains_fn=_mask_to_fn(fallback), source_file=path.name))

    if failures:
        print("Used fallback masks for problematic shapes:")
        for item in failures:
            print(f" - {item}")

    if not loaded:
        raise ValueError(f"No valid uploaded shapes found in {shape_dir}")

    print(f"Loaded {len(loaded)} shapes")
    return tuple(loaded)


def all_shape_names(shape_dir: str = "assets/shapes", orientation_mode: str = "original") -> List[str]:
    return [s.name for s in load_shapes(shape_dir, orientation_mode)]


def mask_for_shape(shape_name: str, shape_dir: str = "assets/shapes", orientation_mode: str = "original") -> MaskFn:
    shape = next((s for s in load_shapes(shape_dir, orientation_mode) if s.name == shape_name), None)
    if shape is None:
        raise KeyError(f"Unknown shape: {shape_name}")
    return shape.contains_fn


def shape_sequence(total_pages: int, rng: random.Random, shape_dir: str = "assets/shapes", orientation_mode: str = "original") -> List[str]:
    names = all_shape_names(shape_dir, orientation_mode)
    if not names:
        return []

    out: List[str] = []
    while len(out) < total_pages:
        cycle = names.copy()
        rng.shuffle(cycle)
        out.extend(cycle)
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
