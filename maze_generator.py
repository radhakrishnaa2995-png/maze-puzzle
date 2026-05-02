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
    """Generate noticeably different puzzle silhouettes."""
    cy = (rows - 1) / 2.0
    cx = (cols - 1) / 2.0
    ry = max(1.0, rows * 0.46)
    rx = max(1.0, cols * 0.46)
    shapes = ["square", "rectangle", "diamond", "hexagon", "circle", "triangle", "octagon", "cross", "pentagon", "kite", "trapezoid", "parallelogram", "rhombus", "ellipse", "arrow"]
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

    # Keep silhouettes organic with edge notches.
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


def _boundary_sides(cell: Cell, active: Set[Cell], rows: int, cols: int) -> List[str]:
    r, c = cell
    sides: list[str] = []
    for side, (dr, dc) in DIRS.items():
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols) or (nr, nc) not in active:
            sides.append(side)
    return sides


def _active_bounds(active: Set[Cell]) -> tuple[int, int, int, int]:
    rows = [r for r, _ in active]
    cols = [c for _, c in active]
    return min(rows), max(rows), min(cols), max(cols)


def _pick_opening(active: Set[Cell], rows: int, cols: int, target: tuple[int, int], preferred: tuple[str, str]) -> tuple[Cell, str]:
    tr, tc = target
    candidates: list[tuple[int, Cell, List[str]]] = []
    for cell in active:
        sides = _boundary_sides(cell, active, rows, cols)
        if not sides:
            continue
        dist = abs(cell[0] - tr) + abs(cell[1] - tc)
        candidates.append((dist, cell, sides))

    candidates.sort(key=lambda x: x[0])
    for _dist, cell, sides in candidates:
        for pref in preferred:
            if pref in sides:
                return cell, pref
    if candidates:
        return candidates[0][1], candidates[0][2][0]

    any_cell = next(iter(active))
    return any_cell, "W"


