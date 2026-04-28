from fpdf import FPDF
import os

class MazePDFBuilder(FPDF):
    def __init__(self):
        # KDP Standard 8.5x11 inches in points
        super().__init__(orientation='P', unit='pt', format=(612, 792))
        self.set_margins(50, 50, 50) # KDP Safe Zones
        self.set_auto_page_break(False)

    def draw_maze(self, grid, x_start, y_start, size, entry, exit_pt):
        rows = len(grid)
        cols = len(grid[0])
        cell_size = size / max(rows, cols)
        
        # FIX 5: Bold Outer Border
        self.set_line_width(3.0)
        self.set_draw_color(0, 0, 0)
        
        # Draw perimeter lines individually to handle openings
        # Top
        for x in range(cols):
            if not (x == entry[0] and 0 == entry[1]):
                self.line(x_start + x*cell_size, y_start, x_start + (x+1)*cell_size, y_start)
        # Bottom
        for x in range(cols):
            if not (x == exit_pt[0] and (rows-1) == exit_pt[1]):
                self.line(x_start + x*cell_size, y_start + rows*cell_size, x_start + (x+1)*cell_size, y_start + rows*cell_size)
        # Left
        for y in range(rows):
            if not (0 == entry[0] and y == entry[1]):
                self.line(x_start, y_start + y*cell_size, x_start, y_start + (y+1)*cell_size)
        # Right
        for y in range(rows):
            if not ((cols-1) == exit_pt[0] and y == exit_pt[1]):
                self.line(x_start + cols*cell_size, y_start + y*cell_size, x_start + cols*cell_size, y_start + (y+1)*cell_size)

        # FIX 5: Inner walls (thinner)
        self.set_line_width(1.2)
        for y in range(rows):
            for x in range(cols):
                if grid[y][x] == 1:
                    # Draw internal segments only
                    if 0 < y < rows-1 and 0 < x < cols-1:
                        # Logic to draw internal block/line
                        self.rect(x_start + x*cell_size, y_start + y*cell_size, cell_size, cell_size, 'F')

    def add_maze_page(self, page_data):
        self.add_page()
        grid = page_data['grid']
        theme = page_data['theme']
        diff = page_data['difficulty']
        
        # FIX 7: TOP SECTION (Title + Stars)
        self.set_font("Arial", 'B', 24)
        self.set_text_color(0, 0, 0)
        self.cell(0, 40, f"Puzzle {page_data['num']}: {theme['name']}", ln=True, align='C')
        
        # FIX 4: Star Indicator
        stars = " " + ("ID" if diff == "Easy" else "IDID" if diff == "Medium" else "IDIDID").replace("ID", chr(171)) 
        # Note: If font doesn't support 171, use '*'
        self.set_font("Arial", 'B', 14)
        self.cell(0, 20, f"Difficulty: {diff} {'*' * page_data['star_count']}", ln=True, align='C')
        
        # FIX 8: Storyline
        self.ln(10)
        self.set_font("Arial", 'B', 12)
        self.multi_cell(0, 15, theme['story'].upper(), align='C')

        # FIX 11: Visual Balance / Maze Placement
        maze_display_size = 380 
        m_x = (612 - maze_display_size) / 2
        m_y = 180
        
        self.draw_maze(grid, m_x, m_y, maze_display_size, page_data['entry'], page_data['exit'])

        # FIX 1 & 9: Large Start & End Images
        img_size = maze_display_size * 0.22 
        
        # Start Image Position (Relative to Entry)
        e_x, e_y = page_data['entry']
        cell_size = maze_display_size / max(len(grid), len(grid[0]))
        
        # Calculate pixel-perfect alignment for entry
        ix_s = m_x + (e_x * cell_size) - (img_size if e_x == 0 else img_size/2)
        iy_s = m_y + (e_y * cell_size) - (img_size if e_y == 0 else img_size/2)
        
        if os.path.exists(theme['start_img']):
            self.image(theme['start_img'], ix_s, iy_s, w=img_size)

        # End Image Position (Relative to Exit)
        ex_x, ex_y = page_data['exit']
        ix_e = m_x + (ex_x * cell_size) + (0 if ex_x < len(grid[0])-1 else 10)
        iy_e = m_y + (ex_y * cell_size) + (0 if ex_y < len(grid)-1 else 10)
        
        if os.path.exists(theme['end_img']):
            self.image(theme['end_img'], ix_e, iy_e, w=img_size)

        # Footer
        self.set_y(-50)
        self.set_font("Arial", 'I', 10)
        self.cell(0, 10, f"Page {page_data['num']}", align='C')
