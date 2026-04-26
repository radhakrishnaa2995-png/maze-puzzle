# shapes.py
"""Load shape silhouettes from PNG/SVG/JPG and expose robust mask utilities."""

from __future__ import annotations

import math
import random
import re
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MaskFn = Callable[[float, float], bool]
_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_EXT_PRIORITY = {".png": 0, ".svg": 1, ".jpg": 2, ".jpeg": 2}


@dataclass(frozen=True)
class LoadedShape:
    name: str
    contains_fn: MaskFn


def _sample_cubic(p0, p1, p2, p3, n=22):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = (mt**3) * p0[0] + 3 * (mt**2) * t * p1[0] + 3 * mt * (t**2) * p2[0] + (t**3) * p3[0]
        y = (mt**3) * p0[1] + 3 * (mt**2) * t * p1[1] + 3 * mt * (t**2) * p2[1] + (t**3) * p3[1]
        pts.append((x, y))
    return pts


def _sample_quadratic(p0, p1, p2, n=18):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = (mt**2) * p0[0] + 2 * mt * t * p1[0] + (t**2) * p2[0]
        y = (mt**2) * p0[1] + 2 * mt * t * p1[1] + (t**2) * p2[1]
        pts.append((x, y))
    return pts


def _parse_path_to_polylines(path_d: str) -> list[list[tuple[float, float]]]:
    tokens = _TOKEN_RE.findall(path_d)
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    polylines: list[list[tuple[float, float]]] = []
    current_line: list[tuple[float, float]] = []
    prev_ctrl = None

    def read_float() -> float:
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
        elif cmd is None:
            raise ValueError("Invalid SVG path: missing command")

        rel = cmd.islower()
        op = cmd.upper()

        if op == "M":
            x = read_float(); y = read_float()
            if rel:
                x += cur[0]; y += cur[1]
            cur = (x, y); start = cur
            if current_line:
                polylines.append(current_line)
            current_line = [cur]
            prev_ctrl = None
            cmd = "l" if rel else "L"
        elif op == "L":
            x = read_float(); y = read_float()
            if rel:
                x += cur[0]; y += cur[1]
            cur = (x, y); current_line.append(cur); prev_ctrl = None
        elif op == "H":
            x = read_float(); x = x + cur[0] if rel else x
            cur = (x, cur[1]); current_line.append(cur); prev_ctrl = None
        elif op == "V":
            y = read_float(); y = y + cur[1] if rel else y
            cur = (cur[0], y); current_line.append(cur); prev_ctrl = None
        elif op == "C":
            x1, y1, x2, y2, x, y = [read_float() for _ in range(6)]
            if rel:
                x1, y1 = x1 + cur[0], y1 + cur[1]
                x2, y2 = x2 + cur[0], y2 + cur[1]
                x, y = x + cur[0], y + cur[1]
            current_line.extend(_sample_cubic(cur, (x1, y1), (x2, y2), (x, y)))
            cur = (x, y); prev_ctrl = (x2, y2)
        elif op == "S":
            x2, y2, x, y = [read_float() for _ in range(4)]
            if prev_ctrl is None:
                x1, y1 = cur
            else:
                x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
            if rel:
                x2, y2 = x2 + cur[0], y2 + cur[1]
                x, y = x + cur[0], y + cur[1]
            current_line.extend(_sample_cubic(cur, (x1, y1), (x2, y2), (x, y)))
            cur = (x, y); prev_ctrl = (x2, y2)
        elif op == "Q":
            x1, y1, x, y = [read_float() for _ in range(4)]
            if rel:
                x1, y1 = x1 + cur[0], y1 + cur[1]
                x, y = x + cur[0], y + cur[1]
            current_line.extend(_sample_quadratic(cur, (x1, y1), (x, y)))
            cur = (x, y); prev_ctrl = (x1, y1)
        elif op == "T":
            x, y = read_float(), read_float()
            if prev_ctrl is None:
                x1, y1 = cur
            else:
                x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
            if rel:
                x, y = x + cur[0], y + cur[1]
            current_line.extend(_sample_quadratic(cur, (x1, y1), (x, y)))
            cur = (x, y); prev_ctrl = (x1, y1)
        elif op == "A":
            _ = [read_float() for _ in range(5)]
            x, y = read_float(), read_float()
            if rel:
                x += cur[0]; y += cur[1]
            cur = (x, y); current_line.append(cur); prev_ctrl = None
        elif op == "Z":
            if current_line and current_line[-1] != start:
                current_line.append(start)
            if current_line:
                polylines.append(current_line)
            current_line = []; cur = start; prev_ctrl = None
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")

    if current_line:
        polylines.append(current_line)
    return polylines


