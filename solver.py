"""Maze solver utilities (BFS shortest-path for puzzle and solution pages)."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple

from maze_generator import DIRS, Maze

Cell = Tuple[int, int]


def _valid_cells(maze: Maze) -> Set[Cell]:
    # Compatibility: support both masked-maze naming styles.
    cells = getattr(maze, "valid_cells", None)
    if cells is None:
        cells = getattr(maze, "active_cells", set())
    return set(cells)


def solve_maze(maze: Maze) -> List[Cell]:
    valid_cells = _valid_cells(maze)

    if maze.start not in valid_cells:
        print(f"Warning: solver start cell is invalid and was skipped: {maze.start}")
        return []
    if maze.end not in valid_cells:
        print(f"Warning: solver end cell is invalid and was skipped: {maze.end}")
        return []

    q = deque([maze.start])
    parent: Dict[Cell, Cell | None] = {maze.start: None}

    while q:
        cur = q.popleft()
        if cur not in valid_cells:
            print(f"Warning: solver encountered invalid cell and skipped it: {cur}")
            continue

        if cur == maze.end:
            break

        walls = maze.walls.get(cur)
        if not walls:
            print(f"Warning: solver missing wall data for cell and skipped it: {cur}")
            continue

        r, c = cur
        for side, (dr, dc) in DIRS.items():
            if side not in walls:
                continue
            if walls[side]:
                continue

            nxt = (r + dr, c + dc)
            if nxt not in valid_cells:
                continue
            if nxt not in maze.walls:
                print(f"Warning: solver missing wall data for neighbor and skipped it: {nxt}")
                continue

            if nxt not in parent:
                parent[nxt] = cur
                q.append(nxt)

    if maze.end not in parent:
        return []

    path: List[Cell] = []
    node: Cell | None = maze.end
    while node is not None:
        path.append(node)
        node = parent[node]
    path.reverse()
    return path
