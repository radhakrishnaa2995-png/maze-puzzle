"""Publication-ready scene maze puzzle book PDF builder with image-first layout pipeline."""

from __future__ import annotations

import random
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs

PAGE_W, PAGE_H = A4

PASTEL_PALETTE = [
    colors.HexColor("#DBEAFE"),
    colors.HexColor("#FBCFE8"),
    colors.HexColor("#FED7AA"),
    colors.HexColor("#D1FAE5"),
]


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


@dataclass
class MazePage:
    pair: IconPair
    path_cells: set[tuple[int, int]]


@dataclass
class MazeGrid:
    rows: int
    cols: int
    area: Box
    cell: float
    open_cells: set[tuple[int, int]]
    walls: Dict[tuple[int, int], dict[str, bool]]
    start: tuple[int, int]
    end: tuple[int, int]


def _draw_page_frame(c: canvas.Canvas, bg: colors.Color) -> None:
    c.setFillColor(bg)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _prepare_icon_reader(path: str) -> ImageReader:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3].astype(np.uint8)

    near_white = (rgb[:, :, 0] >= 230) & (rgb[:, :, 1] >= 230) & (rgb[:, :, 2] >= 230) & (alpha > 0)
    maxc = rgb.max(axis=2)
    minc = rgb.min(axis=2)
    low_sat = (maxc - minc) <= 16
    alpha[near_white & low_sat] = 0

    arr[:, :, 3] = alpha
    cleaned = Image.fromarray(arr, mode="RGBA")
    buf = BytesIO()
    cleaned.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_icon(c: canvas.Canvas, path: str, box: Box) -> None:
    img = _prepare_icon_reader(path)
    iw, ih = img.getSize()
    scale = min(box.w / iw, box.h / ih)
    w, h = iw * scale, ih * scale
    x = box.x + (box.w - w) / 2
    y = box.y + (box.h - h) / 2
    c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")


def place_entry_image() -> Box:
    size = PAGE_W * 0.18
    return Box(PAGE_W * 0.04, PAGE_H * 0.50 - (size / 2), size, size)


def place_exit_image() -> Box:
    size = PAGE_W * 0.18
    return Box(PAGE_W * 0.78, PAGE_H * 0.18 - (size / 2), size, size)


def calculate_remaining_space(entry_box: Box, exit_box: Box) -> Box:
    left = entry_box.x + entry_box.w + 20
    right = exit_box.x - 20
    bottom = PAGE_H * 0.08
    top = PAGE_H * 0.86
    return Box(left, bottom, max(120, right - left), max(220, top - bottom))


def random_shape(rng: random.Random) -> str:
    return rng.choice(["rectangle", "zigzag", "spiral", "wave"])


