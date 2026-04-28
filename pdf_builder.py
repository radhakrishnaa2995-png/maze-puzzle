from fpdf import FPDF
import os

class MazePDFBuilder(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='pt', format='A4')
        self.set_auto_page_break(False)
        self.page_w = 595.28
        self.page_h = 841.89
        
        # LAYOUT CONSTANTS (FIX 1 & 8)
        self.TOP_RESERVED = 120
        self.BOTTOM_MARGIN = 60
        self.SIDE_MARGIN = 50

    def add_maze_page(self, grid, title_text, entry_coord, exit_coord, start_img, end_img):
        self.add_page()
        
        rows = len(grid)
        cols = len(grid[0])

        # CALCULATE CELL SIZE (FIX 2)
        max_maze_w = self.page_w - (self.SIDE_MARGIN * 2)
        max_maze_h = self.page_h - self.TOP_RESERVED - self.BOTTOM_MARGIN
        
        cell_size = min(max_maze_w / cols, max_maze_h / rows)
        
        maze_w = cell_size * cols
        maze_h = cell_size * rows
        
        # CENTER POSITIONS (FIX 2)
        start_x = (self.page_w - maze_w) / 2
        start_y = self.TOP_RESERVED + (max_maze_h - maze_h) / 2

        # DRAW TITLE (FIX 10)
        self.set_font("Arial", 'B', 20)
        self.set_y(50)
        self.cell(0, 40, title_text, 0, 1, 'C')

        # DRAW MAZE
        self.set_fill_color(0, 0, 0)
        for y in range(rows):
            for x in range(cols):
                if grid[y][x] == 1:
                    self.rect(start_x + (x * cell_size), start_y + (y * cell_size), 
                              cell_size + 0.5, cell_size + 0.5, 'F')

        # IMAGE SYSTEM (FIX 5 & 6)
        img_display_size = cell_size * 3.5  # Large, visible icons
        
        # Position Start Image (Centered on entry opening)
        s_idx_x, s_idx_y = entry_coord
        s_img_x = start_x + (s_idx_x * cell_size) - (img_display_size / 2)
        s_img_y = start_y + (s_idx_y * cell_size) - (img_display_size / 2)
        
        # Position End Image (Centered on exit opening)
        e_idx_x, e_idx_y = exit_coord
        e_img_x = start_x + (e_idx_x * cell_size) - (img_display_size / 2)
        e_img_y = start_y + (e_idx_y * cell_size) - (img_display_size / 2)

        # CLAMP IMAGES TO PREVENT OUT-OF-BOUNDS (FIX 7)
        def clamp(val, min_v, max_v):
            return max(min_v, min(val, max_v))

        s_img_x = clamp(s_img_x, 20, self.page_w - img_display_size - 20)
        s_img_y = clamp(s_img_y, self.TOP_RESERVED - 40, self.page_h - 40)
        
        e_img_x = clamp(e_img_x, 20, self.page_w - img_display_size - 20)
        e_img_y = clamp(e_img_y, self.TOP_RESERVED - 40, self.page_h - 40)

        # Place Images
        if os.path.exists(start_img):
            self.image(start_img, s_img_x, s_img_y, img_display_size)
        if os.path.exists(end_img):
            self.image(end_img, e_img_x, e_img_y, img_display_size)
