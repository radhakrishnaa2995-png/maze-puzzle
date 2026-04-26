"""Load SVG silhouettes and expose mask utilities for maze generation.

This module intentionally avoids non-standard binary dependencies so it works in
restricted CI/runtime environments.
"""

from __future__ import annotations

import math
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List

MaskFn = Callable[[float, float], bool]
_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class SVGShape:
    name: str
    polygons: tuple[tuple[tuple[float, float], ...], ...]
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def extent(self) -> float:
        return max(1e-9, max(self.max_x - self.min_x, self.max_y - self.min_y))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


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
            x = read_float()
            y = read_float()
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            start = cur
            if current_line:
                polylines.append(current_line)
            current_line = [cur]
            prev_ctrl = None
            # chained coordinates after M are treated as L
            cmd = "l" if rel else "L"

        elif op == "L":
            x = read_float()
            y = read_float()
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            current_line.append(cur)
            prev_ctrl = None

        elif op == "H":
            x = read_float()
            if rel:
                x += cur[0]
            cur = (x, cur[1])
            current_line.append(cur)
            prev_ctrl = None

        elif op == "V":
            y = read_float()
            if rel:
                y += cur[1]
            cur = (cur[0], y)
            current_line.append(cur)
            prev_ctrl = None

        elif op == "C":
            x1, y1, x2, y2, x, y = read_float(), read_float(), read_float(), read_float(), read_float(), read_float()
            if rel:
                x1, y1 = x1 + cur[0], y1 + cur[1]
                x2, y2 = x2 + cur[0], y2 + cur[1]
                x, y = x + cur[0], y + cur[1]
            pts = _sample_cubic(cur, (x1, y1), (x2, y2), (x, y))
            current_line.extend(pts)
            cur = (x, y)
            prev_ctrl = (x2, y2)

        elif op == "S":
            x2, y2, x, y = read_float(), read_float(), read_float(), read_float()
            if prev_ctrl is None:
                x1, y1 = cur
            else:
                x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
            if rel:
                x2, y2 = x2 + cur[0], y2 + cur[1]
                x, y = x + cur[0], y + cur[1]
            pts = _sample_cubic(cur, (x1, y1), (x2, y2), (x, y))
            current_line.extend(pts)
            cur = (x, y)
            prev_ctrl = (x2, y2)

        elif op == "Q":
            x1, y1, x, y = read_float(), read_float(), read_float(), read_float()
            if rel:
                x1, y1 = x1 + cur[0], y1 + cur[1]
                x, y = x + cur[0], y + cur[1]
            pts = _sample_quadratic(cur, (x1, y1), (x, y))
            current_line.extend(pts)
            cur = (x, y)
            prev_ctrl = (x1, y1)

        elif op == "T":
            x, y = read_float(), read_float()
            if prev_ctrl is None:
                x1, y1 = cur
            else:
                x1, y1 = (2 * cur[0] - prev_ctrl[0], 2 * cur[1] - prev_ctrl[1])
            if rel:
                x, y = x + cur[0], y + cur[1]
            pts = _sample_quadratic(cur, (x1, y1), (x, y))
            current_line.extend(pts)
            cur = (x, y)
            prev_ctrl = (x1, y1)

        elif op == "Z":
            if current_line and current_line[-1] != start:
                current_line.append(start)
            if current_line:
                polylines.append(current_line)
            current_line = []
            cur = start
            prev_ctrl = None

        elif op == "A":
            # Arc support fallback: draw as straight line to end point.
            _ = [read_float() for _ in range(5)]
            x, y = read_float(), read_float()
            if rel:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            current_line.append(cur)
            prev_ctrl = None

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


