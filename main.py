from maze_generator import MazeGenerator
from pdf_builder import MazePDFBuilder

def main():
    pdf = MazePDFBuilder()
    
    # Story-based themes with strict 2-color palettes
    themes = [
        {
            "title": "Pirate Maze", 
            "instruction": "GUIDE THE PIRATE SHIP TO THE TREASURE CHEST!",
            "bg_color": (255, 248, 200), # Pastel Yellow
            "head_color": (199, 21, 133), # Solid Pink
            "start_img": "assets/pirate_ship.png", 
            "end_img": "assets/treasure.png"
        },
        {
            "title": "Car Maze", 
            "instruction": "HELP THE CAR REACH THE GARAGE BEFORE IT RUNS OUT OF FUEL!",
            "bg_color": (225, 240, 255), # Pastel Blue
            "head_color": (210, 70, 0),   # Solid Orange
            "start_img": "assets/car.png", 
            "end_img": "assets/garage.png"
        },
        {
            "title": "Space Journey", 
            "instruction": "HELP THE ROCKET REACH THE PLANET!",
            "bg_color": (240, 225, 255), # Pastel Purple
            "head_color": (75, 0, 130),   # Solid Indigo
            "start_img": "assets/rocket.png", 
            "end_img": "assets/planet.png"
        }
    ]

    for i in range(1, 13): # Generate 12 pages
        theme = themes[(i-1) % len(themes)]
        cols, rows = 23, 27 # Odd numbers work best
        
        # Vary entry/exit points per page
        if i % 2 == 0:
            entry, exit_pt = (0, 5), (cols-1, rows-6)
        else:
            entry, exit_pt = (5, 0), (cols-10, rows-1)
        
        mg = MazeGenerator(cols, rows)
        grid = mg.generate(entry, exit_pt)
        
        pdf.add_maze_page(grid, theme, i, entry, exit_pt)

    pdf.output("Professional_Story_Maze_Book.pdf")
    print("PDF Created: Professional_Story_Maze_Book.pdf")

if __name__ == "__main__":
    main()
