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
    colors.HexColor("#FADADD"),  # pink
    colors.HexColor("#E6E6FA"),  # lavender
    colors.HexColor("#DDF1FF"),  # sky blue
    colors.HexColor("#DFF5E1"),  # mint
    colors.HexColor("#FFE6CC"),  # peach
    colors.HexColor("#FFF6DD"),  # cream
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

    # Decorative confetti circles.
    for _ in range(24):
        pastel = rng.choice(PASTEL_PALETTE)
        c.setFillColor(colors.Color(pastel.red, pastel.green, pastel.blue, alpha=0.30))
        c.circle(rng.uniform(25, PAGE_W - 25), rng.uniform(25, PAGE_H - 25), rng.uniform(5, 18), stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.roundRect(24, 24, PAGE_W - 48, PAGE_H - 48, 22, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#121212"))
    c.setLineWidth(2.8)
    c.roundRect(24, 24, PAGE_W - 48, PAGE_H - 48, 22, fill=0, stroke=1)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#1f2937"))
    c.drawString(40, PAGE_H - 40, title)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#4b5563"))
    c.drawRightString(PAGE_W - 40, PAGE_H - 40, f"Page {page_no}")


def _edge_point(maze: Maze, cell_rc: tuple[int, int], side: str, ox: float, oy: float, cell: float) -> tuple[float, float]:
    r, c = cell_rc
    x0 = ox + c * cell
    y0 = oy + (maze.rows - 1 - r) * cell
    x1, y1 = x0 + cell, y0 + cell
    if side == "N":
        return x0 + cell / 2, y1
    if side == "S":
        return x0 + cell / 2, y0
    if side == "W":
        return x0, y0 + cell / 2
    return x1, y0 + cell / 2


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
    cell = min(frame_w / maze.cols, frame_h / maze.rows)
    ox = frame_x + (frame_w - maze.cols * cell) / 2
    oy = frame_y + (frame_h - maze.rows * cell) / 2

    c.setStrokeColor(colors.HexColor("#111111"))
    c.setLineWidth(1.55)
    c.setLineCap(1)

    for r in range(maze.rows):
        for col in range(maze.cols):
            idx = (r, col)
            if idx not in maze.active_cells:
                continue

            walls = maze.walls[idx]
            x0, y0 = ox + col * cell, oy + (maze.rows - 1 - r) * cell
            x1, y1 = x0 + cell, y0 + cell

            if walls["N"]:
                c.line(x0, y1, x1, y1)
            if walls["S"]:
                c.line(x0, y0, x1, y0)
            if walls["W"]:
                c.line(x0, y0, x0, y1)
            if walls["E"]:
                c.line(x1, y0, x1, y1)

    def _marker(cell_rc: tuple[int, int], text: str, fill: colors.Color) -> None:
        rr, cc = cell_rc
        mx = ox + cc * cell + cell / 2
        my = oy + (maze.rows - 1 - rr) * cell + cell / 2
        rad = max(7, min(11, cell * 0.33))
        c.setFillColor(fill)
        c.circle(mx, my, rad, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", max(8, int(rad)))
        c.drawCentredString(mx, my - rad * 0.34, text)

    _marker(maze.start, "S", colors.HexColor("#16a34a"))
    _marker(maze.end, "F", colors.HexColor("#dc2626"))

    for marker_cell, side, label, fill in [
        (maze.start, maze.start_open_side, "ENTRY", colors.HexColor("#16a34a")),
        (maze.end, maze.end_open_side, "EXIT", colors.HexColor("#dc2626")),
    ]:
        px, py = _edge_point(maze, marker_cell, side, ox, oy, cell)
        dx, dy = 0, 0
        if side == "N":
            dy = 24
        elif side == "S":
            dy = -24
        elif side == "W":
            dx = -30
        else:
            dx = 30

        c.setStrokeColor(fill)
        c.setLineWidth(2.4)
        c.line(px, py, px + dx * 0.55, py + dy * 0.55)

        c.setFillColor(fill)
        c.roundRect(px + dx - 19, py + dy - 7, 38, 14, 4, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(px + dx, py + dy - 2.7, label)

    if show_solution and path:
        c.setStrokeColor(colors.HexColor("#E11D48"))  # red solution path
        c.setLineWidth(max(2.1, cell * 0.24))
        pts = []
        for rr, cc in path:
            px = ox + cc * cell + cell / 2
            py = oy + (maze.rows - 1 - rr) * cell + cell / 2
            pts.append((px, py))
        for i in range(len(pts) - 1):
            c.line(*pts[i], *pts[i + 1])


def _difficulty_for_page(page_idx: int, total_pages: int) -> tuple[str, int, int, float]:
    ratio = page_idx / max(1, total_pages - 1)
    if ratio < 0.33:
        return "Easy", 17, 17, 0.18
    if ratio < 0.66:
        return "Medium", 23, 23, 0.52
    return "Hard", 31, 31, 0.9


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
        c.roundRect(40, PAGE_H - 92, 215, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, PAGE_H - 84, f"Puzzle {page}  •  {difficulty}")

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, PAGE_H - 115, f"{shape}-Shaped Maze")

        c.setFillColor(colors.HexColor("#475569"))
        c.setFont("Helvetica", 11)
        c.drawRightString(PAGE_W - 40, PAGE_H - 112, "Follow ENTRY to EXIT")

        _draw_maze(
            c,
            maze,
            frame_x=50,
            frame_y=86,
            frame_w=PAGE_W - 100,
            frame_h=PAGE_H - 182,
            show_solution=False,
            path=None,
        )
        c.showPage()

    for i, puzzle in enumerate(puzzles, start=1):
        accent = ACCENTS[(i - 1) % len(ACCENTS)]
        _draw_page_background(c, bg_order[pages + i - 1], pages + i, f"{title} • Solutions", rng)

        c.setFillColor(accent)
        c.roundRect(40, PAGE_H - 92, 245, 24, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, PAGE_H - 84, f"Solution {puzzle.puzzle_number}  •  {puzzle.maze.difficulty}")

        c.setFillColor(colors.HexColor("#0f172a"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, PAGE_H - 115, f"{puzzle.maze.shape}-Shaped Maze")

        c.setFillColor(colors.HexColor("#64748b"))
        c.setFont("Helvetica", 11)
        c.drawString(40, PAGE_H - 130, "Correct route is highlighted in red.")

        _draw_maze(
            c,
            puzzle.maze,
            frame_x=50,
            frame_y=86,
            frame_w=PAGE_W - 100,
            frame_h=PAGE_H - 182,
            show_solution=True,
            path=puzzle.solution,
        )
        c.showPage()

    c.save()
