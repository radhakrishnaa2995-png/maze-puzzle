# pdf_builder.py
"""Premium scene maze puzzle book PDF builder."""

from __future__ import annotations

import random
from dataclasses import dataclass
from hashlib import sha1
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs
from maze_generator import Maze, generate_maze, maze_signature
from shapes import palette_sequence
from solver import solve_maze

PAGE_W, PAGE_H = A4

SAFE_LEFT = 0.85 * inch
SAFE_RIGHT = 0.85 * inch
SAFE_TOP = 0.85 * inch
SAFE_BOTTOM = 0.85 * inch

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),  # baby blue
    colors.HexColor("#FED7AA"),  # peach
    colors.HexColor("#D1FAE5"),  # mint
    colors.HexColor("#FEF3C7"),  # cream
    colors.HexColor("#E9D5FF"),  # lavender
    colors.HexColor("#FBCFE8"),  # pink
]
ACCENTS = [
    colors.HexColor("#3B82F6"),
    colors.HexColor("#F97316"),
    colors.HexColor("#10B981"),
    colors.HexColor("#F59E0B"),
    colors.HexColor("#8B5CF6"),
    colors.HexColor("#EC4899"),
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    pair: IconPair
    maze: Maze
    solution: list[tuple[int, int]]


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    progress = (page_idx + 1) / max(1, total_pages)
    if progress <= 0.34:
        return "Easy", 14, 18, 0.18
    if progress <= 0.67:
        return "Medium", 18, 24, 0.55
    return "Hard", 22, 30, 0.92


def _icon_plan(pages: int, pairs: list[IconPair], seed: int) -> list[IconPair]:
    rng = random.Random(seed ^ 0xC0FFEE)
    out: list[IconPair] = []
    while len(out) < pages:
        cycle = pairs.copy()
        rng.shuffle(cycle)
        out.extend(cycle)
    return out[:pages]


def _draw_soft_background(c: canvas.Canvas, bg: colors.Color, rng: random.Random) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 22, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(2)
    c.roundRect(16, 16, PAGE_W - 32, PAGE_H - 32, 22, fill=0, stroke=1)
    for _ in range(16):
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.14))
        c.circle(rng.uniform(30, PAGE_W - 30), rng.uniform(30, PAGE_H - 30), rng.uniform(7, 14), fill=1, stroke=0)


def _draw_page_header(c: canvas.Canvas, page_no: int, title: str) -> None:
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(SAFE_LEFT, PAGE_H - SAFE_TOP + 14, title)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(PAGE_W - SAFE_RIGHT, PAGE_H - SAFE_TOP + 14, f"Page {page_no}")


def _title_block(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, theme_title: str) -> tuple[float, float, float, float]:
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
    c.setFont("Helvetica-Bold", 24)
    c.drawString(bar_x, bar_y - 30, theme_title)

    c.setFillColor(colors.HexColor("#64748B"))
    c.setFont("Helvetica", 10)
    c.drawString(bar_x, bar_y - 44, "Find the path from start icon to finish icon")

    top = bar_y - 58
    return SAFE_LEFT, SAFE_BOTTOM, PAGE_W - SAFE_LEFT - SAFE_RIGHT, top - SAFE_BOTTOM


def _fit_image_box(img_reader: ImageReader, max_w: float, max_h: float) -> tuple[float, float]:
    iw, ih = img_reader.getSize()
    if iw <= 0 or ih <= 0:
        return max_w, max_h
    scale = min(max_w / iw, max_h / ih)
    return iw * scale, ih * scale


def _draw_icon(c: canvas.Canvas, path: str, cx: float, cy: float, max_w: float, max_h: float) -> None:
    try:
        img = ImageReader(path)
        w, h = _fit_image_box(img, max_w, max_h)
        c.drawImage(img, cx - (w / 2), cy - (h / 2), width=w, height=h, preserveAspectRatio=True, mask="auto")
    except Exception:
        c.setFillColor(colors.HexColor("#CBD5E1"))
        c.roundRect(cx - (max_w / 2), cy - (max_h / 2), max_w, max_h, 8, fill=1, stroke=0)


