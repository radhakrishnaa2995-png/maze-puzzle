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
from shapes import load_shapes, palette_sequence
from solver import solve_maze

PAGE_W, PAGE_H = A4

SAFE_LEFT = 0.85 * inch
SAFE_RIGHT = 0.85 * inch
SAFE_TOP = 0.85 * inch
SAFE_BOTTOM = 0.85 * inch

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),
    colors.HexColor("#FED7AA"),
    colors.HexColor("#E9D5FF"),
    colors.HexColor("#D1FAE5"),
    colors.HexColor("#FEF3C7"),
    colors.HexColor("#FBCFE8"),
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


def _shape_cycles(shape_dir: str, orientation_mode: str, seed: int) -> list[tuple[str, str]]:
    loaded = list(load_shapes(shape_dir, orientation_mode))
    if not loaded:
        raise ValueError("No shapes available")

    rng = random.Random(seed ^ 0xA5A5A5)
    first_cycle = loaded.copy()
    rng.shuffle(first_cycle)
    print(f"Loaded {len(first_cycle)} shapes")
    return [(s.name, s.source_file) for s in first_cycle]


def _build_shape_plan(pages: int, seed: int, shape_dir: str, orientation_mode: str) -> list[tuple[str, str]]:
    first_cycle = _shape_cycles(shape_dir, orientation_mode, seed)
    if pages > len(first_cycle):
        raise RuntimeError(
            f"Requested {pages} pages but only {len(first_cycle)} unique shapes are available. "
            "Reduce page count or add more shapes to avoid repeats."
        )

    # Strict no-repeat policy: one shape per page.
    plan = first_cycle[:pages]

    check = {src for _, src in plan}
    if len(check) != len(plan):
        raise RuntimeError("Shape usage verification failed: repeated shape detected in no-repeat mode")

    for i, (_, src) in enumerate(plan, start=1):
        print(f"Using shape {i}: {src}")

    return plan


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

    # Professional centered placement with equal inner margins and no clipping.
    inner_pad = 0.02 * min(fw, fh)
    usable_w = max(32.0, fw - (2 * inner_pad))
    usable_h = max(32.0, fh - (2 * inner_pad))
    cell = min(usable_w / vis_cols, usable_h / vis_rows)
    ox = fx + (fw - vis_cols * cell) / 2
    oy = fy + (fh - vis_rows * cell) / 2

    def box(rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = rc
        x0 = ox + (cc - min_c) * cell
        y0 = oy + (vis_rows - 1 - (r - min_r)) * cell
        return x0, y0, x0 + cell, y0 + cell

    # Darker, cleaner maze outline for better print visibility.
    c.setStrokeColor(colors.HexColor("#374151"))
    c.setLineWidth(max(0.50, cell * (0.055 if easy else 0.07)))

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

    c.setStrokeColor(colors.HexColor("#0B0F19"))
    c.setLineWidth(max(1.55, cell * 0.16))
    for seg in outer:
        c.line(*seg)

    for rc, side, col in [(maze.start, maze.start_open_side, colors.HexColor("#16A34A")), (maze.end, maze.end_open_side, colors.HexColor("#DC2626"))]:
        x0, y0, x1, y1 = box(rc)
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


def build_book(output_file: str, pages: int, seed: int, title: str, shape_dir: str = "assets/shapes", orientation_mode: str = "original") -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    bg_order = palette_sequence((pages * 2) + 10, PASTEL_PALETTE, rng)
    shape_plan = _build_shape_plan(pages, seed, shape_dir, orientation_mode)

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx in range(pages):
        page_no = idx + 1
        shape_name, _src = shape_plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)

        maze = None
        solution = []
        sig = ""
        for attempt in range(24):
            prng = _unique_rng(seed, page_no, shape_name, diff_name, attempt)
            candidate = generate_maze(rows, cols, shape_name, diff_factor, prng, shape_dir=shape_dir)
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
            prng = _unique_rng(seed, page_no, shape_name, diff_name, 999)
            maze = generate_maze(rows, cols, shape_name, diff_factor, prng, shape_dir=shape_dir)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, maze, solution))

        _draw_soft_background(c, bg_order[idx], rng)
        _draw_page_header(c, page_no, title)
        accent = ACCENTS[idx % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, page_no, diff_name, shape_name)
        _draw_maze(c, maze, fx, fy, fw, fh, show_solution=False, path=None, easy=(diff_name == "Easy"))
        c.showPage()

    _draw_soft_background(c, bg_order[pages], rng)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.63, "Solutions")
    c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        _draw_soft_background(c, bg_order[pages + i], rng)
        _draw_page_header(c, pages + i + 1, f"{title} • Solutions")
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.maze.shape)
        _draw_maze(c, puzzle.maze, fx, fy, fw, fh, show_solution=True, path=puzzle.solution, easy=False)
        c.showPage()

    c.save()
