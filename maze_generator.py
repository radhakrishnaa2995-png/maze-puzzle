# maze_generator.py
"""Core maze generation using shape masks with clean entrances/exits."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from shapes import all_shape_names, mask_for_shape

Cell = Tuple[int, int]


@dataclass
class Maze:
    rows: int
    cols: int
    shape: str
    active_cells: Set[Cell]
    walls: Dict[Cell, Dict[str, bool]]
    start: Cell
    end: Cell
    start_open_side: str
    end_open_side: str
    difficulty: str


DIRS = {
    "N": (-1, 0),
    "S": (1, 0),
    "W": (0, -1),
    "E": (0, 1),
}
OPPOSITE = {"N": "S", "S": "N", "W": "E", "E": "W"}


def _center(rows: int, cols: int, r: int, c: int) -> tuple[float, float]:
    return ((c + 0.5) / cols) * 2 - 1, ((r + 0.5) / rows) * 2 - 1


def _largest_component(cells: Set[Cell]) -> Set[Cell]:
    if not cells:
        return set()
    unseen = set(cells)
    biggest: Set[Cell] = set()

    while unseen:
        seed = unseen.pop()
        stack = [seed]
        comp = {seed}
        while stack:
            r, c = stack.pop()
            for dr, dc in DIRS.values():
                nxt = (r + dr, c + dc)
                if nxt in unseen:
                    unseen.remove(nxt)
                    comp.add(nxt)
                    stack.append(nxt)
        if len(comp) > len(biggest):
            biggest = comp

    return biggest


def _mask_cells(rows: int, cols: int, shape_fn, sample_radius: float) -> Set[Cell]:
    offsets = [(0.0, 0.0)]
    if sample_radius > 0:
        offsets.extend([(sample_radius, 0.0), (-sample_radius, 0.0), (0.0, sample_radius), (0.0, -sample_radius)])

    cells: Set[Cell] = set()
    for r in range(rows):
        for c in range(cols):
            x, y = _center(rows, cols, r, c)
            if any(shape_fn(x + dx, y + dy) for dx, dy in offsets):
                cells.add((r, c))

    return _largest_component(cells)


def _adapt_grid(rows: int, cols: int, shape_fn) -> tuple[int, int, Set[Cell]]:
    sr = 0.0
    rr, cc = rows, cols
    best_cells: Set[Cell] = set()
    for _ in range(7):
        cells = _mask_cells(rr, cc, shape_fn, sr)
        best_cells = cells if len(cells) > len(best_cells) else best_cells
        if len(cells) >= 80 and len(cells) / max(1, rr * cc) >= 0.06:
            return rr, cc, cells
        rr = int(rr * 1.28)
        cc = int(cc * 1.28)
        sr = min(0.04, sr + 0.01)
    return rr, cc, best_cells


def _boundary_candidates(cells: Set[Cell], side: str) -> list[Cell]:
    out: list[Cell] = []
    dr, dc = DIRS[side]
    for r, c in cells:
        if (r + dr, c + dc) not in cells:
            out.append((r, c))
    return out


def _pick_entrances(cells: Set[Cell], rng: random.Random) -> tuple[Cell, str, Cell, str]:
    west = _boundary_candidates(cells, "W")
    east = _boundary_candidates(cells, "E")

    if west and east:
        start = min(west, key=lambda rc: (rc[1], abs(rc[0])))
        end = max(east, key=lambda rc: (rc[1], -abs(rc[0])))
        if start == end:
            end = rng.choice([c for c in east if c != start] or east)
        return start, "W", end, "E"

    # fallback opposite exposed sides
    all_exposed: list[tuple[Cell, str]] = []
    for side in DIRS:
        all_exposed.extend((cell, side) for cell in _boundary_candidates(cells, side))
    a_cell, a_side = rng.choice(all_exposed)
    opposite = OPPOSITE[a_side]
    b_candidates = _boundary_candidates(cells - {a_cell}, opposite) or _boundary_candidates(cells, opposite)
    b_cell = rng.choice(b_candidates) if b_candidates else rng.choice(list(cells - {a_cell} or cells))
    b_side = opposite if b_candidates else rng.choice(list(DIRS.keys()))
    return a_cell, a_side, b_cell, b_side


def _carve_dfs(cells: Set[Cell], walls: Dict[Cell, Dict[str, bool]], start: Cell, rng: random.Random, branch_bias: float) -> None:
    visited = {start}
    stack = [start]
    while stack:
        r, c = stack[-1]
        choices: list[tuple[str, Cell]] = []
        for d, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt in cells and nxt not in visited:
                choices.append((d, nxt))

        if not choices:
            stack.pop()
            continue

        # Harder mazes: less straight preference, more branching.
        if len(stack) > 1 and rng.random() < branch_bias:
            prev = stack[-2]
            current_dir = (r - prev[0], c - prev[1])
            straight = [item for item in choices if (item[1][0] - r, item[1][1] - c) == current_dir]
            if straight:
                choices = straight + [c for c in choices if c not in straight]

        d, nxt = rng.choice(choices)
        walls[(r, c)][d] = False
        walls[nxt][OPPOSITE[d]] = False
        visited.add(nxt)
        stack.append(nxt)


def _add_loops(cells: Set[Cell], walls: Dict[Cell, Dict[str, bool]], rng: random.Random, loop_factor: float) -> None:
    candidates: list[tuple[Cell, str, Cell]] = []
    for r, c in cells:
        for d, (dr, dc) in DIRS.items():
            nxt = (r + dr, c + dc)
            if nxt in cells and walls[(r, c)][d]:
                if (nxt, OPPOSITE[d], (r, c)) not in candidates:
                    candidates.append(((r, c), d, nxt))

    rng.shuffle(candidates)
    open_count = int(len(candidates) * loop_factor)
    for cell, d, nxt in candidates[:open_count]:
        walls[cell][d] = False
        walls[nxt][OPPOSITE[d]] = False


def maze_signature(maze: Maze) -> str:
    wall_bits = []
    for cell in sorted(maze.active_cells):
        w = maze.walls[cell]
        wall_bits.append(f"{cell[0]}:{cell[1]}:{int(w['N'])}{int(w['E'])}{int(w['S'])}{int(w['W'])}")
    return f"{maze.shape}|{maze.start}|{maze.end}|" + "|".join(wall_bits)


def generate_maze(
    rows: int,
    cols: int,
    shape: str,
    difficulty_factor: float,
    rng: random.Random,
    shape_dir: str = "assets/shapes",
) -> Maze:
    try:
        shape_fn = mask_for_shape(shape, shape_dir=shape_dir)
    except KeyError:
        available = all_shape_names(shape_dir)
        if not available:
            raise
        shape = available[0]
        shape_fn = mask_for_shape(shape, shape_dir=shape_dir)
    rows, cols, cells = _adapt_grid(rows, cols, shape_fn)

    if len(cells) < 12:
        cells = {(r, c) for r in range(4, 16) for c in range(4, 20)}

    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in cells}

    start, start_side, end, end_side = _pick_entrances(cells, rng)

    # Difficulty controls
    straight_bias = max(0.05, 0.70 - difficulty_factor * 0.65)
    loop_factor = min(0.28, max(0.0, (difficulty_factor - 0.35) * 0.55))

    _carve_dfs(cells, walls, start, rng, branch_bias=straight_bias)
    _add_loops(cells, walls, rng, loop_factor=loop_factor)

    # Clean, visible openings.
    walls[start][start_side] = False
    walls[end][end_side] = False

    return Maze(
        rows=rows,
        cols=cols,
        shape=shape,
        active_cells=cells,
        walls=walls,
        start=start,
        end=end,
        start_open_side=start_side,
        end_open_side=end_side,
        difficulty="",
    )