def create_maze_grid(area: Box, shape: str) -> MazeGrid:
    rows, cols = 18, 14
    cell = min(area.w / cols, area.h / rows)
    rows = max(10, int(area.h / cell))
    cols = max(10, int(area.w / cell))

    open_cells = set()
    for r in range(rows):
        for c in range(cols):
            if shape == "rectangle":
                keep = True
            elif shape == "zigzag":
                keep = (r % 4 != 0) or (2 <= c <= cols - 3)
            elif shape == "spiral":
                d = min(r, c, rows - 1 - r, cols - 1 - c)
                keep = (d % 2 == 0) or (r == rows // 2) or (c == cols // 2)
            else:  # wave
                keep = abs((r - rows / 2) - (3 * np.sin(c / 2.5))) < rows * 0.45
            if keep:
                open_cells.add((r, c))

    walls = {(r, c): {"N": True, "S": True, "E": True, "W": True} for (r, c) in open_cells}
    return MazeGrid(rows, cols, area, cell, open_cells, walls, (rows // 2, 0), (rows // 2, cols - 1))


def _neighbors(cell: tuple[int, int], rows: int, cols: int):
    r, c = cell
    for s, (dr, dc) in {"N": (-1, 0), "S": (1, 0), "W": (0, -1), "E": (0, 1)}.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield s, (nr, nc)


def get_cell_near(box: Box, grid: MazeGrid, side: str) -> tuple[int, int]:
    if side == "entry":
        candidates = [(r, c) for (r, c) in grid.open_cells if c <= 1]
        target_y = box.y + box.h / 2
    else:
        candidates = [(r, c) for (r, c) in grid.open_cells if c >= grid.cols - 2]
        target_y = box.y + box.h / 2
    if not candidates:
        return (grid.rows // 2, 0) if side == "entry" else (grid.rows // 2, grid.cols - 1)

    def y_of(cell):
        r, _ = cell
        return grid.area.y + (grid.rows - 1 - r) * grid.cell + (grid.cell / 2)

    return min(candidates, key=lambda rc: abs(y_of(rc) - target_y))


def generate_valid_path(grid: MazeGrid, start: tuple[int, int], end: tuple[int, int], rng: random.Random) -> list[tuple[int, int]]:
    stack = [start]
    prev = {start: None}
    while stack:
        cur = stack.pop()
        if cur == end:
            break
        nbs = [n for _s, n in _neighbors(cur, grid.rows, grid.cols) if n in grid.open_cells and n not in prev]
        rng.shuffle(nbs)
        for n in nbs:
            prev[n] = cur
            stack.append(n)

    if end not in prev:
        return [start]
    out = []
    cur = end
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    out.reverse()
    return out


def block_false_paths(grid: MazeGrid, valid_path: list[tuple[int, int]]) -> None:
    valid = set(valid_path)
    for cell in list(grid.open_cells):
        if cell not in valid:
            grid.walls[cell] = {"N": True, "S": True, "E": True, "W": True}

    for i in range(len(valid_path) - 1):
        a = valid_path[i]
        b = valid_path[i + 1]
        ar, ac = a
        br, bc = b
        if br == ar + 1:
            grid.walls[a]["S"] = False
            grid.walls[b]["N"] = False
        elif br == ar - 1:
            grid.walls[a]["N"] = False
            grid.walls[b]["S"] = False
        elif bc == ac + 1:
            grid.walls[a]["E"] = False
            grid.walls[b]["W"] = False
        elif bc == ac - 1:
            grid.walls[a]["W"] = False
            grid.walls[b]["E"] = False


def render_maze(grid: MazeGrid, c: canvas.Canvas) -> None:
    c.setStrokeColor(colors.HexColor("#111827"))
    c.setLineWidth(max(2.2, grid.cell * 0.12))
    c.setLineCap(1)
    c.setLineJoin(1)

    for (r, col) in grid.open_cells:
        x0 = grid.area.x + col * grid.cell
        y0 = grid.area.y + (grid.rows - 1 - r) * grid.cell
        x1, y1 = x0 + grid.cell, y0 + grid.cell
        w = grid.walls[(r, col)]
        if w["N"]:
            c.line(x0, y1, x1, y1)
        if w["S"]:
            c.line(x0, y0, x1, y0)
        if w["W"]:
            c.line(x0, y0, x0, y1)
        if w["E"]:
            c.line(x1, y0, x1, y1)


def generate_maze_page(c: canvas.Canvas, pair: IconPair, rng: random.Random) -> None:
    entry_box = place_entry_image()
    exit_box = place_exit_image()
    maze_area = calculate_remaining_space(entry_box, exit_box)
    grid = create_maze_grid(maze_area, shape=random_shape(rng))

    start = get_cell_near(entry_box, grid, "entry")
    end = get_cell_near(exit_box, grid, "exit")
    path = generate_valid_path(grid, start, end, rng)
    block_false_paths(grid, path)

    # explicit image-to-maze openings
    grid.walls[start]["W"] = False
    grid.walls[end]["E"] = False

    _draw_icon(c, str(pair.start_path), entry_box)
    _draw_icon(c, str(pair.finish_path), exit_box)
    render_maze(grid, c)


def build_book(
    output_file: str,
    pages: int,
    seed: int,
    title: str,
    icon_dir: str = "assets/icons",
    difficulty_profiles: dict[str, Any] | None = None,
    shape_dir: str | None = None,
    icon_scale: float = 0.2,
    anchor_cycle: list[list[str]] | None = None,
) -> None:
    if shape_dir:
        icon_dir = shape_dir

    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)
    pairs = load_icon_pairs(icon_dir)

    for i in range(pages):
        _draw_page_frame(c, PASTEL_PALETTE[i % len(PASTEL_PALETTE)])
        pair = pairs[i % len(pairs)]
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(PAGE_W * 0.06, PAGE_H * 0.92, pair.title)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(PAGE_W * 0.06, PAGE_H * 0.89, "CAN YOU SOLVE THIS MAZE?")
        generate_maze_page(c, pair, rng)
        c.showPage()

    c.save()
