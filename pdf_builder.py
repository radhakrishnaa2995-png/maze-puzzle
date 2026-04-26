# pdf_builder.py
"""Premium PDF composition for maze puzzle books."""

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

SAFE_LEFT = 1.05 * inch
SAFE_RIGHT = 1.05 * inch
SAFE_TOP = 0.95 * inch
SAFE_BOTTOM = 0.95 * inch

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),  # soft blue
    colors.HexColor("#FED7AA"),  # peach
    colors.HexColor("#E9D5FF"),  # lavender
    colors.HexColor("#D1FAE5"),  # mint
    colors.HexColor("#FEF3C7"),  # cream
    colors.HexColor("#FBCFE8"),  # blush pink
]

ACCENTS = [
    colors.HexColor("#3B82F6"),
    colors.HexColor("#F97316"),
    colors.HexColor("#8B5CF6"),
    colors.HexColor("#10B981"),
    colors.HexColor("#F59E0B"),
    colors.HexColor("#EC4899"),
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    maze: Maze
    solution: list[tuple[int, int]]


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.35:
        return "Easy", 31, 31, 0.18
    if progress <= 0.70:
        return "Medium", 43, 43, 0.56
    return "Hard", 57, 57, 0.95


def _draw_soft_background(c: canvas.Canvas, bg: colors.Color, rng: random.Random) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 22, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(2)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 22, fill=0, stroke=1)

    for _ in range(18):
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.16))
        c.circle(rng.uniform(30, PAGE_W - 30), rng.uniform(30, PAGE_H - 30), rng.uniform(6, 14), fill=1, stroke=0)


def _draw_cover(c: canvas.Canvas, rng: random.Random, bg: colors.Color) -> None:
    _draw_soft_background(c, bg, rng)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.66, "Maze Puzzle Book for Kids")

    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.59, "Easy • Medium • Hard")

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.53, "Fun shape mazes for young puzzle explorers")
    c.showPage()


def _draw_instructions(c: canvas.Canvas, rng: random.Random, bg: colors.Color) -> None:
    _draw_soft_background(c, bg, rng)
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 28)
    c.drawString(SAFE_LEFT, PAGE_H - SAFE_TOP - 20, "How to Play")

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#374151"))
    lines = [
        "1. Start at the green arrow.",
        "2. Trace a path through the maze.",
        "3. Reach the red arrow to finish.",
        "4. Stuck? Check the solutions section at the end.",
    ]
    y = PAGE_H - SAFE_TOP - 65
    for ln in lines:
        c.drawString(SAFE_LEFT, y, ln)
        y -= 28
    c.showPage()


def _draw_page_header(c: canvas.Canvas, page_no: int, title: str) -> None:
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(SAFE_LEFT, PAGE_H - SAFE_TOP + 14, title)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(PAGE_W - SAFE_RIGHT, PAGE_H - SAFE_TOP + 14, f"Page {page_no}")


