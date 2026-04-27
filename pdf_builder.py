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
from maze_generator import DIRS, Maze, generate_maze, maze_signature
from solver import solve_maze

PAGE_W, PAGE_H = A4

# Requested page margins.
SAFE_LEFT = 0.45 * inch
SAFE_RIGHT = 0.45 * inch
SAFE_TOP = 0.45 * inch
SAFE_BOTTOM = 0.45 * inch

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),  # pastel blue
    colors.HexColor("#FBCFE8"),  # pastel pink
    colors.HexColor("#FED7AA"),  # pastel peach
    colors.HexColor("#D1FAE5"),  # pastel mint
    colors.HexColor("#E9D5FF"),  # pastel lavender
    colors.HexColor("#FEF3C7"),  # pastel cream
]
ACCENTS = [
    colors.HexColor("#2563EB"),
    colors.HexColor("#DB2777"),
    colors.HexColor("#EA580C"),
    colors.HexColor("#059669"),
    colors.HexColor("#7C3AED"),
    colors.HexColor("#CA8A04"),
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
        return "Easy", 13, 16, 0.18
    if progress <= 0.67:
        return "Medium", 17, 22, 0.56
    return "Hard", 21, 28, 0.92


def _palette_cycle(total: int, rng: random.Random) -> list[colors.Color]:
    base = PASTEL_PALETTE.copy()
    out: list[colors.Color] = []
    while len(out) < total:
        rng.shuffle(base)
        out.extend(base)
    return out[:total]


def _icon_plan(pages: int, pairs: list[IconPair], seed: int) -> list[IconPair]:
    rng = random.Random(seed ^ 0xC0FFEE)
    out: list[IconPair] = []
    while len(out) < pages:
        cycle = pairs.copy()
        rng.shuffle(cycle)
        out.extend(cycle)
    return out[:pages]


def _draw_background(c: canvas.Canvas, bg: colors.Color, rng: random.Random) -> None:
    # Full-page background color as requested.
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Premium thin rounded border inside margins.
    inner_x = SAFE_LEFT * 0.55
    inner_y = SAFE_BOTTOM * 0.55
    inner_w = PAGE_W - (inner_x * 2)
    inner_h = PAGE_H - (inner_y * 2)
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.5)
    c.roundRect(inner_x, inner_y, inner_w, inner_h, 16, fill=0, stroke=1)

    # Soft decorations.
    for _ in range(20):
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.10))
        c.circle(rng.uniform(20, PAGE_W - 20), rng.uniform(20, PAGE_H - 20), rng.uniform(5, 13), fill=1, stroke=0)


def _draw_bottom_page_no(c: canvas.Canvas, page_no: int) -> None:
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAGE_W / 2, SAFE_BOTTOM * 0.35, f"Page {page_no}")


def _title_block(c: canvas.Canvas, accent: colors.Color, puzzle_no: int, difficulty: str, theme_title: str) -> tuple[float, float, float, float]:
    title_x = SAFE_LEFT
    title_w = PAGE_W - SAFE_LEFT - SAFE_RIGHT
    title_h = 44
    title_y = PAGE_H - SAFE_TOP - title_h

    c.setFillColor(accent)
    c.roundRect(title_x, title_y, title_w, title_h, 14, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(title_x + 16, title_y + 27, f"Puzzle {puzzle_no} • {difficulty}")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 28)
    c.drawString(title_x, title_y - 34, theme_title)

    content_top = title_y - 48
    content_bottom = SAFE_BOTTOM + 22
    return SAFE_LEFT, content_bottom, title_w, content_top - content_bottom


def _fit_image_box(img_reader: ImageReader, max_w: float, max_h: float) -> tuple[float, float]:
    iw, ih = img_reader.getSize()
    if iw <= 0 or ih <= 0:
        return max_w, max_h
    scale = min(max_w / iw, max_h / ih)
    return iw * scale, ih * scale


def _draw_icon(c: canvas.Canvas, path: str, cx: float, cy: float, size: float) -> None:
    try:
        img = ImageReader(path)
        w, h = _fit_image_box(img, size, size)
        c.drawImage(img, cx - (w / 2), cy - (h / 2), width=w, height=h, preserveAspectRatio=True, mask="auto")
    except Exception:
        c.setFillColor(colors.HexColor("#CBD5E1"))
        c.roundRect(cx - (size / 2), cy - (size / 2), size, size, 10, fill=1, stroke=0)


