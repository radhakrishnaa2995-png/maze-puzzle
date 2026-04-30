    # Validation checks for geometry-driven alignment.
    center_x = geom.offset_x + (geom.maze_width / 2)
    center_y = geom.offset_y + (geom.maze_height / 2)
    if abs(center_x - (PAGE_W / 2)) > PAGE_W * 0.06 or abs(center_y - (PAGE_H / 2)) > PAGE_H * 0.10:
        print("Warning: maze center drift detected; auto-centering has been applied.")

    maze_line_width = min(2.4, max(1.8, geom.cell_size * 0.14))
    outer_line_width = maze_line_width
    line_color = colors.HexColor("#111111")

    c.setStrokeColor(line_color)
    c.setLineWidth(maze_line_width)
    for rc in maze.active_cells:
        x0, y0, x1, y1 = cell_box(rc, geom)
        w = maze.walls[rc]
        if w["N"]:
            c.line(x0, y1, x1, y1)
        if w["S"]:
            c.line(x0, y0, x1, y0)
        if w["W"]:
            c.line(x0, y0, x0, y1)
        if w["E"]:
            c.line(x1, y0, x1, y1)
