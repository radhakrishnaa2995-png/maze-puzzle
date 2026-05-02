"""Professional kids maze worksheet generator (image-first layout)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from icons import IconPair, load_icon_pairs

PAGE_W, PAGE_H = A4


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


def _draw_page_bg(c: canvas.Canvas) -> None:
    c.setFillColor(colors.HexColor("#D8F3E7"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _clean_icon(path: str) -> ImageReader:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    rgb = arr[:, :, :3]
    a = arr[:, :, 3]
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    low_sat = (mx - mn) <= 18
    near_white = (rgb[:, :, 0] >= 226) & (rgb[:, :, 1] >= 226) & (rgb[:, :, 2] >= 226)
    a[near_white & low_sat] = 0
    arr[:, :, 3] = a
    out = Image.fromarray(arr, mode="RGBA")
    buf = BytesIO()
    out.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_icon(c: canvas.Canvas, path: str, box: Box) -> None:
    img = _clean_icon(path)
    iw, ih = img.getSize()
    scale = min(box.w / iw, box.h / ih)
    w, h = iw * scale, ih * scale
    x = box.x + (box.w - w) / 2
    y = box.y + (box.h - h) / 2
    c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")


def place_entry_image() -> Box:
    s = PAGE_W * 0.20
    return Box(PAGE_W * 0.04, PAGE_H * 0.53 - s / 2, s, s)


def place_exit_image() -> Box:
    s = PAGE_W * 0.20
    return Box(PAGE_W * 0.76, PAGE_H * 0.24 - s / 2, s, s)


def calculate_remaining_space(entry: Box, exitb: Box) -> Box:
    left = entry.x + entry.w + 22
    right = exitb.x - 22
    bottom = PAGE_H * 0.10
    top = PAGE_H * 0.84
    return Box(left, bottom, right - left, top - bottom)


def get_maze_shape(rng: random.Random) -> str:
    return rng.choice(["rectangle","square","zigzag","spiral","wave","s_shape","circular"])


def difficulty_for_page(i: int, total: int) -> str:
    p = (i + 1) / max(1, total)
    if p <= 0.33:
        return "easy"
    if p <= 0.70:
        return "medium"
    return "hard"


def grid_size_for_difficulty(level: str) -> tuple[int, int]:
    if level == "easy":
        return 10, 8
    if level == "medium":
        return 14, 10
    return 18, 12


def shape_cells(rows: int, cols: int, shape: str) -> set[tuple[int, int]]:
    cells = set()
    for r in range(rows):
        for c in range(cols):
            keep = True
            if shape == "square":
                keep = abs(r - rows / 2) <= rows * 0.45 and abs(c - cols / 2) <= cols * 0.45
            elif shape == "zigzag":
                keep = (r % 3 != 0) or (1 <= c <= cols - 2)
            elif shape == "spiral":
                d = min(r, c, rows - 1 - r, cols - 1 - c)
                keep = (d % 2 == 0) or (r == rows // 2)
            elif shape == "wave":
                keep = abs((r - rows / 2) - 2.4 * np.sin(c / 1.9)) < rows * 0.42
            elif shape == "s_shape":
                keep = abs((r - rows / 2) - 2.8 * np.sin(c / 2.2)) < rows * 0.28
            elif shape == "circular":
                cy, cx = rows / 2.0, cols / 2.0
                d = ((r - cy) ** 2 + (c - cx) ** 2) ** 0.5
                keep = (rows * 0.18) <= d <= (rows * 0.48)
            if keep:
                cells.add((r, c))
    return cells


def neighbors(cell: tuple[int, int], rows: int, cols: int):
    r, c = cell
    for side, (dr, dc) in {"N": (-1, 0), "S": (1, 0), "W": (0, -1), "E": (0, 1)}.items():
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield side, (nr, nc)


def get_cell_near(box: Box, area: Box, rows: int, cols: int, edge: str, active: set[tuple[int, int]]) -> tuple[int, int]:
    if edge == "left":
        cand = [(r, c) for r, c in active if c <= 1]
    else:
        cand = [(r, c) for r, c in active if c >= cols - 2]
    if not cand:
        return (rows // 2, 0 if edge == "left" else cols - 1)

    def py(r):
        ch = area.h / rows
        return area.y + (rows - 1 - r) * ch + ch / 2

    target = box.y + box.h / 2
    return min(cand, key=lambda rc: abs(py(rc[0]) - target))


def create_main_path(start: tuple[int, int], end: tuple[int, int], rows: int, cols: int, active: set[tuple[int, int]], rng: random.Random) -> list[tuple[int, int]]:
    stack = [start]
    prev = {start: None}
    while stack:
        cur = stack.pop()
        if cur == end:
            break
        ns = [n for _s, n in neighbors(cur, rows, cols) if n in active and n not in prev]
        rng.shuffle(ns)
        ns.sort(key=lambda c: abs(c[1] - end[1]) + abs(c[0] - end[0]))
        for n in ns:
            prev[n] = cur
            stack.append(n)
    if end not in prev:
        return [start, end]
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return list(reversed(path))


def shape_guided_path(shape: str, rows: int, cols: int, active: set[tuple[int, int]], start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    if shape == "zigzag":
        p = []
        for c in range(cols):
            rr = range(1, rows - 1) if c % 2 == 0 else range(rows - 2, 0, -1)
            for r in rr:
                if (r, c) in active:
                    p.append((r, c))
        return [start] + [x for x in p if x not in {start, end}] + [end]
    if shape == "s_shape":
        p = []
        for c in range(cols):
            yc = (rows * 0.5) + (rows * 0.28 * np.sin((c / max(1, cols - 1)) * np.pi * 2))
            r = int(max(1, min(rows - 2, yc)))
            if (r, c) in active:
                p.append((r, c))
        return [start] + [x for x in p if x not in {start, end}] + [end]
    if shape == "circular":
        cy, cx = rows / 2.0, cols / 2.0
        p = []
        for t in np.linspace(0.0, 2.3 * np.pi, num=max(32, cols * 3)):
            rad = min(rows, cols) * (0.45 - 0.25 * (t / (2.3 * np.pi)))
            r = int(round(cy + np.sin(t) * rad))
            c = int(round(cx + np.cos(t) * rad))
            if (r, c) in active:
                p.append((r, c))
        uniq = []
        seen = set()
        for cell in p:
            if cell not in seen:
                uniq.append(cell)
                seen.add(cell)
        return [start] + [x for x in uniq if x not in {start, end}] + [end]
    return []


def add_dead_ends(path: list[tuple[int, int]], active: set[tuple[int, int]], rows: int, cols: int, level: str, rng: random.Random) -> set[tuple[int, int]]:
    keep = set(path)
    count = {"easy": 2, "medium": 6, "hard": 10}[level]
    for _ in range(count):
        base = rng.choice(path[1:-1]) if len(path) > 2 else path[0]
        opts = [n for _s, n in neighbors(base, rows, cols) if n in active and n not in keep]
        if opts:
            keep.add(rng.choice(opts))
    return keep


def build_walls(active: set[tuple[int, int]], rows: int, cols: int, keep: set[tuple[int, int]], path: list[tuple[int, int]]) -> dict[tuple[int, int], dict[str, bool]]:
    walls = {c: {"N": True, "S": True, "E": True, "W": True} for c in active}
    path_set = set(path)
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        ar, ac = a
        br, bc = b
        if br == ar + 1:
            walls[a]["S"] = False; walls[b]["N"] = False
        elif br == ar - 1:
            walls[a]["N"] = False; walls[b]["S"] = False
        elif bc == ac + 1:
            walls[a]["E"] = False; walls[b]["W"] = False
        elif bc == ac - 1:
            walls[a]["W"] = False; walls[b]["E"] = False

    for c in keep - path_set:
        # dead-end cell: open to only one adjacent kept cell
        links = []
        for s, n in neighbors(c, rows, cols):
            if n in keep:
                links.append((s, n))
        if links:
            s, n = links[0]
            opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[s]
            walls[c][s] = False
            walls[n][opp] = False
    return walls


def render_maze(c: canvas.Canvas, area: Box, rows: int, cols: int, active: set[tuple[int, int]], walls: dict[tuple[int, int], dict[str, bool]]) -> None:
    cw = area.w / cols
    ch = area.h / rows
    c.setStrokeColor(colors.black)
    c.setLineWidth(max(2.6, min(cw, ch) * 0.14))
    c.setLineCap(1)
    c.setLineJoin(1)

    for r, col in active:
        x0 = area.x + col * cw
        y0 = area.y + (rows - 1 - r) * ch
        x1, y1 = x0 + cw, y0 + ch
        w = walls[(r, col)]
        if w["N"]: c.line(x0, y1, x1, y1)
        if w["S"]: c.line(x0, y0, x1, y0)
        if w["W"]: c.line(x0, y0, x0, y1)
        if w["E"]: c.line(x1, y0, x1, y1)


def generate_maze_page(c: canvas.Canvas, pair: IconPair, page_idx: int, total_pages: int, rng: random.Random) -> None:
    level = difficulty_for_page(page_idx, total_pages)
    entry = place_entry_image()
    exitb = place_exit_image()
    area = calculate_remaining_space(entry, exitb)

    rows, cols = grid_size_for_difficulty(level)
    shape = get_maze_shape(rng)
    active = shape_cells(rows, cols, shape)

    start = get_cell_near(entry, area, rows, cols, "left", active)
    end = get_cell_near(exitb, area, rows, cols, "right", active)

    path = shape_guided_path(shape, rows, cols, active, start, end)
    if len(path) < 2:
        path = create_main_path(start, end, rows, cols, active, rng)
    keep = add_dead_ends(path, active, rows, cols, level, rng)
    walls = build_walls(active, rows, cols, keep, path)

    # connect to image edges
    if start in walls:
        walls[start]["W"] = False
    if end in walls:
        walls[end]["E"] = False

    _draw_icon(c, str(pair.start_path), entry)
    _draw_icon(c, str(pair.finish_path), exitb)
    render_maze(c, area, rows, cols, active, walls)


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

    pairs = load_icon_pairs(icon_dir)
    rng = random.Random(seed)
    c = canvas.Canvas(output_file, pagesize=A4)

    for i in range(pages):
        pair = pairs[i % len(pairs)]
        _draw_page_bg(c)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(PAGE_W * 0.05, PAGE_H * 0.93, pair.title)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(PAGE_W * 0.05, PAGE_H * 0.90, "CAN YOU SOLVE THIS MAZE?")
        generate_maze_page(c, pair, i, pages, rng)
        c.showPage()

    c.save()