def _draw_maze(c: canvas.Canvas, maze: Maze, fx: float, fy: float, fw: float, fh: float, show_solution: bool, path: list[tuple[int, int]] | None, start_icon: str, finish_icon: str) -> None:
    rows, cols = maze.rows, maze.cols
    icon_space = min(84.0, fw * 0.12)
    pad = 8.0

    grid_x = fx + icon_space + pad
    grid_w = fw - (2 * (icon_space + pad))
    grid_h = fh
    cell = min(grid_w / cols, grid_h / rows)
    maze_w = cols * cell
    maze_h = rows * cell
    ox = grid_x + (grid_w - maze_w) / 2
    oy = fy + (fh - maze_h) / 2

    def box(cell_rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = cell_rc
        x0 = ox + (cc * cell)
        y0 = oy + ((rows - 1 - r) * cell)
        return x0, y0, x0 + cell, y0 + cell

    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(max(0.9, cell * 0.12))

    # Internal walls
    for r in range(rows):
        for cc in range(cols):
            x0, y0, x1, y1 = box((r, cc))
            w = maze.walls[(r, cc)]
            if w["N"]:
                c.line(x0, y1, x1, y1)
            if w["S"]:
                c.line(x0, y0, x1, y0)
            if w["W"]:
                c.line(x0, y0, x0, y1)
            if w["E"]:
                c.line(x1, y0, x1, y1)

    # Thick outer border
    c.setStrokeColor(colors.HexColor("#0F172A"))
    c.setLineWidth(max(2.4, cell * 0.24))
    c.rect(ox, oy, maze_w, maze_h, fill=0, stroke=1)

    # Start/finish icon placement and labels
    start_x = fx + (icon_space * 0.55)
    finish_x = fx + fw - (icon_space * 0.55)
    icon_y = oy + (maze_h * 0.50)

    _draw_icon(c, start_icon, start_x, icon_y, icon_space, icon_space)
    _draw_icon(c, finish_icon, finish_x, icon_y, icon_space, icon_space)

    c.setFillColor(colors.HexColor("#16A34A"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(start_x, oy - 16, "START")

    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(finish_x, oy - 16, "FINISH")

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(2.0, cell * 0.26))
        points = []
        for r, cc in path:
            x0, y0, _, _ = box((r, cc))
            points.append((x0 + (cell / 2), y0 + (cell / 2)))
        for i in range(len(points) - 1):
            c.line(*points[i], *points[i + 1])


def _unique_rng(seed: int, page: int, theme_key: str, difficulty: str, attempt: int) -> random.Random:
    h = sha1(f"{seed}|{page}|{theme_key}|{difficulty}|{attempt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def build_book(output_file: str, pages: int, seed: int, title: str, icon_dir: str = "assets/icons") -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    pairs = load_icon_pairs(icon_dir)
    plan = _icon_plan(pages, pairs, seed)
    bg_order = palette_sequence((pages * 2) + 10, PASTEL_PALETTE, rng)

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx in range(pages):
        page_no = idx + 1
        pair = plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)

        maze = None
        solution: list[tuple[int, int]] = []
        sig = ""
        for attempt in range(30):
            prng = _unique_rng(seed, page_no, pair.key, diff_name, attempt)
            candidate = generate_maze(rows, cols, pair.key, diff_factor, prng)
            candidate.difficulty = diff_name
            candidate_path = solve_maze(candidate)
            if not candidate_path:
                continue
            sig = maze_signature(candidate)
            if sig in seen_signatures:
                continue
            maze = candidate
            solution = candidate_path
            break

        if maze is None:
            prng = _unique_rng(seed, page_no, pair.key, diff_name, 999)
            maze = generate_maze(rows, cols, pair.key, diff_factor, prng)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, pair, maze, solution))

        _draw_soft_background(c, bg_order[idx], rng)
        _draw_page_header(c, page_no, title)
        accent = ACCENTS[idx % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, page_no, diff_name, pair.title)
        _draw_maze(
            c,
            maze,
            fx,
            fy,
            fw,
            fh,
            show_solution=False,
            path=None,
            start_icon=str(pair.start_path),
            finish_icon=str(pair.finish_path),
        )
        c.showPage()

    # Solutions cover
    _draw_soft_background(c, bg_order[pages], rng)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.63, "Solutions")
    c.showPage()

    # Solution pages
    for i, puzzle in enumerate(puzzles, start=1):
        _draw_soft_background(c, bg_order[pages + i], rng)
        _draw_page_header(c, pages + i + 1, f"{title} • Solutions")
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.pair.title)
        _draw_maze(
            c,
            puzzle.maze,
            fx,
            fy,
            fw,
            fh,
            show_solution=True,
            path=puzzle.solution,
            start_icon=str(puzzle.pair.start_path),
            finish_icon=str(puzzle.pair.finish_path),
        )
        c.showPage()

    c.save()