def _collect_polygons(svg_path: Path) -> list[list[tuple[float, float]]]:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = "{http://www.w3.org/2000/svg}"

    polys: list[list[tuple[float, float]]] = []

    for elem in root.iter():
        tag = elem.tag
        if tag == f"{ns}path" and elem.get("d"):
            polys.extend(_parse_path_to_polylines(elem.get("d", "")))
        elif tag == f"{ns}polygon" and elem.get("points"):
            polys.append(_parse_points_attr(elem.get("points", "")))
        elif tag == f"{ns}rect":
            x = float(elem.get("x", "0"))
            y = float(elem.get("y", "0"))
            w = float(elem.get("width", "0"))
            h = float(elem.get("height", "0"))
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            polys.append(pts)
        elif tag == f"{ns}circle":
            cx = float(elem.get("cx", "0"))
            cy = float(elem.get("cy", "0"))
            r = float(elem.get("r", "0"))
            pts = [(cx + math.cos(2 * math.pi * t / 72) * r, cy + math.sin(2 * math.pi * t / 72) * r) for t in range(73)]
            polys.append(pts)
        elif tag == f"{ns}ellipse":
            cx = float(elem.get("cx", "0"))
            cy = float(elem.get("cy", "0"))
            rx = float(elem.get("rx", "0"))
            ry = float(elem.get("ry", "0"))
            pts = [(cx + math.cos(2 * math.pi * t / 72) * rx, cy + math.sin(2 * math.pi * t / 72) * ry) for t in range(73)]
            polys.append(pts)

    return [p for p in polys if len(p) >= 3]


def _bounds(polygons: list[list[tuple[float, float]]]) -> tuple[float, float, float, float]:
    xs = [x for poly in polygons for x, _ in poly]
    ys = [y for poly in polygons for _, y in poly]
    return min(xs), min(ys), max(xs), max(ys)


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


def _load_single_svg(svg_path: Path) -> SVGShape:
    polys = _collect_polygons(svg_path)
    if not polys:
        raise ValueError(f"No supported shape elements found in {svg_path}")

    min_x, min_y, max_x, max_y = _bounds(polys)
    packed = tuple(tuple(p) for p in polys)
    return SVGShape(
        name=svg_path.stem.replace("_", " ").title(),
        polygons=packed,
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
    )


def _discover_svg_files(shape_dir: str) -> list[Path]:
    root = Path(shape_dir)
    files: list[Path] = []

    if root.exists():
        files.extend(sorted(root.glob("*.svg")))
        if not files:
            files.extend(sorted(root.rglob("*.svg")))

    # Fallback discovery for CI/repo layout differences.
    if not files:
        repo_root = Path.cwd()
        for candidate in [repo_root / "assets", repo_root / "shapes", repo_root]:
            if candidate.exists():
                files.extend(sorted(candidate.rglob("*.svg")))
            if files:
                break

    # Deduplicate while preserving order.
    seen = set()
    deduped = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


@lru_cache(maxsize=8)
def load_svg_shapes(shape_dir: str = "assets/shapes") -> tuple[SVGShape, ...]:
    files = _discover_svg_files(shape_dir)
    if not files:
        raise FileNotFoundError(
            "No SVG files found. Checked: "
            f"'{shape_dir}', '{Path.cwd() / 'assets'}', '{Path.cwd() / 'shapes'}', and repository root recursively."
        )
    return tuple(_load_single_svg(f) for f in files)


def all_shape_names(shape_dir: str = "assets/shapes") -> List[str]:
    return [s.name for s in load_svg_shapes(shape_dir)]


def mask_for_shape(shape_name: str, shape_dir: str = "assets/shapes") -> MaskFn:
    shape = next((s for s in load_svg_shapes(shape_dir) if s.name == shape_name), None)
    if shape is None:
        raise KeyError(f"Unknown shape name: {shape_name}")

    cx, cy = shape.center
    scale = shape.extent / 2

    def fn(x: float, y: float) -> bool:
        px = cx + x * scale
        py = cy + y * scale
        # odd-even rule across all SVG paths/polygons
        toggles = 0
        for poly in shape.polygons:
            if _point_in_poly(px, py, poly):
                toggles ^= 1
        return toggles == 1

    return fn


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