def _draw_svg_outline_to_mask(svg_path: Path, base_size: int = 400) -> np.ndarray:
    raw = svg_path.read_bytes()
    text = raw.decode("utf-8-sig", errors="ignore")
    idx = text.find("<")
    if idx > 0:
        text = text[idx:]
    root = ET.fromstring(text)
    ns = "{http://www.w3.org/2000/svg}"

    lines: list[list[tuple[float, float]]] = []

    for elem in root.iter():
        tag = elem.tag
        if tag == f"{ns}path" and elem.get("d"):
            lines.extend(_parse_path_to_polylines(elem.get("d", "")))
        elif tag == f"{ns}polygon" and elem.get("points"):
            pts = [float(n) for n in re.split(r"[ ,]+", elem.get("points", "").strip()) if n]
            poly = list(zip(pts[0::2], pts[1::2]))
            if poly and poly[0] != poly[-1]:
                poly.append(poly[0])
            lines.append(poly)
        elif tag == f"{ns}rect":
            x = float(elem.get("x", "0")); y = float(elem.get("y", "0")); w = float(elem.get("width", "0")); h = float(elem.get("height", "0"))
            lines.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
        elif tag == f"{ns}circle":
            cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0")); r = float(elem.get("r", "0"))
            lines.append([(cx + math.cos(2 * math.pi * t / 72) * r, cy + math.sin(2 * math.pi * t / 72) * r) for t in range(73)])
        elif tag == f"{ns}ellipse":
            cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0")); rx = float(elem.get("rx", "0")); ry = float(elem.get("ry", "0"))
            lines.append([(cx + math.cos(2 * math.pi * t / 72) * rx, cy + math.sin(2 * math.pi * t / 72) * ry) for t in range(73)])

    if not lines:
        raise ValueError(f"No drawable SVG outline in {svg_path}")

    xs = [x for line in lines for x, _ in line]
    ys = [y for line in lines for _, y in line]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max_x - min_x
    h = max_y - min_y
    if w <= 0 or h <= 0:
        raise ValueError(f"Degenerate SVG bounds in {svg_path}")

    canvas = Image.new("L", (base_size, base_size), 0)
    draw = ImageDraw.Draw(canvas)
    pad = base_size * 0.08
    scale = min((base_size - 2 * pad) / w, (base_size - 2 * pad) / h)

    stroke = max(2, int(base_size * 0.008))
    for line in lines:
        mapped = [((x - min_x) * scale + pad, (y - min_y) * scale + pad) for x, y in line]
        if len(mapped) >= 2:
            draw.line(mapped, fill=255, width=stroke)

    return np.array(canvas) > 0


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    q = deque()

    for x in range(w):
        if not mask[0, x]:
            q.append((0, x)); visited[0, x] = True
        if not mask[h - 1, x]:
            q.append((h - 1, x)); visited[h - 1, x] = True
    for y in range(h):
        if not mask[y, 0]:
            q.append((y, 0)); visited[y, 0] = True
        if not mask[y, w - 1]:
            q.append((y, w - 1)); visited[y, w - 1] = True

    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    holes = (~mask) & (~visited)
    return mask | holes


def _preprocess_outline_mask(mask: np.ndarray, scale: int = 4) -> np.ndarray:
    scale = max(3, min(6, scale))
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)

    # Thicken lines + close small gaps.
    img = img.filter(ImageFilter.MaxFilter(size=5))
    img = img.filter(ImageFilter.MaxFilter(size=5))
    img = img.filter(ImageFilter.MinFilter(size=3))

    arr = np.array(img) > 0
    arr = _fill_holes(arr)
    return arr


