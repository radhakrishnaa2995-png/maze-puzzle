"""Creative child-friendly shape masks for maze silhouettes."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Iterable, List

MaskFn = Callable[[float, float], bool]


@dataclass(frozen=True)
class ShapeTemplate:
    name: str
    mask: MaskFn


def _circle(cx: float, cy: float, r: float) -> MaskFn:
    def fn(x: float, y: float) -> bool:
        dx, dy = x - cx, y - cy
        return (dx * dx) + (dy * dy) <= r * r

    return fn


def _ellipse(cx: float, cy: float, rx: float, ry: float, rot: float = 0.0) -> MaskFn:
    c, s = math.cos(rot), math.sin(rot)

    def fn(x: float, y: float) -> bool:
        tx = x - cx
        ty = y - cy
        xr = tx * c + ty * s
        yr = -tx * s + ty * c
        return (xr * xr) / (rx * rx + 1e-9) + (yr * yr) / (ry * ry + 1e-9) <= 1

    return fn


def _rect(cx: float, cy: float, w: float, h: float) -> MaskFn:
    def fn(x: float, y: float) -> bool:
        return abs(x - cx) <= w / 2 and abs(y - cy) <= h / 2

    return fn


def _polygon(points: list[tuple[float, float]]) -> MaskFn:
    def fn(x: float, y: float) -> bool:
        inside = False
        j = len(points) - 1
        for i, (xi, yi) in enumerate(points):
            xj, yj = points[j]
            if (yi > y) != (yj > y):
                x_inter = (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
                if x < x_inter:
                    inside = not inside
            j = i
        return inside

    return fn


def _star(cx: float, cy: float, r_outer: float, r_inner: float) -> MaskFn:
    pts: list[tuple[float, float]] = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _polygon(pts)


def _heart(scale: float = 1.0, shift_y: float = 0.02) -> MaskFn:
    def fn(x: float, y: float) -> bool:
        sx = x / max(0.1, scale)
        sy = (y - shift_y) / max(0.1, scale)
        value = (sx * sx + sy * sy - 1) ** 3 - sx * sx * sy**3
        return value <= 0 and sy <= 1.05

    return fn


def _union(parts: Iterable[MaskFn]) -> MaskFn:
    parts = list(parts)

    def fn(x: float, y: float) -> bool:
        return any(p(x, y) for p in parts)

    return fn


def _subtract(base: MaskFn, holes: Iterable[MaskFn]) -> MaskFn:
    holes = list(holes)

    def fn(x: float, y: float) -> bool:
        return base(x, y) and not any(h(x, y) for h in holes)

    return fn


def _build_templates(rng: random.Random) -> List[ShapeTemplate]:
    j = lambda s=0.04: rng.uniform(-s, s)

    templates: List[ShapeTemplate] = []

    # Dinosaur
    dinosaur = _union(
        [
            _ellipse(-0.05, -0.02, 0.55 + j(0.03), 0.34 + j(0.03)),
            _rect(0.38, 0.18, 0.24, 0.22),
            _circle(0.50, 0.28, 0.16),
            _polygon([(-0.62, -0.02), (-0.92, 0.10), (-0.80, -0.18)]),
            _rect(-0.22, -0.46, 0.16, 0.26),
            _rect(0.10, -0.45, 0.16, 0.26),
        ]
    )
    templates.append(ShapeTemplate("Dinosaur", dinosaur))

    # Rocket
    rocket = _union(
        [
            _ellipse(0.0, 0.02, 0.30 + j(0.02), 0.62 + j(0.04)),
            _polygon([(0.0, 0.94), (-0.18, 0.56), (0.18, 0.56)]),
            _polygon([(-0.30, -0.16), (-0.54, -0.38), (-0.16, -0.34)]),
            _polygon([(0.30, -0.16), (0.54, -0.38), (0.16, -0.34)]),
            _polygon([(-0.10, -0.60), (0.10, -0.60), (0.0, -0.92)]),
        ]
    )
    templates.append(ShapeTemplate("Rocket", rocket))

    # Animal (cat-like)
    animal = _union(
        [
            _ellipse(-0.08, -0.05, 0.52, 0.30),
            _circle(0.38, 0.18, 0.20),
            _polygon([(0.26, 0.30), (0.34, 0.54), (0.44, 0.32)]),
            _polygon([(0.44, 0.32), (0.56, 0.54), (0.56, 0.30)]),
            _rect(-0.28, -0.45, 0.14, 0.28),
            _rect(-0.02, -0.45, 0.14, 0.28),
            _rect(0.22, -0.45, 0.14, 0.28),
            _ellipse(-0.56, 0.20, 0.26, 0.08, rot=0.8),
        ]
    )
    templates.append(ShapeTemplate("Animal", animal))

    # Butterfly
    butterfly = _union(
        [
            _ellipse(-0.34, 0.20, 0.32, 0.28),
            _ellipse(0.34, 0.20, 0.32, 0.28),
            _ellipse(-0.28, -0.28, 0.34, 0.24),
            _ellipse(0.28, -0.28, 0.34, 0.24),
            _rect(0.0, -0.02, 0.16, 0.72),
        ]
    )
    templates.append(ShapeTemplate("Butterfly", butterfly))

    # Fish
    fish = _union(
        [
            _ellipse(-0.08, -0.02, 0.58, 0.34),
            _polygon([(0.46, 0.0), (0.90, 0.30), (0.90, -0.30)]),
            _polygon([(-0.10, 0.33), (0.12, 0.62), (0.18, 0.28)]),
        ]
    )
    templates.append(ShapeTemplate("Fish", fish))

    # Car
    car = _union(
        [
            _rect(0.0, -0.18, 1.40, 0.44),
            _polygon([(-0.56, 0.04), (-0.26, 0.34), (0.34, 0.34), (0.60, 0.04)]),
            _circle(-0.42, -0.36, 0.20),
            _circle(0.42, -0.36, 0.20),
        ]
    )
    templates.append(ShapeTemplate("Car", car))

    # Train
    train = _union(
        [
            _rect(-0.12, -0.12, 1.42, 0.44),
            _rect(0.44, 0.14, 0.42, 0.34),
            _rect(0.58, 0.42, 0.16, 0.20),
            _circle(-0.56, -0.38, 0.16),
            _circle(-0.12, -0.38, 0.16),
            _circle(0.34, -0.38, 0.16),
        ]
    )
    templates.append(ShapeTemplate("Train", train))

    # Castle
    castle = _union(
        [
            _rect(0.0, -0.05, 1.32, 0.74),
            _rect(-0.52, 0.34, 0.30, 0.46),
            _rect(0.52, 0.34, 0.30, 0.46),
            _rect(-0.25, 0.42, 0.14, 0.16),
            _rect(0.0, 0.42, 0.14, 0.16),
            _rect(0.25, 0.42, 0.14, 0.16),
        ]
    )
    templates.append(ShapeTemplate("Castle", castle))

    # Tree
    tree = _union(
        [
            _rect(0.0, -0.52, 0.26, 0.56),
            _circle(0.0, 0.12, 0.42),
            _circle(-0.30, 0.04, 0.28),
            _circle(0.30, 0.04, 0.28),
            _circle(0.0, 0.40, 0.26),
        ]
    )
    templates.append(ShapeTemplate("Tree", tree))

    # Flower
    flower = _union(
        [
            _circle(0.0, 0.08, 0.22),
            _circle(0.0, 0.46, 0.21),
            _circle(0.0, -0.30, 0.21),
            _circle(-0.38, 0.08, 0.21),
            _circle(0.38, 0.08, 0.21),
            _circle(-0.28, 0.34, 0.20),
            _circle(0.28, 0.34, 0.20),
            _rect(0.0, -0.62, 0.11, 0.44),
        ]
    )
    templates.append(ShapeTemplate("Flower", flower))

    # Ice Cream
    ice_cream = _union(
        [
            _circle(-0.18, 0.34, 0.25),
            _circle(0.16, 0.34, 0.25),
            _circle(0.0, 0.50, 0.25),
            _polygon([(-0.28, 0.14), (0.28, 0.14), (0.0, -0.88)]),
        ]
    )
    templates.append(ShapeTemplate("Ice Cream", ice_cream))

    # Balloon
    balloon = _union(
        [
            _ellipse(0.0, 0.18, 0.42, 0.54),
            _polygon([(-0.08, -0.28), (0.08, -0.28), (0.0, -0.44)]),
            _rect(0.0, -0.64, 0.05, 0.34),
        ]
    )
    templates.append(ShapeTemplate("Balloon", balloon))

    templates.append(ShapeTemplate("Star", _star(0.0, 0.02, 0.88, 0.36)))
    templates.append(ShapeTemplate("Heart", _heart(0.95, 0.05)))

    # Robot
    robot = _union(
        [
            _rect(0.0, 0.36, 0.48, 0.34),
            _rect(0.0, -0.06, 0.78, 0.56),
            _rect(-0.54, -0.04, 0.20, 0.40),
            _rect(0.54, -0.04, 0.20, 0.40),
            _rect(-0.18, -0.62, 0.18, 0.34),
            _rect(0.18, -0.62, 0.18, 0.34),
            _rect(0.0, 0.62, 0.06, 0.14),
            _circle(0.0, 0.72, 0.06),
        ]
    )
    templates.append(ShapeTemplate("Robot", robot))

    # Cloud
    cloud = _union(
        [
            _circle(-0.38, 0.02, 0.24),
            _circle(-0.12, 0.18, 0.28),
            _circle(0.18, 0.14, 0.26),
            _circle(0.44, 0.02, 0.20),
            _rect(0.0, -0.10, 1.02, 0.28),
        ]
    )
    templates.append(ShapeTemplate("Cloud", cloud))

    # Planet
    ring_band = _ellipse(0.0, -0.02, 0.82, 0.26, rot=-0.25)
    planet = _union([_circle(0.0, 0.0, 0.46), ring_band])
    templates.append(ShapeTemplate("Planet", planet))

    # Bird
    bird = _union(
        [
            _ellipse(-0.06, 0.00, 0.46, 0.30),
            _circle(0.36, 0.18, 0.14),
            _polygon([(0.50, 0.16), (0.78, 0.24), (0.50, 0.02)]),
            _ellipse(-0.22, 0.10, 0.28, 0.18, rot=-0.45),
            _rect(0.00, -0.42, 0.06, 0.22),
        ]
    )
    templates.append(ShapeTemplate("Bird", bird))

    # Teddy Bear
    teddy = _union(
        [
            _circle(-0.20, 0.46, 0.12),
            _circle(0.20, 0.46, 0.12),
            _circle(0.0, 0.28, 0.26),
            _ellipse(0.0, -0.12, 0.36, 0.34),
            _circle(-0.34, -0.06, 0.14),
            _circle(0.34, -0.06, 0.14),
            _circle(-0.16, -0.46, 0.14),
            _circle(0.16, -0.46, 0.14),
        ]
    )
    templates.append(ShapeTemplate("Teddy Bear", teddy))

    return templates


def mask_for_shape(shape_name: str, rng: random.Random | None = None) -> MaskFn:
    rng = rng or random.Random()
    templates = _build_templates(rng)
    for template in templates:
        if template.name == shape_name:
            return template.mask
    raise KeyError(f"Unknown shape: {shape_name}")


def all_shape_names() -> List[str]:
    fixed_rng = random.Random(12345)
    return [shape.name for shape in _build_templates(fixed_rng)]


def shape_sequence(total_pages: int, rng: random.Random, min_gap: int = 3) -> List[str]:
    names = all_shape_names()
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
            # Relax only when unavoidable.
            candidate = rng.choice(names)
            if not sequence or candidate != sequence[-1]:
                sequence.append(candidate)

    return sequence


def palette_sequence(total_pages: int, palettes: Iterable[str], rng: random.Random) -> List[str]:
    colors = list(palettes)
    if not colors:
        return []

    sequence: List[str] = []
    while len(sequence) < total_pages:
        rng.shuffle(colors)
        sequence.extend(colors)
    return sequence[:total_pages]