def _pick_opening_on_side(active: Set[Cell], rows: int, cols: int, side: str, target_row: int) -> tuple[Cell, str]:
    candidates: list[tuple[int, Cell]] = []
    min_row, max_row, min_col, max_col = _active_bounds(active)
    for cell in active:
        r, c = cell
        if side == "W" and c != min_col:
            continue
        if side == "E" and c != max_col:
            continue
        if side == "N" and r != min_row:
            continue
        if side == "S" and r != max_row:
            continue
        sides = _boundary_sides(cell, active, rows, cols)
        if side in sides:
            candidates.append((abs(cell[0] - target_row), cell))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1], side
    # Fallback should be rare; preserve validity with closest boundary opening.
    pref = (side, "W", "E", "N", "S")
    return _pick_opening(active, rows, cols, (target_row, cols // 2), pref)


def _pick_corner_opening(active: Set[Cell], rows: int, cols: int, corner: str) -> tuple[Cell, str]:
    min_row, max_row, min_col, max_col = _active_bounds(active)
    corner_specs = {
        "tl": ((min_row, min_col), ("N", "W")),
        "tr": ((min_row, max_col), ("N", "E")),
        "bl": ((max_row, min_col), ("S", "W")),
        "br": ((max_row, max_col), ("S", "E")),
    }
    target, preferred = corner_specs[corner]
    candidates: list[tuple[int, Cell, List[str]]] = []
    for cell in active:
        r, c = cell
        if corner == "tl" and not (r == min_row or c == min_col):
            continue
        if corner == "tr" and not (r == min_row or c == max_col):
            continue
        if corner == "bl" and not (r == max_row or c == min_col):
            continue
        if corner == "br" and not (r == max_row or c == max_col):
            continue
        sides = _boundary_sides(cell, active, rows, cols)
        if not sides:
            continue
        dist = abs(r - target[0]) + abs(c - target[1])
        candidates.append((dist, cell, sides))

    candidates.sort(key=lambda x: x[0])
    for _dist, cell, sides in candidates:
        for pref in preferred:
            if pref in sides:
                return cell, pref
    if candidates:
        return candidates[0][1], candidates[0][2][0]
    return _pick_opening(active, rows, cols, target, preferred)


def _carve_masked_dfs(
    rows: int,
    cols: int,
    active: Set[Cell],
    walls: Dict[Cell, Dict[str, bool]],
    start: Cell,
    rng: random.Random,
    straight_preference: float,
) -> None:
    visited: Set[Cell] = {start}
    stack: list[Cell] = [start]
    prev_dir: dict[Cell, str] = {}

    while stack:
        cur = stack[-1]
        options: list[tuple[str, Cell]] = []
        for side, nxt in _neighbors(cur, rows, cols):
            if nxt in active and nxt not in visited:
                options.append((side, nxt))

        if not options:
            stack.pop()
            continue

        if rng.random() < straight_preference and cur in prev_dir:
            straight = [opt for opt in options if opt[0] == prev_dir[cur]]
            side, nxt = rng.choice(straight or options)
        else:
            side, nxt = rng.choice(options)

        walls[cur][side] = False
        walls[nxt][OPPOSITE[side]] = False
        prev_dir[nxt] = side
        visited.add(nxt)
        stack.append(nxt)


def _carve_prim(
    rows: int,
    cols: int,
    active: Set[Cell],
    walls: Dict[Cell, Dict[str, bool]],
    start: Cell,
    rng: random.Random,
    branch_bias: float,
) -> None:
    visited: Set[Cell] = {start}
    frontier: list[tuple[Cell, str, Cell]] = []
    for side, nxt in _neighbors(start, rows, cols):
        if nxt in active:
            frontier.append((start, side, nxt))

    while frontier:
        idx = 0 if (rng.random() < branch_bias) else rng.randrange(len(frontier))
        cur, side, nxt = frontier.pop(idx)
        if nxt in visited:
            continue

        walls[cur][side] = False
        walls[nxt][OPPOSITE[side]] = False
        visited.add(nxt)

        for nside, nn in _neighbors(nxt, rows, cols):
            if nn in active and nn not in visited:
                frontier.append((nxt, nside, nn))


def _path_exists(start: Cell, end: Cell, active: Set[Cell], walls: Dict[Cell, Dict[str, bool]], rows: int, cols: int) -> bool:
    seen: Set[Cell] = {start}
    stack: list[Cell] = [start]
    while stack:
        cur = stack.pop()
        if cur == end:
            return True
        for side, nxt in _neighbors(cur, rows, cols):
            if nxt not in active or nxt in seen:
                continue
            if walls[cur][side]:
                continue
            seen.add(nxt)
            stack.append(nxt)
    return False


def _force_connect(start: Cell, end: Cell, active: Set[Cell], walls: Dict[Cell, Dict[str, bool]], rows: int, cols: int) -> None:
    """Guarantee entry->exit connectivity by carving a direct rescue tunnel when needed."""
    if _path_exists(start, end, active, walls, rows, cols):
        return

    cur = start
    guard = 0
    while cur != end and guard < (rows * cols * 3):
        guard += 1
        r, c = cur
        er, ec = end
        options: list[tuple[str, Cell, int]] = []
        for side, nxt in _neighbors(cur, rows, cols):
            if nxt not in active:
                continue
            dist = abs(nxt[0] - er) + abs(nxt[1] - ec)
            options.append((side, nxt, dist))
        if not options:
            break
        options.sort(key=lambda x: x[2])
        side, nxt, _ = options[0]
        walls[cur][side] = False
        walls[nxt][OPPOSITE[side]] = False
        cur = nxt


def _carve_kruskal(
    rows: int,
    cols: int,
    active: Set[Cell],
    walls: Dict[Cell, Dict[str, bool]],
    rng: random.Random,
) -> None:
    parent: Dict[Cell, Cell] = {cell: cell for cell in active}
    rank: Dict[Cell, int] = {cell: 0 for cell in active}

    def find(x: Cell) -> Cell:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: Cell, b: Cell) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            parent[ra] = rb
        elif rank[ra] > rank[rb]:
            parent[rb] = ra
        else:
            parent[rb] = ra
            rank[ra] += 1
        return True

    edges: list[tuple[Cell, str, Cell]] = []
    for cell in active:
        for side, nxt in _neighbors(cell, rows, cols):
            if nxt not in active:
                continue
            if cell < nxt:
                edges.append((cell, side, nxt))

    rng.shuffle(edges)
    for cell, side, nxt in edges:
        if union(cell, nxt):
            walls[cell][side] = False
            walls[nxt][OPPOSITE[side]] = False



def _largest_connected_component(cells: Set[Cell], rows: int, cols: int) -> Set[Cell]:
    if not cells:
        return set()
    remaining = set(cells)
    largest: Set[Cell] = set()
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        component = {seed}
        while stack:
            cur = stack.pop()
            for _side, nxt in _neighbors(cur, rows, cols):
                if nxt in remaining:
                    remaining.remove(nxt)
                    component.add(nxt)
                    stack.append(nxt)
        if len(component) > len(largest):
            largest = component
    return largest

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
    # Difficulty tuning focused on visual differentiation.
    if difficulty_factor <= 0.30:
        profile = "easy"
        rows = max(12, min(rows + rng.randint(-1, 1), 16))
        cols = max(12, min(cols + rng.randint(-1, 1), 16))
        straight_pref = 0.72
        branch_bias = 0.75
    elif difficulty_factor <= 0.75:
        profile = "medium"
        rows = max(18, min(rows + rng.randint(-1, 2), 26))
        cols = max(20, min(cols + rng.randint(-1, 2), 30))
        straight_pref = 0.44
        branch_bias = 0.48
    else:
        profile = "hard"
        rows = max(28, min(rows + rng.randint(0, 3), 36))
        cols = max(32, min(cols + rng.randint(0, 4), 44))
        straight_pref = 0.18
        branch_bias = 0.25

    # Use geometric silhouette masks by default for clearer requested shape variety.
    active = _shape_allowed_mask(rows, cols, rng, profile, forced_shape=forced_shape)
    active = _largest_connected_component(active, rows, cols)
    if not active:
        active = {(r, c) for r in range(rows) for c in range(cols)}
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in active}

    # Architecture rule: choose entry/exit from intended image flow first.
    anchor_side = {
        "left": "W",
        "right": "E",
        "top": "N",
        "bottom": "S",
        "tl": "N",
        "tr": "N",
        "bl": "S",
        "br": "S",
        "l": "W",
        "r": "E",
        "t": "N",
        "b": "S",
    }
    start_key = start_anchor.lower()
    end_key = end_anchor.lower()
    if start_key in {"tl", "tr", "bl", "br"}:
        start, start_side = _pick_corner_opening(active, rows, cols, start_key)
    else:
        start_side_pref = anchor_side.get(start_key, "W")
        start, start_side = _pick_opening_on_side(active, rows, cols, start_side_pref, target_row=rows // 2)

    if end_key in {"tl", "tr", "bl", "br"}:
        end, end_side = _pick_corner_opening(active, rows, cols, end_key)
    else:
        end_side_pref = anchor_side.get(end_key, "E")
        end, end_side = _pick_opening_on_side(active, rows, cols, end_side_pref, target_row=rows // 2)

    if end_side == start_side:
        alternative = "E" if start_side != "E" else "W"
        end, end_side = _pick_opening_on_side(active, rows, cols, alternative, target_row=rows // 2)

    algorithm = "dfs"
    if algorithm == "prim":
        _carve_prim(rows, cols, active, walls, start, rng, branch_bias=branch_bias)
    elif algorithm == "kruskal":
        _carve_kruskal(rows, cols, active, walls, rng)
    elif algorithm == "biased":
        _carve_masked_dfs(rows, cols, active, walls, start, rng, straight_preference=max(0.10, straight_pref * 0.72))
    else:
        _carve_masked_dfs(rows, cols, active, walls, start, rng, straight_preference=straight_pref)
    # Keep a single-solution maze (tree): do not add extra loops.
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
