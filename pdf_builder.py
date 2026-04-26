# pdf_builder.py
"""PDF composition for premium printable maze books."""

from __future__ import annotations

import random
from dataclasses import dataclass
from hashlib import sha1
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from maze_generator import Maze, generate_maze, maze_signature
from shapes import palette_sequence, shape_sequence
from solver import solve_maze

PAGE_W, PAGE_H = A4

SAFE_LEFT = 1.0 * inch
SAFE_RIGHT = 1.0 * inch
SAFE_TOP = 0.9 * inch
SAFE_BOTTOM = 0.9 * inch

PASTEL_PALETTE = [
    colors.HexColor("#FCE7F3"),
    colors.HexColor("#E0E7FF"),
    colors.HexColor("#DCFCE7"),
    colors.HexColor("#FEF3C7"),
    colors.HexColor("#DBEAFE"),
    colors.HexColor("#FAE8FF"),
]

ACCENTS = [
    colors.HexColor("#4F46E5"),
    colors.HexColor("#0F766E"),
    colors.HexColor("#C2410C"),
    colors.HexColor("#7C3AED"),
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    maze: Maze
    solution: list[tuple[int, int]]


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    # 1-30% easy, 31-70% medium, 71-100% hard
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.30:
        return "Easy", 33, 33, 0.18
    if progress <= 0.70:
        return "Medium", 45, 45, 0.56
    return "Hard", 59, 59, 0.92


def _draw_background(c: canvas.Canvas, bg: colors.Color, page_number: int, title: str, rng: random.Random) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 20, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#0F172A"))
    c.setLineWidth(2.2)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 20, fill=0, stroke=1)

    for _ in range(20):
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.14))
        c.circle(rng.uniform(32, PAGE_W - 32), rng.uniform(32, PAGE_H - 32), rng.uniform(6, 15), stroke=0, fill=1)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(SAFE_LEFT, PAGE_H - SAFE_TOP + 12, title)
    c.setFont("Helvetica", 10)
    c.drawRightString(PAGE_W - SAFE_RIGHT, PAGE_H - SAFE_TOP + 12, f"Page {page_number}")


