from reportlab.lib.utils import ImageReader
import random

def _draw_maze(c, maze, pair, page_w, page_h, difficulty):

    # =========================
    # SAFE PAGE LAYOUT
    # =========================
    margin = 40

    title_h = 90
    maze_top = page_h - title_h
    maze_bottom = margin

    maze_height = maze_top - maze_bottom
    maze_width = page_w - 2 * margin

    rows = maze.rows
    cols = maze.cols

    cell_size = min(
        maze_width / cols,
        maze_height / rows
    )

    maze_w = cell_size * cols
    maze_h = cell_size * rows

    maze_x = (page_w - maze_w) / 2
    maze_y = maze_bottom + (maze_height - maze_h) / 2

    # =========================
    # RANDOM ENTRY/EXIT STYLE
    # =========================
    patterns = [
        ("TL", "BR"),
        ("TR", "BL"),
        ("LEFT", "RIGHT"),
        ("TOP", "BOTTOM")
    ]

    entry_type, exit_type = random.choice(patterns)

    # =========================
    # GET ENTRY / EXIT CELLS
    # =========================
    def get_edge_cell(edge):
        if edge == "TL":
            return (0, 0)
        if edge == "TR":
            return (0, cols - 1)
        if edge == "BL":
            return (rows - 1, 0)
        if edge == "BR":
            return (rows - 1, cols - 1)
        if edge == "LEFT":
            return (rows // 2, 0)
        if edge == "RIGHT":
            return (rows // 2, cols - 1)
        if edge == "TOP":
            return (0, cols // 2)
        if edge == "BOTTOM":
            return (rows - 1, cols // 2)

    start_cell = get_edge_cell(entry_type)
    end_cell = get_edge_cell(exit_type)

    maze.set_entry_exit(start_cell, end_cell)

    # =========================
    # DRAW MAZE
    # =========================
    c.setLineWidth(2)

    for r in range(rows):
        for col in range(cols):
            x = maze_x + col * cell_size
            y = maze_y + (rows - r - 1) * cell_size

            walls = maze.walls[(r, col)]

            if walls["top"]:
                c.line(x, y + cell_size, x + cell_size, y + cell_size)
            if walls["bottom"]:
                c.line(x, y, x + cell_size, y)
            if walls["left"]:
                c.line(x, y, x, y + cell_size)
            if walls["right"]:
                c.line(x + cell_size, y, x + cell_size, y + cell_size)

    # =========================
    # IMAGE SIZE (BIG FIX)
    # =========================
    img_size = cell_size * 2.5

    def draw_icon(image_path, cell, side):
        r, col = cell

        cx = maze_x + col * cell_size + cell_size / 2
        cy = maze_y + (rows - r - 1) * cell_size + cell_size / 2

        if side in ["LEFT", "TL", "BL"]:
            x = cx - img_size * 1.2
            y = cy - img_size / 2
        elif side in ["RIGHT", "TR", "BR"]:
            x = cx + img_size * 0.2
            y = cy - img_size / 2
        elif side == "TOP":
            x = cx - img_size / 2
            y = cy + img_size * 0.2
        else:  # BOTTOM
            x = cx - img_size / 2
            y = cy - img_size * 1.2

        c.drawImage(
            ImageReader(image_path),
            x,
            y,
            width=img_size,
            height=img_size,
            mask='auto'
        )

    draw_icon(pair.start_path, start_cell, entry_type)
    draw_icon(pair.end_path, end_cell, exit_type)
