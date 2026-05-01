"""Masked full-page scene-maze generation utilities with algorithm variation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

Cell = Tuple[int, int]


@dataclass
class Maze:
    rows: int
    cols: int
    theme: str
    walls: Dict[Cell, Dict[str, bool]]
    active_cells: Set[Cell]
    start: Cell
    end: Cell
    start_open_side: str
    end_open_side: str
    entry_opening: tuple[int, int, str]
    exit_opening: tuple[int, int, str]
    difficulty: str

    @property
    def valid_cells(self) -> Set[Cell]:
        return self.active_cells

    def is_valid(self, r: int, c: int) -> bool:
        return (r, c) in self.active_cells


DIRS = {
    "N": (-1, 0),
    "S": (1, 0),
    "W": (0, -1),
    "E": (0, 1),
}
OPPOSITE = {"N": "S", "S": "N", "W": "E", "E": "W"}
_LAST_SHAPE: str | None = None


def _neighbors(cell: Cell, rows: int, cols: int) -> List[tuple[str, Cell]]:
    r, c = cell
    out: list[tuple[str, Cell]] = []
    for side, (dr, dc) in DIRS.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((side, (nr, nc)))
    return out


def _allowed_mask(rows: int, cols: int, rng: random.Random, profile: str) -> Set[Cell]:
    """Create large masks with light edge carving so mazes stay page-dominant yet unique."""
    allowed: Set[Cell] = {(r, c) for r in range(rows) for c in range(cols)}

    bay_count = {"easy": 2, "medium": 3, "hard": 4}.get(profile, 3)
    for _ in range(bay_count):
        side = rng.choice(["N", "S", "W", "E"])
        depth = rng.randint(1, max(2, rows // 10 if side in {"N", "S"} else cols // 10))
        span = rng.randint(max(3, cols // 8 if side in {"N", "S"} else rows // 8), max(4, cols // 4 if side in {"N", "S"} else rows // 4))

        if side in {"N", "S"}:
            start_c = rng.randint(1, max(1, cols - span - 1))
            rr = range(0, depth) if side == "N" else range(rows - depth, rows)
            for r in rr:
                for c in range(start_c, min(cols - 1, start_c + span)):
                    allowed.discard((r, c))
        else:
            start_r = rng.randint(1, max(1, rows - span - 1))
            cc = range(0, depth) if side == "W" else range(cols - depth, cols)
            for c in cc:
                for r in range(start_r, min(rows - 1, start_r + span)):
                    allowed.discard((r, c))

    return allowed


def _shape_allowed_mask(rows: int, cols: int, rng: random.Random, profile: str) -> Set[Cell]:
    """Generate noticeably different puzzle silhouettes."""
    cy = (rows - 1) / 2.0
    cx = (cols - 1) / 2.0
    ry = max(1.0, rows * 0.46)
    rx = max(1.0, cols * 0.46)
    shapes = ["square", "rectangle", "diamond", "hexagon", "circle", "triangle", "octagon", "cross", "pentagon", "kite", "trapezoid"]
    global _LAST_SHAPE
    candidates = [sh for sh in shapes if sh != _LAST_SHAPE] or shapes
    shape = rng.choice(candidates)
    _LAST_SHAPE = shape
    allowed: Set[Cell] = set()

    for r in range(rows):
        for c in range(cols):
            yn = (r - cy) / ry
            xn = (c - cx) / rx
            inside = False
            if shape == "circle":
                inside = (xn * xn) + (yn * yn) <= 1.0
            elif shape == "diamond":
                inside = abs(xn) + abs(yn) <= 1.0
            elif shape == "square":
                inside = abs(xn) <= 0.88 and abs(yn) <= 0.88
            elif shape == "rectangle":
                inside = abs(xn) <= 0.96 and abs(yn) <= 0.62
            elif shape == "hexagon":
                inside = abs(xn) <= 0.90 and abs(yn) <= 0.86 and (abs(xn) * 0.58 + abs(yn)) <= 1.0
            elif shape == "triangle":
                # Upward-facing triangle: broad base at bottom, apex at top.
                inside = yn >= -0.9 and yn <= 0.9 and abs(xn) <= ((yn + 0.9) / 1.8) * 0.95
            elif shape == "octagon":
                inside = abs(xn) <= 0.92 and abs(yn) <= 0.92 and (abs(xn) + abs(yn)) <= 1.40
            elif shape == "cross":
                inside = (abs(xn) <= 0.30 and abs(yn) <= 0.94) or (abs(yn) <= 0.30 and abs(xn) <= 0.94)
            elif shape == "pentagon":
                inside = abs(xn) <= 0.92 and yn >= -0.92 and yn <= 0.92 and (abs(xn) * 0.55 + yn) <= 0.95
            elif shape == "kite":
                inside = (abs(xn) + abs(yn) * 0.68) <= 0.98 and yn <= 0.98
            else:  # trapezoid
                half_w = 0.35 + ((0.92 - 0.35) * (0.95 - (yn + 1.0) * 0.5))
                inside = yn >= -0.9 and yn <= 0.9 and abs(xn) <= half_w

            if inside:
                allowed.add((r, c))

    carve_count = {"easy": 2, "medium": 3, "hard": 4}.get(profile, 3)
    for _ in range(carve_count):
        side = rng.choice(["N", "S", "W", "E"])
        depth = rng.randint(1, max(2, rows // 12 if side in {"N", "S"} else cols // 12))
        span = rng.randint(
            max(3, cols // 10 if side in {"N", "S"} else rows // 10),
            max(4, cols // 4 if side in {"N", "S"} else rows // 4),
        )
        if side in {"N", "S"}:
            start_c = rng.randint(1, max(1, cols - span - 1))
            rr = range(0, depth) if side == "N" else range(rows - depth, rows)
            for r in rr:
                for c in range(start_c, min(cols - 1, start_c + span)):
                    allowed.discard((r, c))
        else:
            start_r = rng.randint(1, max(1, rows - span - 1))
            cc = range(0, depth) if side == "W" else range(cols - depth, cols)
            for c in cc:
                for r in range(start_r, min(rows - 1, start_r + span)):
                    allowed.discard((r, c))

    return allowed

# ... (rest of file unchanged up to generate_maze)

def generate_maze(
    rows: int,
    cols: int,
    theme: str,
    difficulty_factor: float,
    rng: random.Random,
    start_anchor: str = "tl",
    end_anchor: str = "br",
) -> Maze:
    if difficulty_factor <= 0.30:
        profile = "easy"
        rows = max(12, min(rows + rng.randint(-1, 1), 16))
        cols = max(12, min(cols + rng.randint(-1, 1), 16))
        straight_pref = 0.72
        loop_factor = 0.18
        branch_bias = 0.75
    elif difficulty_factor <= 0.75:
        profile = "medium"
        rows = max(18, min(rows + rng.randint(-1, 2), 26))
        cols = max(20, min(cols + rng.randint(-1, 2), 30))
        straight_pref = 0.44
        loop_factor = 0.10
        branch_bias = 0.48
    else:
        profile = "hard"
        rows = max(28, min(rows + rng.randint(0, 3), 36))
        cols = max(32, min(cols + rng.randint(0, 4), 44))
        straight_pref = 0.18
        loop_factor = 0.04
        branch_bias = 0.25

    # Use geometric silhouette masks by default for clearer requested shape variety.
    active = _shape_allowed_mask(rows, cols, rng, profile)
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in active}

    # ... opening selection unchanged ...

    if profile == "hard":
        algorithm = rng.choice(["kruskal", "prim", "dfs"])
    elif profile == "medium":
        algorithm = rng.choice(["dfs", "prim", "kruskal", "biased"])
    else:
        algorithm = rng.choice(["dfs", "prim", "biased"])

    # ... rest unchanged ...