def _draw_arrow(c: canvas.Canvas, px: float, py: float, side: str, color: colors.Color) -> None:
    c.setFillColor(color)
    if side == "N":
        pts = [px, py + 18, px - 7, py + 6, px + 7, py + 6]
    elif side == "S":
        pts = [px, py - 18, px - 7, py - 6, px + 7, py - 6]
    elif side == "W":
        pts = [px - 18, py, px - 6, py - 7, px - 6, py + 7]
    else:
        pts = [px + 18, py, px + 6, py - 7, px + 6, py + 7]

    path = c.beginPath()
    path.moveTo(pts[0], pts[1])
    path.lineTo(pts[2], pts[3])
    path.lineTo(pts[4], pts[5])
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def _draw_maze(c: canvas.Canvas, maze: Maze, frame_x: float, frame_y: float, frame_w: float, frame_h: float, show_solution: bool, path: list[tuple[int, int]] | None) -> None:
    min_r = min(r for r, _ in maze.active_cells)
    max_r = max(r for r, _ in maze.active_cells)
    min_c = min(col for _, col in maze.active_cells)
    max_c = max(col for _, col in maze.active_cells)

    vis_rows = max_r - min_r + 1
    vis_cols = max_c - min_c + 1

    cell = min(frame_w / vis_cols, frame_h / vis_rows)
    ox = frame_x + (frame_w - (vis_cols * cell)) / 2
    oy = frame_y + (frame_h - (vis_rows * cell)) / 2

    def box(cell_rc: tuple[int, int]) -> tuple[float, float, float, float]:
        rr, cc = cell_rc
        local_r = rr - min_r
        local_c = cc - min_c
        x0 = ox + local_c * cell
        y0 = oy + (vis_rows - 1 - local_r) * cell
        return x0, y0, x0 + cell, y0 + cell

    c.setStrokeColor(colors.HexColor("#666666"))
    c.setLineCap(1)
    c.setLineWidth(max(0.4, cell * 0.06))

    border_segments: list[tuple[float, float, float, float]] = []

    for cell_rc in maze.active_cells:
        r, col = cell_rc
        x0, y0, x1, y1 = box(cell_rc)
        w = maze.walls[cell_rc]

        if w["N"]:
            c.line(x0, y1, x1, y1)
        if w["S"]:
            c.line(x0, y0, x1, y0)
        if w["W"]:
            c.line(x0, y0, x0, y1)
        if w["E"]:
            c.line(x1, y0, x1, y1)

        for side, (dr, dc), seg in [
            ("N", (-1, 0), (x0, y1, x1, y1)),
            ("S", (1, 0), (x0, y0, x1, y0)),
            ("W", (0, -1), (x0, y0, x0, y1)),
            ("E", (0, 1), (x1, y0, x1, y1)),
        ]:
            if (r + dr, col + dc) in maze.active_cells:
                continue
            if cell_rc == maze.start and side == maze.start_open_side:
                continue
            if cell_rc == maze.end and side == maze.end_open_side:
                continue
            border_segments.append(seg)

    c.setStrokeColor(colors.HexColor("#111827"))
    c.setLineWidth(max(1.4, cell * 0.14))
    for seg in border_segments:
        c.line(*seg)

    for cell_rc, side, col in [
        (maze.start, maze.start_open_side, colors.HexColor("#16A34A")),
        (maze.end, maze.end_open_side, colors.HexColor("#DC2626")),
    ]:
        x0, y0, x1, y1 = box(cell_rc)
        if side == "N":
            px, py = x0 + cell / 2, y1
        elif side == "S":
            px, py = x0 + cell / 2, y0
        elif side == "W":
            px, py = x0, y0 + cell / 2
        else:
            px, py = x1, y0 + cell / 2
        _draw_arrow(c, px, py, side, col)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#E11D48"))
        c.setLineWidth(max(1.6, cell * 0.17))
        pts = []
        for rr, cc in path:
            x0, y0, _, _ = box((rr, cc))
            pts.append((x0 + cell / 2, y0 + cell / 2))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _title_bar(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, shape: str) -> tuple[float, float, float, float]:
    bar_x = SAFE_LEFT
    bar_w = PAGE_W - SAFE_LEFT - SAFE_RIGHT
    bar_h = 34
    bar_y = PAGE_H - SAFE_TOP - bar_h - 8

    c.setFillColor(accent)
    c.roundRect(bar_x, bar_y, bar_w, bar_h, 10, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(bar_x + 12, bar_y + 20, f"Puzzle {puzzle_no} • {difficulty}")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 19)
    c.drawString(bar_x, bar_y - 26, f"{shape} Maze")

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 10)
    c.drawString(bar_x, bar_y - 40, "Green arrow = start entrance • Red arrow = finish exit")

    top = bar_y - 52
    bottom = SAFE_BOTTOM
    return SAFE_LEFT, bottom, PAGE_W - SAFE_LEFT - SAFE_RIGHT, top - bottom


def _unique_rng(seed: int, page: int, shape: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{shape}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(output_file: str, pages: int, seed: int, title: str, shape_dir: str = "assets/shapes") -> None:
    base_rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    shape_order = shape_sequence(pages, base_rng, shape_dir=shape_dir, min_gap=4)
    bg_order = palette_sequence((pages * 2) + 4, PASTEL_PALETTE, base_rng)

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for page_idx in range(pages):
        page_no = page_idx + 1
        difficulty, rows, cols, diff_factor = _difficulty_for_page(page_idx, pages)
        shape = shape_order[page_idx]

        maze = None
        solution = []
        sig = ""
        for attempt in range(20):
            page_rng = _unique_rng(seed, page_no, shape, difficulty, attempt)
            candidate = generate_maze(rows, cols, shape, diff_factor, page_rng, shape_dir=shape_dir)
            candidate.difficulty = difficulty
            path = solve_maze(candidate)
            if not path:
                continue
            sig = maze_signature(candidate)
            if sig in seen_signatures:
                continue
            maze = candidate
            solution = path
            break

        if maze is None:
            page_rng = _unique_rng(seed, page_no, shape, difficulty, 999)
            maze = generate_maze(rows, cols, shape, diff_factor, page_rng, shape_dir=shape_dir)
            maze.difficulty = difficulty
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, maze, solution))

        accent = ACCENTS[page_idx % len(ACCENTS)]
        _draw_background(c, bg_order[page_idx], page_no, title, base_rng)
        frame_x, frame_y, frame_w, frame_h = _title_bar(c, accent, page_no, difficulty, shape)
        _draw_maze(c, maze, frame_x, frame_y, frame_w, frame_h, show_solution=False, path=None)
        c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        _draw_background(c, bg_order[pages + i], pages + i, f"{title} • Solutions", base_rng)
        frame_x, frame_y, frame_w, frame_h = _title_bar(c, accent, puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.maze.shape)
        _draw_maze(c, puzzle.maze, frame_x, frame_y, frame_w, frame_h, show_solution=True, path=puzzle.solution)
        c.showPage()

    c.save()
