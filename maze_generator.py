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

    # Edge bays vary silhouette without shrinking maze occupancy too much.
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
    # Difficulty tuning focused on visual differentiation.
    if difficulty_factor <= 0.30:
        profile = "easy"
        rows = max(14, min(rows + rng.randint(-1, 2), 18))
        cols = max(14, min(cols + rng.randint(-2, 2), 20))
        straight_pref = 0.88
        loop_factor = 0.16
        branch_bias = 0.68
    elif difficulty_factor <= 0.75:
        profile = "medium"
        rows = max(18, min(rows + rng.randint(-2, 2), 24))
        cols = max(20, min(cols + rng.randint(-3, 3), 30))
        straight_pref = 0.58
        loop_factor = 0.11
        branch_bias = 0.50
    else:
        profile = "hard"
        rows = max(24, min(rows + rng.randint(-2, 2), 32))
        cols = max(28, min(cols + rng.randint(-3, 3), 40))
        straight_pref = 0.28
        loop_factor = 0.06
        branch_bias = 0.35

    active = _allowed_mask(rows, cols, rng, profile)
    walls: Dict[Cell, Dict[str, bool]] = {cell: {"N": True, "S": True, "W": True, "E": True} for cell in active}

    side_to_target: dict[str, tuple[int, int]] = {
        "N": (0, cols // 2),
        "S": (rows - 1, cols // 2),
        "W": (rows // 2, 0),
        "E": (rows // 2, cols - 1),
    }
    # Prefer natural visual flow: start on left/top, finish on right/bottom.
    start_side_pref = rng.choice(["W", "N", "W", "N", "E", "S"])
    opposite = {"N": "S", "S": "N", "W": "E", "E": "W"}
    # Favor opposite-side exits for longer, more satisfying paths.
    all_sides = ["N", "S", "W", "E"]
    end_candidates = [s for s in all_sides if s != start_side_pref]
    weighted = [opposite[start_side_pref], opposite[start_side_pref], "E", "S"] + end_candidates
    end_side_pref = rng.choice(weighted)

    start, start_side = _pick_opening(
        active,
        rows,
        cols,
        side_to_target[start_side_pref],
        (start_side_pref, "W", "N", "E", "S"),
    )
    end, end_side = _pick_opening(
        active,
        rows,
        cols,
        side_to_target[end_side_pref],
        (end_side_pref, "E", "S", "W", "N"),
    )

    algorithm = rng.choice(["dfs", "prim", "kruskal", "biased"])
    if algorithm == "prim":
        _carve_prim(rows, cols, active, walls, start, rng, branch_bias=branch_bias)
    elif algorithm == "kruskal":
        _carve_kruskal(rows, cols, active, walls, rng)
    elif algorithm == "biased":
        _carve_masked_dfs(rows, cols, active, walls, start, rng, straight_preference=max(0.10, straight_pref * 0.72))
    else:
        _carve_masked_dfs(rows, cols, active, walls, start, rng, straight_preference=straight_pref)
    _add_loops(active, walls, rows, cols, rng, loop_factor)
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
