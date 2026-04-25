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
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _ellipse(cx: float, cy: float, rx: float, ry: float, rot: float = 0.0) -> MaskFn:
    c, s = math.cos(rot), math.sin(rot)

    def fn(x: float, y: float) -> bool:
        tx, ty = x - cx, y - cy
        xr = tx * c + ty * s
        yr = -tx * s + ty * c
        return (xr * xr) / (rx * rx + 1e-9) + (yr * yr) / (ry * ry + 1e-9) <= 1

    return fn


def _rect(cx: float, cy: float, w: float, h: float) -> MaskFn:
    return lambda x, y: abs(x - cx) <= w / 2 and abs(y - cy) <= h / 2


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
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return _polygon(pts)


def _heart(scale: float = 1.0, shift_y: float = 0.02) -> MaskFn:
    def fn(x: float, y: float) -> bool:
        sx = x / max(0.1, scale)
        sy = (y - shift_y) / max(0.1, scale)
        return (sx * sx + sy * sy - 1) ** 3 - sx * sx * sy**3 <= 0 and sy <= 1.05

    return fn


def _union(parts: Iterable[MaskFn]) -> MaskFn:
    parts = list(parts)
    return lambda x, y: any(p(x, y) for p in parts)


def _build_templates(rng: random.Random) -> List[ShapeTemplate]:
    j = lambda s=0.03: rng.uniform(-s, s)
    templates: List[ShapeTemplate] = []

    # Dinosaur (triceratops-like profile)
    dino_outline = _polygon(
        [
            (-0.95, 0.15), (-0.82, 0.26), (-0.66, 0.24), (-0.54, 0.38), (-0.30, 0.44),
            (-0.05, 0.48), (0.24, 0.42), (0.48, 0.28), (0.64, 0.16), (0.88, 0.08),
            (0.96, -0.02), (0.82, -0.08), (0.56, -0.12), (0.52, -0.32), (0.40, -0.52),
            (0.20, -0.50), (0.14, -0.24), (-0.10, -0.24), (-0.16, -0.54), (-0.34, -0.54),
            (-0.44, -0.30), (-0.62, -0.20), (-0.84, -0.10), (-0.96, 0.02),
        ]
    )
    horn = _polygon([(-0.94, 0.24), (-1.02, 0.34), (-0.90, 0.33)])
    templates.append(ShapeTemplate("Dinosaur", _union([dino_outline, horn])))

    rocket = _union([
        _ellipse(0.0, 0.02, 0.33 + j(0.02), 0.70 + j(0.03)),
        _polygon([(0.0, 0.98), (-0.20, 0.58), (0.20, 0.58)]),
        _polygon([(-0.32, -0.14), (-0.60, -0.42), (-0.18, -0.36)]),
        _polygon([(0.32, -0.14), (0.60, -0.42), (0.18, -0.36)]),
        _polygon([(-0.10, -0.66), (0.10, -0.66), (0.0, -0.98)]),
    ])
    templates.append(ShapeTemplate("Rocket", rocket))

    animal = _union([
        _ellipse(-0.06, -0.04, 0.56, 0.31), _circle(0.40, 0.16, 0.19),
        _polygon([(0.28, 0.28), (0.36, 0.54), (0.46, 0.30)]),
        _polygon([(0.44, 0.30), (0.58, 0.54), (0.58, 0.28)]),
        _rect(-0.30, -0.46, 0.14, 0.30), _rect(-0.02, -0.46, 0.14, 0.30), _rect(0.24, -0.46, 0.14, 0.30),
        _ellipse(-0.58, 0.18, 0.28, 0.08, rot=0.8),
    ])
    templates.append(ShapeTemplate("Animal", animal))

    templates.append(ShapeTemplate("Butterfly", _union([
        _ellipse(-0.35, 0.22, 0.33, 0.30), _ellipse(0.35, 0.22, 0.33, 0.30),
        _ellipse(-0.30, -0.30, 0.35, 0.25), _ellipse(0.30, -0.30, 0.35, 0.25),
        _rect(0.0, -0.02, 0.16, 0.76),
    ])))

    templates.append(ShapeTemplate("Fish", _union([
        _ellipse(-0.10, -0.02, 0.62, 0.36), _polygon([(0.48, 0.0), (0.96, 0.34), (0.96, -0.34)]),
        _polygon([(-0.12, 0.34), (0.14, 0.66), (0.22, 0.30)]),
    ])))

    train = _union([
        _rect(-0.08, -0.08, 1.60, 0.50),
        _rect(0.52, 0.18, 0.42, 0.34),
        _rect(0.64, 0.44, 0.16, 0.20),
        _circle(-0.62, -0.38, 0.17), _circle(-0.20, -0.38, 0.17), _circle(0.24, -0.38, 0.17), _circle(0.66, -0.38, 0.17),
    ])
    templates.append(ShapeTemplate("Train", train))

    car = _union([
        _rect(0.0, -0.16, 1.46, 0.46),
        _polygon([(-0.58, 0.04), (-0.24, 0.34), (0.34, 0.34), (0.62, 0.04)]),
        _circle(-0.44, -0.36, 0.20), _circle(0.44, -0.36, 0.20),
    ])
    templates.append(ShapeTemplate("Car", car))

    castle = _union([
        _rect(0.0, -0.06, 1.36, 0.76), _rect(-0.54, 0.34, 0.30, 0.48), _rect(0.54, 0.34, 0.30, 0.48),
        _rect(-0.26, 0.44, 0.14, 0.16), _rect(0.0, 0.44, 0.14, 0.16), _rect(0.26, 0.44, 0.14, 0.16),
    ])
    templates.append(ShapeTemplate("Castle", castle))

    templates.append(ShapeTemplate("Tree", _union([
        _rect(0.0, -0.56, 0.28, 0.60), _circle(0.0, 0.14, 0.45), _circle(-0.32, 0.04, 0.30), _circle(0.32, 0.04, 0.30), _circle(0.0, 0.42, 0.28),
    ])))

    templates.append(ShapeTemplate("Flower", _union([
        _circle(0.0, 0.10, 0.24), _circle(0.0, 0.50, 0.22), _circle(0.0, -0.30, 0.22),
        _circle(-0.40, 0.10, 0.22), _circle(0.40, 0.10, 0.22), _circle(-0.30, 0.36, 0.20), _circle(0.30, 0.36, 0.20),
        _rect(0.0, -0.64, 0.12, 0.46),
    ])))

    templates.append(ShapeTemplate("Ice Cream", _union([
        _circle(-0.20, 0.34, 0.27), _circle(0.20, 0.34, 0.27), _circle(0.0, 0.52, 0.26), _polygon([(-0.30, 0.14), (0.30, 0.14), (0.0, -0.92)]),
    ])))

    templates.append(ShapeTemplate("Balloon", _union([
        _ellipse(0.0, 0.20, 0.44, 0.56), _polygon([(-0.08, -0.30), (0.08, -0.30), (0.0, -0.46)]), _rect(0.0, -0.66, 0.05, 0.34),
    ])))

    templates.append(ShapeTemplate("Star", _star(0.0, 0.04, 0.92, 0.38)))
    templates.append(ShapeTemplate("Heart", _heart(0.98, 0.05)))

    robot = _union([
        _rect(0.0, 0.40, 0.56, 0.34),
        _rect(0.0, -0.04, 0.92, 0.60),
        _rect(-0.62, -0.06, 0.22, 0.42), _rect(0.62, -0.06, 0.22, 0.42),
        _rect(-0.20, -0.70, 0.20, 0.34), _rect(0.20, -0.70, 0.20, 0.34),
        _rect(0.0, 0.66, 0.06, 0.12), _circle(0.0, 0.75, 0.06),
    ])
    templates.append(ShapeTemplate("Robot", robot))

    templates.append(ShapeTemplate("Cloud", _union([
        _circle(-0.40, 0.04, 0.25), _circle(-0.14, 0.20, 0.30), _circle(0.18, 0.16, 0.28), _circle(0.46, 0.04, 0.22), _rect(0.0, -0.12, 1.10, 0.30),
    ])))

    templates.append(ShapeTemplate("Planet", _union([_circle(0.0, 0.02, 0.48), _ellipse(0.0, -0.02, 0.88, 0.28, rot=-0.25)])))

    templates.append(ShapeTemplate("Bird", _union([
        _ellipse(-0.08, 0.00, 0.50, 0.32), _circle(0.38, 0.18, 0.14), _polygon([(0.52, 0.16), (0.84, 0.24), (0.52, 0.02)]),
        _ellipse(-0.24, 0.10, 0.30, 0.19, rot=-0.45), _rect(0.00, -0.44, 0.06, 0.24),
    ])))

    teddy = _union([
        _circle(-0.22, 0.56, 0.13), _circle(0.22, 0.56, 0.13),
        _circle(0.0, 0.36, 0.28), _ellipse(0.0, -0.08, 0.40, 0.38),
        _circle(-0.38, -0.06, 0.16), _circle(0.38, -0.06, 0.16),
        _ellipse(-0.20, -0.56, 0.16, 0.14), _ellipse(0.20, -0.56, 0.16, 0.14),
    ])
    templates.append(ShapeTemplate("Teddy Bear", teddy))

    return templates


def mask_for_shape(shape_name: str, rng: random.Random | None = None) -> MaskFn:
    rng = rng or random.Random()
    for template in _build_templates(rng):
        if template.name == shape_name:
            return template.mask
    raise KeyError(f"Unknown shape: {shape_name}")


def all_shape_names() -> List[str]:
    return [shape.name for shape in _build_templates(random.Random(12345))]


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
            candidate = rng.choice(names)
            if not sequence or candidate != sequence[-1]:
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