def _draw_arrow(c: canvas.Canvas, px: float, py: float, side: str, color: colors.Color) -> None:
    c.setFillColor(color)
    if side == "N":
        pts = [px, py + 18, px - 8, py + 6, px + 8, py + 6]
    elif side == "S":
        pts = [px, py - 18, px - 8, py - 6, px + 8, py - 6]
    elif side == "W":
        pts = [px - 18, py, px - 6, py - 8, px - 6, py + 8]
    else:
        pts = [px + 18, py, px + 6, py - 8, px + 6, py + 8]

    p = c.beginPath()
    p.moveTo(pts[0], pts[1])
    p.lineTo(pts[2], pts[3])
    p.lineTo(pts[4], pts[5])
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _draw_maze(c: canvas.Canvas, maze: Maze, fx: float, fy: float, fw: float, fh: float, show_solution: bool, path: list[tuple[int, int]] | None, easy: bool) -> None:
    min_r = min(r for r, _ in maze.active_cells)
    max_r = max(r for r, _ in maze.active_cells)
    min_c = min(cc for _, cc in maze.active_cells)
    max_c = max(cc for _, cc in maze.active_cells)

    vis_rows = max_r - min_r + 1
    vis_cols = max_c - min_c + 1
    cell = min(fw / vis_cols, fh / vis_rows)
    ox = fx + (fw - vis_cols * cell) / 2
    oy = fy + (fh - vis_rows * cell) / 2

    def box(rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = rc
        x0 = ox + (cc - min_c) * cell
        y0 = oy + (vis_rows - 1 - (r - min_r)) * cell
        return x0, y0, x0 + cell, y0 + cell

    c.setStrokeColor(colors.HexColor("#6B7280"))
    c.setLineWidth(max(0.35, cell * (0.045 if easy else 0.06)))

    outer = []
    for rc in maze.active_cells:
        r, cc = rc
        x0, y0, x1, y1 = box(rc)
        w = maze.walls[rc]

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
            if (r + dr, cc + dc) in maze.active_cells:
                continue
            if rc == maze.start and side == maze.start_open_side:
                continue
            if rc == maze.end and side == maze.end_open_side:
                continue
            outer.append(seg)

    c.setStrokeColor(colors.HexColor("#111827"))
    c.setLineWidth(max(1.35, cell * 0.14))
    for seg in outer:
        c.line(*seg)

    for rc, side, color in [
        (maze.start, maze.start_open_side, colors.HexColor("#16A34A")),
        (maze.end, maze.end_open_side, colors.HexColor("#DC2626")),
    ]:
        x0, y0, x1, y1 = box(rc)
        if side == "N":
            px, py = x0 + cell / 2, y1
        elif side == "S":
            px, py = x0 + cell / 2, y0
        elif side == "W":
            px, py = x0, y0 + cell / 2
        else:
            px, py = x1, y0 + cell / 2
        _draw_arrow(c, px, py, side, color)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#E11D48"))
        c.setLineWidth(max(1.4, cell * 0.16))
        pts = []
        for r, cc in path:
            x0, y0, _, _ = box((r, cc))
            pts.append((x0 + cell / 2, y0 + cell / 2))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _title_block(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, shape: str) -> tuple[float, float, float, float]:
    bar_x = SAFE_LEFT
    bar_w = PAGE_W - SAFE_LEFT - SAFE_RIGHT
    bar_h = 36
    bar_y = PAGE_H - SAFE_TOP - bar_h - 8

    c.setFillColor(accent)
    c.roundRect(bar_x, bar_y, bar_w, bar_h, 11, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(bar_x + 14, bar_y + 22, f"Puzzle {puzzle_no} • {difficulty}")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(bar_x, bar_y - 28, f"{shape} Maze")

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 10)
    c.drawString(bar_x, bar_y - 42, "Start at green arrow • Finish at red arrow")

    top = bar_y - 56
    return SAFE_LEFT, SAFE_BOTTOM, PAGE_W - SAFE_LEFT - SAFE_RIGHT, top - SAFE_BOTTOM


def _unique_rng(seed: int, page: int, shape: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{shape}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(output_file: str, pages: int, seed: int, title: str, shape_dir: str = "assets/shapes") -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    bg_order = palette_sequence((pages * 2) + 10, PASTEL_PALETTE, rng)
    shape_order = shape_sequence(pages, rng, shape_dir=shape_dir, min_gap=5)

    _draw_cover(c, rng, bg_order[0])
    _draw_instructions(c, rng, bg_order[1])

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx in range(pages):
        page_no = idx + 1
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)
        shape = shape_order[idx]

        maze = None
        solution = []
        sig = ""
        for attempt in range(24):
            prng = _unique_rng(seed, page_no, shape, diff_name, attempt)
            candidate = generate_maze(rows, cols, shape, diff_factor, prng, shape_dir=shape_dir)
            candidate.difficulty = diff_name
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
            prng = _unique_rng(seed, page_no, shape, diff_name, 999)
            maze = generate_maze(rows, cols, shape, diff_factor, prng, shape_dir=shape_dir)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, maze, solution))

        _draw_soft_background(c, bg_order[idx + 2], rng)
        _draw_page_header(c, page_no, title)

        accent = ACCENTS[idx % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, page_no, diff_name, shape)
        _draw_maze(c, maze, fx, fy, fw, fh, show_solution=False, path=None, easy=(diff_name == "Easy"))
        c.showPage()

    _draw_soft_background(c, bg_order[pages + 3], rng)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.63, "Solutions")
    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.57, "Check your route and try again for perfect runs!")
    c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        _draw_soft_background(c, bg_order[pages + 3 + i], rng)
        _draw_page_header(c, pages + 3 + i, f"{title} • Solutions")
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.maze.shape)
        _draw_maze(c, puzzle.maze, fx, fy, fw, fh, show_solution=True, path=puzzle.solution, easy=False)
        c.showPage()

    _draw_soft_background(c, bg_order[-1], rng)
    c.setFillColor(colors.HexColor("#065F46"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, "Great Job!")
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.55, "You completed the maze challenge book.")
    c.showPage()

    c.save()
