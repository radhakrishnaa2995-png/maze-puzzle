from maze_generator import MazeGenerator
from pdf_builder import MazePDFBuilder

def get_rotation_coords(page_num, cols, rows):
    """FIX 3: Rotation patterns for variety."""
    pattern = page_num % 4
    if pattern == 1: # TOP-LEFT to BOTTOM-RIGHT
        return (1, 0), (cols - 2, rows - 1)
    elif pattern == 2: # TOP-RIGHT to BOTTOM-LEFT
        return (cols - 2, 0), (1, rows - 1)
    elif pattern == 3: # LEFT to RIGHT
        return (0, rows // 2), (cols - 1, rows // 2)
    else: # TOP to BOTTOM
        return (cols // 2, 0), (cols // 2, rows - 1)

def main():
    pdf = MazePDFBuilder()
    # Maze dimensions (Must be ODD numbers for proper wall logic)
    cols, rows = 21, 25 
    
    themes = [
        {"title": "HELP THE CAR REACH THE GARAGE!", "start": "car.png", "end": "car garage.png"},
        {"title": "HELP THE SHIP FIND THE TREASURE!", "start": "pirates ship.png", "end": "planet.jpg"},
        {"title": "HELP THE ROCKET REACH MARS!", "start": "rocket.png", "end": "planet.jpg"},
        {"title": "HELP THE CAT FIND THE MILK!", "start": "cat.png", "end": "milk bowl.png"}
    ]

    for i in range(1, 11): # Generate 10 professional pages
        theme = themes[(i-1) % len(themes)]
        
        # Get Pattern (FIX 3)
        entry, exit = get_rotation_coords(i, cols, rows)
        
        # Generate Maze Logic (FIX 4 & 9)
        mg = MazeGenerator(cols, rows)
        grid = mg.generate(entry, exit, loop_factor=0.12)
        
        # Build PDF Page (FIX 11 Validation is inside the builder)
        pdf.add_maze_page(
            grid, 
            theme["title"], 
            entry, 
            exit, 
            f"assets/icons/icons/{theme['start']}", 
            f"assets/icons/icons/{theme['end']}"
        )

    pdf.output("Professional_Children_Maze_Book.pdf")
    print("✅ Success: Professional PDF generated with centered layout and clamped icons.")

if __name__ == "__main__":
    main()