def _anchor_icon_point(anchor: str, maze_x: float, maze_y: float, maze_w: float, maze_h: float, gap: float) -> tuple[float, float]:
    if anchor == "tl":
        return maze_x - gap, maze_y + maze_h + gap
    if anchor == "tr":
        return maze_x + maze_w + gap, maze_y + maze_h + gap
    if anchor == "bl":
        return maze_x - gap, maze_y - gap
    if anchor == "br":
        return maze_x + maze_w + gap, maze_y - gap
    if anchor == "left":
        return maze_x - gap, maze_y + (maze_h / 2)
    if anchor == "right":
        return maze_x + maze_w + gap, maze_y + (maze_h / 2)
    return maze_x - gap, maze_y + (maze_h / 2)


def _draw_maze(c: canvas.Canvas, maze: Maze, fx: float, fy: float, fw: float, fh: float, show_solution: bool, path: list[tuple[int, int]] | None, pair: IconPair) -> None:
    rows, cols = maze.rows, maze.cols

    # Use 65-75% area for maze body (target ~70%).
    max_maze_w = fw * 0.74
    max_maze_h = fh * 0.72
    cell = min(max_maze_w / cols, max_maze_h / rows)

    maze_w = cols * cell
    maze_h = rows * cell
    maze_x = fx + (fw - maze_w) / 2
    maze_y = fy + (fh - maze_h) / 2

    def box(cell_rc: tuple[int, int]) -> tuple[float, float, float, float]:
        r, cc = cell_rc
        x0 = maze_x + (cc * cell)
        y0 = maze_y + ((rows - 1 - r) * cell)
        return x0, y0, x0 + cell, y0 + cell

    # Medium internal walls.
    c.setStrokeColor(colors.HexColor("#1F2937"))
    c.setLineWidth(max(0.85, cell * 0.10))

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

    # Thick outer walls with real openings preserved.
    c.setStrokeColor(colors.black)
    c.setLineWidth(max(2.2, cell * 0.23))
    for r in range(rows):
        for cc in range(cols):
            x0, y0, x1, y1 = box((r, cc))
            w = maze.walls[(r, cc)]
            if r == 0 and w["N"]:
                c.line(x0, y1, x1, y1)
            if r == rows - 1 and w["S"]:
                c.line(x0, y0, x1, y0)
            if cc == 0 and w["W"]:
                c.line(x0, y0, x0, y1)
            if cc == cols - 1 and w["E"]:
                c.line(x1, y0, x1, y1)

    icon_size = min(90.0, max(56.0, min(fw, fh) * 0.16))
    icon_gap = (icon_size * 0.55)

    sx, sy = _anchor_icon_point(pair.start_anchor, maze_x, maze_y, maze_w, maze_h, icon_gap)
    ex, ey = _anchor_icon_point(pair.end_anchor, maze_x, maze_y, maze_w, maze_h, icon_gap)

    _draw_icon(c, str(pair.start_path), sx, sy, icon_size)
    _draw_icon(c, str(pair.finish_path), ex, ey, icon_size)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#DC2626"))
        c.setLineWidth(max(1.9, cell * 0.24))
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
    bg_order = _palette_cycle((pages * 2) + 12, rng)

    puzzles: List[PuzzlePage] = []
    seen_signatures: set[str] = set()

    for idx in range(pages):
        page_no = idx + 1
        pair = plan[idx]
        diff_name, rows, cols, diff_factor = _difficulty_for_page(idx, pages)

        maze = None
        solution: list[tuple[int, int]] = []
        sig = ""

        for attempt in range(42):
            prng = _unique_rng(seed, page_no, pair.key, diff_name, attempt)
            candidate = generate_maze(
                rows,
                cols,
                pair.key,
                diff_factor,
                prng,
                start_anchor=pair.start_anchor,
                end_anchor=pair.end_anchor,
            )
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
            maze = generate_maze(rows, cols, pair.key, diff_factor, prng, pair.start_anchor, pair.end_anchor)
            maze.difficulty = diff_name
            solution = solve_maze(maze)
            sig = maze_signature(maze)

        seen_signatures.add(sig)
        puzzles.append(PuzzlePage(page_no, pair, maze, solution))

        _draw_background(c, bg_order[idx], rng)
        accent = ACCENTS[idx % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, page_no, diff_name, pair.title)
        _draw_maze(c, maze, fx, fy, fw, fh, show_solution=False, path=None, pair=pair)
        _draw_bottom_page_no(c, page_no)
        c.showPage()

    # Solutions cover
    _draw_background(c, bg_order[pages], rng)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(PAGE_W / 2, PAGE_H * 0.62, "Solutions")
    _draw_bottom_page_no(c, pages + 1)
    c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        _draw_background(c, bg_order[pages + i], rng)
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        fx, fy, fw, fh = _title_block(c, accent, puzzle.puzzle_number, puzzle.maze.difficulty, puzzle.pair.title)
        _draw_maze(c, puzzle.maze, fx, fy, fw, fh, show_solution=True, path=puzzle.solution, pair=puzzle.pair)
        _draw_bottom_page_no(c, pages + i + 1)
        c.showPage()

    c.save()
