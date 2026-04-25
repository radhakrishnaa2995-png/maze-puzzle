"""PDF composition for printable maze books."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from maze_generator import Maze, generate_maze
from shapes import palette_sequence, shape_sequence
from solver import solve_maze

PAGE_W, PAGE_H = A4

PASTEL_PALETTE = [
    colors.HexColor("#FADADD"),
    colors.HexColor("#E6E6FA"),
    colors.HexColor("#DDF1FF"),
    colors.HexColor("#DFF5E1"),
    colors.HexColor("#FFE6CC"),
    colors.HexColor("#FFF6DD"),
]

ACCENTS = [
    colors.HexColor("#5B6EF5"),
    colors.HexColor("#22A699"),
    colors.HexColor("#F97316"),
    colors.HexColor("#8B5CF6"),
]


@dataclass
class PuzzlePage:
    puzzle_number: int
    maze: Maze
    solution: list[tuple[int, int]]


def _draw_page_background(c: canvas.Canvas, bg: colors.Color, page_no: int, title: str, rng: random.Random) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    for _ in range(24):
        pastel = rng.choice(PASTEL_PALETTE)
        c.setFillColor(colors.Color(pastel.red, pastel.green, pastel.blue, alpha=0.30))
        c.circle(rng.uniform(25, PAGE_W - 25), rng.uniform(25, PAGE_H - 25), rng.uniform(5, 18), stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.roundRect(20, 20, PAGE_W - 40, PAGE_H - 40, 22, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#121212"))
    c.setLineWidth(2.8)
    c.roundRect(20, 20, PAGE_W - 40, PAGE_H - 40, 22, fill=0, stroke=1)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#1f2937"))
    c.drawString(36, PAGE_H - 38, title)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#4b5563"))
    c.drawRightString(PAGE_W - 36, PAGE_H - 38, f"Page {page_no}")


def _draw_direction_arrow(c: canvas.Canvas, px: float, py: float, side: str, color: colors.Color) -> None:
    c.setFillColor(color)
    if side == "N":
        pts = [px, py + 18, px - 7, py + 6, px + 7, py + 6]
    elif side == "S":
        pts = [px, py - 18, px - 7, py - 6, px + 7, py - 6]
    elif side == "W":
        pts = [px - 18, py, px - 6, py - 7, px - 6, py + 7]
    else:
        pts = [px + 18, py, px + 6, py - 7, px + 6, py + 7]
    p = c.beginPath()
    p.moveTo(pts[0], pts[1])
    p.lineTo(pts[2], pts[3])
    p.lineTo(pts[4], pts[5])
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    ratio = page_idx / max(1, total_pages - 1)
    if ratio < 0.33:
        return "Easy", 33, 33, 0.20
    if ratio < 0.66:
        return "Medium", 45, 45, 0.56
    return "Hard", 59, 59, 0.9


def _draw_maze(
    c: canvas.Canvas,
    maze: Maze,
    frame_x: float,
    frame_y: float,
    frame_w: float,
    frame_h: float,
    show_solution: bool,
    path: list[tuple[int, int]] | None,
) -> None:
    min_r = min(r for r, _ in maze.active_cells)
    max_r = max(r for r, _ in maze.active_cells)
    min_c = min(c_ for _, c_ in maze.active_cells)
    max_c = max(c_ for _, c_ in maze.active_cells)

    vis_rows = (max_r - min_r + 1)
    vis_cols = (max_c - min_c + 1)

    cell = min(frame_w / vis_cols, frame_h / vis_rows)
    ox = frame_x + (frame_w - vis_cols * cell) / 2
    oy = frame_y + (frame_h - vis_rows * cell) / 2

    def box_for(cell_rc: tuple[int, int]) -> tuple[float, float, float, float]:
        rr, cc = cell_rc
        local_r = rr - min_r
        local_c = cc - min_c
        x0 = ox + local_c * cell
        y0 = oy + (vis_rows - 1 - local_r) * cell
        x1, y1 = x0 + cell, y0 + cell
        return x0, y0, x1, y1

    c.setStrokeColor(colors.HexColor("#7A7A7A"))
    c.setLineWidth(max(0.35, cell * 0.06))
    c.setLineCap(1)

    outline_segments: list[tuple[float, float, float, float]] = []

    for idx in maze.active_cells:
        r, col = idx
        walls = maze.walls[idx]
        x0, y0, x1, y1 = box_for(idx)

        if walls["N"]:
            c.line(x0, y1, x1, y1)
        if walls["S"]:
            c.line(x0, y0, x1, y0)
        if walls["W"]:
            c.line(x0, y0, x0, y1)
        if walls["E"]:
            c.line(x1, y0, x1, y1)

        up = (r - 1, col) not in maze.active_cells
        dn = (r + 1, col) not in maze.active_cells
        lf = (r, col - 1) not in maze.active_cells
        rt = (r, col + 1) not in maze.active_cells

        if up and not (idx == maze.start and maze.start_open_side == "N") and not (idx == maze.end and maze.end_open_side == "N"):
            outline_segments.append((x0, y1, x1, y1))
        if dn and not (idx == maze.start and maze.start_open_side == "S") and not (idx == maze.end and maze.end_open_side == "S"):
            outline_segments.append((x0, y0, x1, y0))
        if lf and not (idx == maze.start and maze.start_open_side == "W") and not (idx == maze.end and maze.end_open_side == "W"):
            outline_segments.append((x0, y0, x0, y1))
        if rt and not (idx == maze.start and maze.start_open_side == "E") and not (idx == maze.end and maze.end_open_side == "E"):
            outline_segments.append((x1, y0, x1, y1))

    c.setStrokeColor(colors.HexColor("#101010"))
    c.setLineWidth(max(1.4, cell * 0.14))
    for x0, y0, x1, y1 in outline_segments:
        c.line(x0, y0, x1, y1)

    for marker_cell, side, col in [
        (maze.start, maze.start_open_side, colors.HexColor("#22c55e")),
        (maze.end, maze.end_open_side, colors.HexColor("#ef4444")),
    ]:
        x0, y0, x1, y1 = box_for(marker_cell)
        if side == "N":
            px, py = x0 + cell / 2, y1
        elif side == "S":
            px, py = x0 + cell / 2, y0
        elif side == "W":
            px, py = x0, y0 + cell / 2
        else:
            px, py = x1, y0 + cell / 2
        _draw_direction_arrow(c, px, py, side, col)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#E11D48"))
        c.setLineWidth(max(1.5, cell * 0.16))
        pts = []
        for rr, cc in path:
            x0, y0, _, _ = box_for((rr, cc))
            pts.append((x0 + cell / 2, y0 + cell / 2))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def build_book(output_file: str, pages: int, seed: int, title: str) -> None:
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    shape_order = shape_sequence(pages, rng, min_gap=3)
    bg_order = palette_sequence((pages * 2) + 3, PASTEL_PALETTE, rng)

    puzzles: List[PuzzlePage] = []

    for page in range(1, pages + 1):
        accent = ACCENTS[(page - 1) % len(ACCENTS)]
        _draw_page_background(c, bg_order[page - 1], page, title, rng)

        difficulty, rows, cols, diff = _difficulty_for_page(page - 1, pages)
        shape = shape_order[page - 1]

        maze = generate_maze(rows=rows, cols=cols, shape=shape, difficulty_factor=diff, rng=rng)
        maze.difficulty = difficulty
        solution = solve_maze(maze)
        puzzles.append(PuzzlePage(page, maze, solution))

        c.setFillColor(accent)
        c.roundRect(36, PAGE_H - 90, 220, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(46, PAGE_H - 82, f"Puzzle {page}  •  {difficulty}")

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(36, PAGE_H - 114, f"{shape}-Shaped Maze")

        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica", 11)
        c.drawRightString(PAGE_W - 36, PAGE_H - 111, "Green arrow = start, red arrow = finish")

        _draw_maze(c, maze, frame_x=34, frame_y=74, frame_w=PAGE_W - 68, frame_h=PAGE_H - 164, show_solution=False, path=None)
        c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        _draw_page_background(c, bg_order[pages + i - 1], pages + i, f"{title} • Solutions", rng)

        c.setFillColor(accent)
        c.roundRect(36, PAGE_H - 90, 250, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(46, PAGE_H - 82, f"Solution {puzzle.puzzle_number}  •  {puzzle.maze.difficulty}")

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(36, PAGE_H - 114, f"{puzzle.maze.shape}-Shaped Maze")

        c.setFillColor(colors.HexColor("#64748b"))
        c.setFont("Helvetica", 11)
        c.drawString(36, PAGE_H - 129, "Correct route is highlighted in red.")

        _draw_maze(c, puzzle.maze, frame_x=34, frame_y=74, frame_w=PAGE_W - 68, frame_h=PAGE_H - 164, show_solution=True, path=puzzle.solution)
        c.showPage()

    c.save()
