from fpdf import FPDF
import os

class MazePDFBuilder(FPDF):
    def __init__(self):
        super().__init__(orientation='P', unit='pt', format='A4')
        self.set_auto_page_break(False)
        self.page_w = 595.28
        self.page_h = 841.89

    def add_maze_page(self, grid, theme, page_num, entry, exit_pt):
        self.add_page()
        
        # 1. SET TWO-COLOR THEME
        bg = theme['bg_color']
        head = theme['head_color']
        self.set_fill_color(*bg)
        self.rect(0, 0, self.page_w, self.page_h, 'F')

        # 2. HEADER PILL WITH STAR RATING
        self.set_fill_color(*head)
        self.rect(40, 40, 515, 25, 'F') 
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 11)
        self.text(55, 57, f"Puzzle {page_num} - Easy " + chr(171)) # 171 is a star proxy in some fonts, or use '*'

        # 3. TEXT ACCORDING TO STORYLINE
        self.set_text_color(30, 30, 30)
        self.set_font("Arial", 'B', 16)
        self.text(40, 85, theme['title'])
        self.set_font("Arial", '', 8)
        self.text(40, 98, theme['instruction'])

        # 4. MAZE DIMENSIONS
        rows, cols = len(grid), len(grid[0])
        cell_size = 18
        maze_w = cell_size * cols
        maze_h = cell_size * rows
        offset_x = (self.page_w - maze_w) / 2
        offset_y = 130

        # 5. DRAW LINE MAZE WITH OPENINGS
        self.set_draw_color(0, 0, 0)
        self.set_line_width(1.2)
        
        for y in range(rows):
            for x in range(cols):
                # Horizontal walls
                if y == 0:
                    # Only draw top border if it's NOT the entry/exit
                    if not (x == entry[0] and y == entry[1]) and not (x == exit_pt[0] and y == exit_pt[1]):
                        self.line(offset_x + x*cell_size, offset_y + y*cell_size, offset_x + (x+1)*cell_size, offset_y + y*cell_size)
                
                # Vertical walls
                if x == 0:
                    # Only draw left border if it's NOT the entry/exit
                    if not (x == entry[0] and y == entry[1]) and not (x == exit_pt[0] and y == exit_pt[1]):
                        self.line(offset_x + x*cell_size, offset_y + y*cell_size, offset_x + x*cell_size, offset_y + (y+1)*cell_size)

                # Internal Walls
                if grid[y][x] == 1:
                    # Bottom wall
                    if y < rows - 1 and grid[y+1][x] == 0:
                         self.line(offset_x + x*cell_size, offset_y + (y+1)*cell_size, offset_x + (x+1)*cell_size, offset_y + (y+1)*cell_size)
                    # Right wall
                    if x < cols - 1 and grid[y][x+1] == 0:
                        self.line(offset_x + (x+1)*cell_size, offset_y + y*cell_size, offset_x + (x+1)*cell_size, offset_y + (y+1)*cell_size)

        # Draw outer perimeter EXCEPT openings
        # Bottom Edge
        for x in range(cols):
            if not (x == exit_pt[0] and (rows-1) == exit_pt[1]):
                self.line(offset_x + x*cell_size, offset_y + rows*cell_size, offset_x + (x+1)*cell_size, offset_y + rows*cell_size)
        # Right Edge
        for y in range(rows):
            if not ((cols-1) == exit_pt[0] and y == exit_pt[1]):
                self.line(offset_x + cols*cell_size, offset_y + y*cell_size, offset_x + cols*cell_size, offset_y + (y+1)*cell_size)

        # 6. ICON PLACEMENT AT OPENINGS
        icon_size = 35
        # Start Icon (Placed slightly outside entry)
        s_x = offset_x + (entry[0] * cell_size) - (icon_size if entry[0] == 0 else 10)
        s_y = offset_y + (entry[1] * cell_size) - (icon_size / 2)
        if os.path.exists(theme['start_img']):
            self.image(theme['start_img'], s_x, s_y, icon_size)

        # End Icon (Placed slightly outside exit)
        e_x = offset_x + (exit_pt[0] * cell_size) + (5 if exit_pt[0] == cols-1 else -10)
        e_y = offset_y + (exit_pt[1] * cell_size) - (icon_size / 2)
        if os.path.exists(theme['end_img']):
            self.image(theme['end_img'], e_x, e_y, icon_size)

        # 7. PAGE FOOTER
        self.set_text_color(50, 50, 50)
        self.set_font("Arial", '', 9)
        self.text(self.page_w/2 - 15, self.page_h - 40, f"Page {page_num}")
