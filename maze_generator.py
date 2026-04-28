"""Masked full-page scene-maze generation utilities."""

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


def _neighbors(cell: Cell, rows: int, cols: int) -> List[tuple[str, Cell]]:
    r, c = cell
    out: list[tuple[str, Cell]] = []
    for side, (dr, dc) in DIRS.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((side, (nr, nc)))
    return out


def _allowed_mask(rows: int, cols: int) -> Set[Cell]:
    """Centered, flowing worksheet mask that avoids icon zones."""
    allowed: Set[Cell] = set()

    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5) / cols
            y = (r + 0.5) / rows

            in_start_zone = x < 0.24 and y < 0.30
            in_finish_zone = x > 0.76 and y > 0.72

            in_main = 0.10 <= x <= 0.90 and 0.12 <= y <= 0.88
            top_right_arm = x >= 0.30 and y <= 0.62
            bottom_left_arm = x <= 0.70 and y >= 0.36
            connector = 0.34 <= y <= 0.64 and 0.28 <= x <= 0.72

            ok = in_main and (top_right_arm or bottom_left_arm or connector) and not in_start_zone and not in_finish_zone
            if ok:
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


def _add_loops(active: Set[Cell], walls: Dict[Cell, Dict[str, bool]], rows: int, cols: int, rng: random.Random, loop_factor: float) -> None:
    candidates: list[tuple[Cell, str, Cell]] = []
    for cell in active:
        for side, nxt in _neighbors(cell, rows, cols):
            if nxt not in active:
                continue
            if walls[cell][side]:
                rev = (nxt, OPPOSITE[side], cell)
                if rev not in candidates:
                    candidates.append((cell, side, nxt))

    rng.shuffle(candidates)
    open_count = int(len(candidates) * loop_factor)
    for cell, side, nxt in candidates[:open_count]:
        walls[cell][side] = False
        walls[nxt][OPPOSITE[side]] = False


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
) -> Maze:
    # Difficulty tuning focused on readability.
    if difficulty_factor <= 0.30:
        rows = max(16, min(rows, 20))
        cols = max(20, min(cols, 26))
        straight_pref = 0.82
        loop_factor = 0.24
    elif difficulty_factor <= 0.75:
        rows = max(22, min(rows, 28))
        cols = max(28, min(cols, 34))
        straight_pref = 0.54
        loop_factor = 0.14
    else:
        rows = max(28, min(rows, 34))
        cols = max(34, min(cols, 42))
        straight_pref = 0.24
        loop_factor = 0.07

    active = _allowed_mask(rows, cols)
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in active}

    start, start_side = _pick_opening(active, rows, cols, (int(rows * 0.14), int(cols * 0.24)), ("W", "N"))
    end, end_side = _pick_opening(active, rows, cols, (int(rows * 0.84), int(cols * 0.86)), ("E", "S"))

    _carve_masked_dfs(rows, cols, active, walls, start, rng, straight_preference=straight_pref)
    _add_loops(active, walls, rows, cols, rng, loop_factor)

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
        difficulty="",
    )
