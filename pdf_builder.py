from fpdf import FPDF
import os

class MazePDFBuilder(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='pt', format='A4')
        self.set_auto_page_break(False)
        self.page_w = 595.28
        self.page_h = 841.89

    def add_maze_page(self, grid, theme_data, page_num, entry, exit, start_img, end_img):
        self.add_page()
        
        # 1. DRAW PASTEL BACKGROUND
        bg = theme_data['bg_color']
        self.set_fill_color(bg[0], bg[1], bg[2])
        self.rect(0, 0, self.page_w, self.page_h, 'F')

        # 2. HEADER PILL
        head = theme_data['head_color']
        self.set_fill_color(head[0], head[1], head[2])
        # Rounded rectangle for the "Puzzle X - Easy" bar
        self.rect(40, 40, 515, 30, 'F') 
        
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 12)
        self.text(60, 60, f"Puzzle {page_num} - Easy")

        # 3. TITLES
        self.set_text_color(40, 40, 40)
        self.set_font("Arial", 'B', 18)
        self.text(40, 95, theme_data['main_title'])
        self.set_font("Arial", '', 9)
        self.text(40, 110, theme_data['sub_title'])

        # 4. MAZE SPECS
        rows, cols = len(grid), len(grid[0])
        cell_size = 20
        maze_w = cell_size * cols
        maze_h = cell_size * rows
        offset_x = (self.page_w - maze_w) / 2
        offset_y = 150 # Starting below titles

        # 5. DRAW LINE-BASED MAZE (Matching Reference Image 3)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(1.5)
        
        for y in range(rows):
            for x in range(cols):
                if grid[y][x] == 1: # Wall logic for lines
                    # Draw horizontal walls
                    if y == 0 or (y > 0 and grid[y-1][x] == 0):
                         self.line(offset_x + x*cell_size, offset_y + y*cell_size, 
                                   offset_x + (x+1)*cell_size, offset_y + y*cell_size)
                    # Draw vertical walls
                    if x == 0 or (x > 0 and grid[y][x-1] == 0):
                        self.line(offset_x + x*cell_size, offset_y + y*cell_size, 
                                  offset_x + x*cell_size, offset_y + (y+1)*cell_size)
        
        # External Border
        self.rect(offset_x, offset_y, maze_w, maze_h)

        # 6. ICON PLACEMENT
        icon_size = 40
        # Entry Icon
        ex, ey = entry
        ix = offset_x + (ex * cell_size) - (icon_size if ex == 0 else 0)
        iy = offset_y + (ey * cell_size) - (icon_size/2)
        if os.path.exists(start_img):
            self.image(start_img, ix - 10, iy, icon_size)

        # Exit Icon
        ox, oy = exit
        ox_pos = offset_x + (ox * cell_size)
        oy_pos = offset_y + (oy * cell_size) - (icon_size/2)
        if os.path.exists(end_img):
            self.image(end_img, ox_pos + 5, oy_pos, icon_size)

        # 7. PAGE NUMBER
        self.set_font("Arial", '', 10)
        self.text(self.page_w/2 - 10, self.page_h - 40, f"Page {page_num}")
