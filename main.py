from maze_generator import MazeGenerator
from pdf_builder import MazePDFBuilder

def main():
    pdf = MazePDFBuilder()
    
    # Themes matching the requested pastel/header style
    themes = [
        {
            "main_title": "Pirate Maze", 
            "sub_title": "GUIDE THE PIRATE SHIP TO THE TREASURE CHEST!",
            "bg_color": (255, 245, 200), # Light Yellow Pastel
            "head_color": (220, 40, 120), # Pink/Magenta Header
            "start": "pirate_ship.png", "end": "treasure.png"
        },
        {
            "main_title": "Car Maze", 
            "sub_title": "HELP THE CAR REACH THE GARAGE BEFORE IT RUNS OUT OF FUEL!",
            "bg_color": (220, 235, 255), # Light Blue Pastel
            "head_color": (230, 80, 0),   # Orange Header
            "start": "car.png", "end": "garage.png"
        }
    ]

    for i in range(1, 11):
        theme = themes[(i-1) % len(themes)]
        cols, rows = 21, 25
        
        # Entry/Exit points at edges
        entry = (0, rows // 2)
        exit_pt = (cols - 1, rows // 2)
        
        mg = MazeGenerator(cols, rows)
        grid = mg.generate(entry, exit_pt)
        
        pdf.add_maze_page(
            grid, theme, i, entry, exit_pt,
            f"assets/{theme['start']}", f"assets/{theme['end']}"
        )

    pdf.output("Custom_Maze_Book.pdf")

if __name__ == "__main__":
    main()
