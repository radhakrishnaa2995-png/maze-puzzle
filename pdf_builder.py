from reportlab.lib.utils import ImageReader
import random

def _draw_maze(c, maze, pair, page_w, page_h, difficulty):

    # =========================
    # PAGE LAYOUT (FIXED)
    # =========================
    margin = 40
    TOP_RESERVED = 100   # SPACE FOR TITLE (VERY IMPORTANT)

    maze_top = page_h - TOP_RESERVED
    maze_bottom = margin

    maze_height = maze_top - maze_bottom
    maze_width = page_w - 2 * margin

    rows = maze.rows
    cols = maze.cols

    # =========================
    # CELL SIZE (FIT BOTH AXES)
    # =========================
    cell_size = min(
        maze_width / cols,
        maze_height / rows
    )

    maze_w = cell_size * cols
    maze_h = cell_size * rows

    # =========================
    # PERFECT CENTERING
    # =========================
    maze_x = (page_w - maze_w) / 2
    maze_y = maze_bottom + (maze_height - maze_h) / 2

    # =========================
    # ENTRY / EXIT (FROM MAZE)
    # =========================
    start_cell = maze.start
    end_cell = maze.end

    entry_side = maze.start_open_side
    exit_side = maze.end_open_side

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
    # IMAGE SIZE (BIG + CLEAN)
    # =========================
    img_size = cell_size * 3   # BIGGER THAN BEFORE

    # =========================
    # PERFECT IMAGE ALIGNMENT
    # =========================
    def draw_icon(image_path, cell, side):
        r, col = cell

        # CENTER OF CELL
        cx = maze_x + col * cell_size + cell_size / 2
        cy = maze_y + (rows - r - 1) * cell_size + cell_size / 2

        GAP = 4  # small gap from wall

        # POSITION BASED ON OPEN SIDE
        if side == "W":  # LEFT
            x = cx - img_size - GAP
            y = cy - img_size / 2

        elif side == "E":  # RIGHT
            x = cx + GAP
            y = cy - img_size / 2

        elif side == "N":  # TOP
            x = cx - img_size / 2
            y = cy + GAP

        elif side == "S":  # BOTTOM
            x = cx - img_size / 2
            y = cy - img_size - GAP

        else:
            # fallback (should never happen)
            x = cx - img_size / 2
            y = cy - img_size / 2

        c.drawImage(
            ImageReader(image_path),
            x,
            y,
            width=img_size,
            height=img_size,
            mask='auto'
        )

    # =========================
    # DRAW START & END IMAGES
    # =========================
    draw_icon(pair.start_path, start_cell, entry_side)
    draw_icon(pair.end_path, end_cell, exit_side)
