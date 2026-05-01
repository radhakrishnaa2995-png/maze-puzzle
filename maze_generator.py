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


def _shape_allowed_mask(rows: int, cols: int, rng: random.Random, profile: str, forced_shape: str | None = None) -> Set[Cell]:
    cy = (rows - 1) / 2.0
    cx = (cols - 1) / 2.0
    ry = max(1.0, rows * 0.46)
    rx = max(1.0, cols * 0.46)

    shapes = [
        "square", "rectangle", "diamond", "hexagon", "circle", "triangle",
        "octagon", "cross", "pentagon", "kite", "trapezoid",
        "parallelogram", "rhombus", "ellipse", "arrow"
    ]
    global _LAST_SHAPE
    candidates = [sh for sh in shapes if sh != _LAST_SHAPE] or shapes
    shape = forced_shape if forced_shape in shapes else rng.choice(candidates)
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
                inside = yn >= -0.9 and yn <= 0.9 and abs(xn) <= ((yn + 0.9) / 1.8) * 0.95
            elif shape == "octagon":
                inside = abs(xn) <= 0.92 and abs(yn) <= 0.92 and (abs(xn) + abs(yn)) <= 1.40
            elif shape == "cross":
                inside = (abs(xn) <= 0.30 and abs(yn) <= 0.94) or (abs(yn) <= 0.30 and abs(xn) <= 0.94)
            elif shape == "pentagon":
                inside = abs(xn) <= 0.92 and yn >= -0.92 and yn <= 0.92 and (abs(xn) * 0.55 + yn) <= 0.95
            elif shape == "kite":
                inside = (abs(xn) + abs(yn) * 0.68) <= 0.98 and yn <= 0.98
            elif shape == "trapezoid":
                half_w = 0.35 + ((0.92 - 0.35) * (0.95 - (yn + 1.0) * 0.5))
                inside = yn >= -0.9 and yn <= 0.9 and abs(xn) <= half_w
            elif shape == "parallelogram":
                sx = xn - (yn * 0.38)
                inside = abs(sx) <= 0.82 and abs(yn) <= 0.82
            elif shape == "rhombus":
                inside = abs(xn) * 0.85 + abs(yn) <= 0.98
            elif shape == "ellipse":
                inside = (xn * xn) / 1.0 + (yn * yn) / 0.62 <= 1.0
            else:  # arrow
                inside = (yn <= 0.15 and abs(xn) <= 0.30) or (yn > 0.15 and yn <= 0.92 and abs(xn) <= (0.96 - yn))

            if inside:
                allowed.add((r, c))

    return allowed


def _boundary_sides(cell: Cell, active: Set[Cell], rows: int, cols: int) -> List[str]:
    r, c = cell
    sides: list[str] = []
    for side, (dr, dc) in DIRS.items():
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols) or (nr, nc) not in active:
            sides.append(side)
    return sides


def _pick_corner_opening(active: Set[Cell], rows: int, cols: int, corner: str) -> tuple[Cell, str]:
    min_row = min(r for r, _ in active)
    max_row = max(r for r, _ in active)
    min_col = min(c for _, c in active)
    max_col = max(c for _, c in active)

    corner_specs = {
        "tl": ((min_row, min_col), ("N", "W")),
        "tr": ((min_row, max_col), ("N", "E")),
        "bl": ((max_row, min_col), ("S", "W")),
        "br": ((max_row, max_col), ("S", "E")),
    }
    target, preferred = corner_specs[corner]

    candidates: list[tuple[int, Cell, List[str]]] = []
    for cell in active:
        sides = _boundary_sides(cell, active, rows, cols)
        if not sides:
            continue
        dist = abs(cell[0] - target[0]) + abs(cell[1] - target[1])
        candidates.append((dist, cell, sides))

    candidates.sort(key=lambda x: x[0])
    for _, cell, sides in candidates:
        for pref in preferred:
            if pref in sides:
                return cell, pref
    return candidates[0][1], candidates[0][2][0]


def _carve_masked_dfs(rows: int, cols: int, active: Set[Cell], walls: Dict[Cell, Dict[str, bool]], start: Cell, rng: random.Random) -> None:
    visited: Set[Cell] = {start}
    stack: list[Cell] = [start]

    while stack:
        cur = stack[-1]
        options: list[tuple[str, Cell]] = []
        r, c = cur
        for side, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt in active and nxt not in visited:
                options.append((side, nxt))

        if not options:
            stack.pop()
            continue

        side, nxt = rng.choice(options)
        walls[cur][side] = False
        walls[nxt][OPPOSITE[side]] = False
        visited.add(nxt)
        stack.append(nxt)


def _force_connect(start: Cell, end: Cell, active: Set[Cell], walls: Dict[Cell, Dict[str, bool]], rows: int, cols: int) -> None:
    seen: Set[Cell] = {start}
    stack: list[Cell] = [start]
    while stack:
        cur = stack.pop()
        if cur == end:
            return
        r, c = cur
        for side, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt not in active or nxt in seen or walls[cur][side]:
                continue
            seen.add(nxt)
            stack.append(nxt)

    cur = start
    while cur != end:
        r, c = cur
        er, ec = end
        options: list[tuple[str, Cell, int]] = []
        for side, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt not in active:
                continue
            dist = abs(nxt[0] - er) + abs(nxt[1] - ec)
            options.append((side, nxt, dist))
        options.sort(key=lambda x: x[2])
        side, nxt, _ = options[0]
        walls[cur][side] = False
        walls[nxt][OPPOSITE[side]] = False
        cur = nxt


def maze_signature(maze: Maze) -> str:
    bits = []
    for cell in sorted(maze.active_cells):
        w = maze.walls[cell]
        bits.append(f"{cell[0]}:{cell[1]}:{int(w['N'])}{int(w['E'])}{int(w['S'])}{int(w['W'])}")
    return f"{maze.theme}|{maze.start}|{maze.end}|" + "|".join(bits)


def generate_maze(
    rows: int,
    cols: int,
    theme: str,
    difficulty_factor: float,
    rng: random.Random,
    start_anchor: str = "tl",
    end_anchor: str = "br",
    forced_shape: str | None = None,
) -> Maze:
    if difficulty_factor <= 0.30:
        rows = max(12, min(rows + rng.randint(-1, 1), 16))
        cols = max(12, min(cols + rng.randint(-1, 1), 16))
    elif difficulty_factor <= 0.75:
        rows = max(18, min(rows + rng.randint(-1, 2), 26))
        cols = max(20, min(cols + rng.randint(-1, 2), 30))
    else:
        rows = max(28, min(rows + rng.randint(0, 3), 36))
        cols = max(32, min(cols + rng.randint(0, 4), 44))

    active = _shape_allowed_mask(rows, cols, rng, "any", forced_shape=forced_shape)
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in active}

    start, start_side = _pick_corner_opening(active, rows, cols, start_anchor.lower() if start_anchor in {"tl", "tr", "bl", "br"} else "tl")
    end, end_side = _pick_corner_opening(active, rows, cols, end_anchor.lower() if end_anchor in {"tl", "tr", "bl", "br"} else "br")

    _carve_masked_dfs(rows, cols, active, walls, start, rng)
    _force_connect(start, end, active, walls, rows, cols)

    walls[start][start_side] = False
    walls[end][end_side] = False

    return Maze(
        rows=rows,
        cols=cols,
        theme=theme,
        walls=walls,
        active_cells=active,
        start=start,
        end=end,
        start_open_side=start_side,
        end_open_side=end_side,
        entry_opening=(start[0], start[1], start_side),
        exit_opening=(end[0], end[1], end_side),
        difficulty="",
    )
