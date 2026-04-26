"""Load shape silhouettes from PNG/SVG/JPG and expose mask utilities."""

from __future__ import annotations

import math
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List

import numpy as np
from PIL import Image

MaskFn = Callable[[float, float], bool]
_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_EXT_PRIORITY = {".png": 0, ".svg": 1, ".jpg": 2, ".jpeg": 2}


@dataclass(frozen=True)
class LoadedShape:
    name: str
    contains_fn: MaskFn


def _sample_cubic(p0, p1, p2, p3, n=20):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = (mt**3) * p0[0] + 3 * (mt**2) * t * p1[0] + 3 * mt * (t**2) * p2[0] + (t**3) * p3[0]
        y = (mt**3) * p0[1] + 3 * (mt**2) * t * p1[1] + 3 * mt * (t**2) * p2[1] + (t**3) * p3[1]
        pts.append((x, y))
    return pts


def _sample_quadratic(p0, p1, p2, n=16):
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

        assert cmd is not None
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


def _parse_points_attr(raw: str) -> list[tuple[float, float]]:
    nums = [float(n) for n in re.split(r"[ ,]+", raw.strip()) if n]
    pts = list(zip(nums[0::2], nums[1::2]))
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _point_in_poly(x: float, y: float, poly: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_inter = (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            if x < x_inter:
                inside = not inside
        j = i
    return inside


def _build_svg_contains(svg_path: Path) -> MaskFn:
    raw = svg_path.read_bytes()
    text = raw.decode("utf-8-sig", errors="ignore")
    start_idx = text.find("<")
    if start_idx > 0:
        text = text[start_idx:]
    root = ET.fromstring(text)
    ns = "{http://www.w3.org/2000/svg}"

    polys: list[list[tuple[float, float]]] = []
    for elem in root.iter():
        tag = elem.tag
        if tag == f"{ns}path" and elem.get("d"):
            polys.extend(_parse_path_to_polylines(elem.get("d", "")))
        elif tag == f"{ns}polygon" and elem.get("points"):
            polys.append(_parse_points_attr(elem.get("points", "")))
        elif tag == f"{ns}rect":
            x = float(elem.get("x", "0")); y = float(elem.get("y", "0")); w = float(elem.get("width", "0")); h = float(elem.get("height", "0"))
            polys.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
        elif tag == f"{ns}circle":
            cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0")); r = float(elem.get("r", "0"))
            polys.append([(cx + math.cos(2 * math.pi * t / 72) * r, cy + math.sin(2 * math.pi * t / 72) * r) for t in range(73)])
        elif tag == f"{ns}ellipse":
            cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0")); rx = float(elem.get("rx", "0")); ry = float(elem.get("ry", "0"))
            polys.append([(cx + math.cos(2 * math.pi * t / 72) * rx, cy + math.sin(2 * math.pi * t / 72) * ry) for t in range(73)])

    polys = [tuple(p) for p in polys if len(p) >= 3]
    if not polys:
        raise ValueError(f"No valid polygonal content in SVG: {svg_path}")

    xs = [x for poly in polys for x, _ in poly]
    ys = [y for poly in polys for _, y in poly]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    scale = max(max(xs) - min(xs), max(ys) - min(ys)) / 2

    def fn(x: float, y: float) -> bool:
        px = cx + x * scale
        py = cy + y * scale
        toggles = 0
        for poly in polys:
            if _point_in_poly(px, py, poly):
                toggles ^= 1
        return toggles == 1

    return fn


def _build_raster_contains(image_path: Path) -> MaskFn:
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)

    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]
    gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])

    # Prefer alpha silhouettes when present, otherwise dark-object-on-light-background.
    if np.any(alpha < 250):
        mask = alpha > 16
        mask &= gray < 245
    else:
        mask = gray < 235

    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise ValueError(f"No black silhouette detected in image: {image_path}")

    min_x, max_x = int(xs.min()), int(xs.max())
    min_y, max_y = int(ys.min()), int(ys.max())
    cropped = mask[min_y : max_y + 1, min_x : max_x + 1]
    h, w = cropped.shape

    def fn(x: float, y: float) -> bool:
        # x,y are normalized to [-1, 1]
        px = int(round((x + 1) * 0.5 * (w - 1)))
        py = int(round((y + 1) * 0.5 * (h - 1)))
        py = (h - 1) - py
        if 0 <= px < w and 0 <= py < h:
            return bool(cropped[py, px])
        return False

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
        chosen.extend(variants)  # keep fallbacks in order if first fails
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
            if f.suffix.lower() == ".svg":
                contains = _build_svg_contains(f)
            else:
                contains = _build_raster_contains(f)
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