def _orient_mask(mask: np.ndarray, name: str) -> np.ndarray:
    lname = name.lower()
    if mask.size == 0:
        return mask

    # basic stats helpers
    def edge_density(arr: np.ndarray, side: str, span: int = 8) -> float:
        span = min(span, arr.shape[1] // 3 if arr.shape[1] >= 3 else 1)
        if side == "left":
            blk = arr[:, :span]
        else:
            blk = arr[:, -span:]
        return float(blk.sum()) / max(1, blk.size)

    def band_density(arr: np.ndarray, where: str, span: int = 10) -> float:
        span = min(span, arr.shape[0] // 3 if arr.shape[0] >= 3 else 1)
        if where == "top":
            blk = arr[:span, :]
        else:
            blk = arr[-span:, :]
        return float(blk.sum()) / max(1, blk.size)

    # Horizontal orientation rules
    if any(k in lname for k in ["dinosaur", "fish", "cat"]):
        left = edge_density(mask, "left")
        right = edge_density(mask, "right")
        if right < left:
            mask = np.fliplr(mask)

    if "bird" in lname:
        left = edge_density(mask, "left")
        right = edge_density(mask, "right")
        if right > left:
            mask = np.fliplr(mask)

    # Vertical orientation rules
    if "rocket" in lname:
        top = band_density(mask, "top")
        bottom = band_density(mask, "bottom")
        if top >= bottom:
            mask = np.flipud(mask)

    if "heart" in lname or "butterfly" in lname:
        top = band_density(mask, "top")
        bottom = band_density(mask, "bottom")
        if top < bottom:
            mask = np.flipud(mask)

    return mask


def _build_raster_contains(image_path: Path) -> MaskFn:
    shape_name = image_path.stem
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    if np.any(alpha < 250):
        base = (alpha > 16) & (gray < 245)
    else:
        base = gray < 235

    base = _preprocess_outline_mask(base)
    base = _orient_mask(base, shape_name)
    ys, xs = np.where(base)
    if len(xs) == 0:
        raise ValueError(f"No silhouette detected in image: {image_path}")
    cropped = base[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        px = int(round((x + 1) * 0.5 * (w - 1)))
        py = int(round((y + 1) * 0.5 * (h - 1)))
        py = (h - 1) - py
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return fn


def _build_svg_contains(svg_path: Path) -> MaskFn:
    shape_name = svg_path.stem
    base = _draw_svg_outline_to_mask(svg_path)
    processed = _preprocess_outline_mask(base)
    processed = _orient_mask(processed, shape_name)
    ys, xs = np.where(processed)
    if len(xs) == 0:
        raise ValueError(f"No silhouette detected in SVG: {svg_path}")
    cropped = processed[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        px = int(round((x + 1) * 0.5 * (w - 1)))
        py = int(round((y + 1) * 0.5 * (h - 1)))
        py = (h - 1) - py
        return 0 <= px < w and 0 <= py < h and bool(cropped[py, px])

    return fn


def _discover_shape_files(shape_dir: str) -> list[Path]:
    root = Path(shape_dir)
    files: list[Path] = []

    search_roots = [root]
    repo_root = Path.cwd()
    if root != repo_root:
        search_roots.extend([repo_root / "assets", repo_root / "shapes", repo_root])

    for sr in search_roots:
        if sr.exists():
            files.extend(sorted([f for f in sr.rglob("*") if f.suffix.lower() in _EXT_PRIORITY]))

    seen = set()
    out: list[Path] = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def _choose_best_files(files: list[Path]) -> list[Path]:
    grouped: dict[str, list[Path]] = {}
    for f in files:
        grouped.setdefault(f.stem.lower(), []).append(f)

    chosen: list[Path] = []
    for _, variants in sorted(grouped.items()):
        variants.sort(key=lambda p: (_EXT_PRIORITY.get(p.suffix.lower(), 99), str(p)))
        chosen.extend(variants)
    return chosen


@lru_cache(maxsize=8)
def load_shapes(shape_dir: str = "assets/shapes") -> tuple[LoadedShape, ...]:
    files = _discover_shape_files(shape_dir)
    if not files:
        raise FileNotFoundError(f"No shape files found in {shape_dir} (supported: PNG, SVG, JPG).")

    ordered = _choose_best_files(files)
    loaded: list[LoadedShape] = []
    used_names: set[str] = set()

    for f in ordered:
        name = f.stem.replace("_", " ").title()
        if name in used_names:
            continue
        try:
            contains = _build_svg_contains(f) if f.suffix.lower() == ".svg" else _build_raster_contains(f)
            loaded.append(LoadedShape(name=name, contains_fn=contains))
            used_names.add(name)
        except Exception:
            continue

    if not loaded:
        raise ValueError("Shape files were discovered, but none could be parsed as valid silhouettes.")

    return tuple(loaded)


def all_shape_names(shape_dir: str = "assets/shapes") -> List[str]:
    return [s.name for s in load_shapes(shape_dir)]


def mask_for_shape(shape_name: str, shape_dir: str = "assets/shapes") -> MaskFn:
    shape = next((s for s in load_shapes(shape_dir) if s.name == shape_name), None)
    if shape is None:
        raise KeyError(f"Unknown shape name: {shape_name}")
    return shape.contains_fn


def shape_sequence(total_pages: int, rng: random.Random, shape_dir: str = "assets/shapes", min_gap: int = 3) -> List[str]:
    names = all_shape_names(shape_dir)
    sequence: List[str] = []
    while len(sequence) < total_pages:
        pool = names.copy()
        rng.shuffle(pool)
        for name in pool:
            if len(sequence) >= total_pages:
                break
            if any(name == prev for prev in sequence[-min_gap:]):
                continue
            sequence.append(name)
        if len(sequence) < total_pages and all(any(n == prev for prev in sequence[-min_gap:]) for n in names):
            candidate = rng.choice(names)
            if not sequence or sequence[-1] != candidate:
                sequence.append(candidate)
    return sequence


def palette_sequence(total_pages: int, palettes: Iterable[str], rng: random.Random) -> List[str]:
    colors = list(palettes)
    if not colors:
        return []
    out: List[str] = []
    while len(out) < total_pages:
        rng.shuffle(colors)
        out.extend(colors)
    return out[:total_pages]
