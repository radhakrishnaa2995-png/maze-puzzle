from maze_generator import MazeGenerator
from pdf_builder import MazePDFBuilder

def main():
    pdf = MazePDFBuilder()
    gen = MazeGenerator()
    
    # Story Themes
    themes = [
        {"name": "Pirate Quest", "story": "Help the pirate ship reach the treasure chest!", "start_img": "assets/ship.png", "end_img": "assets/treasure.png"},
        {"name": "Space Race", "story": "Guide the rocket to the mystery planet!", "start_img": "assets/rocket.png", "end_img": "assets/planet.png"},
        {"name": "City Drive", "story": "Help the car reach the garage safely!", "start_img": "assets/car.png", "end_img": "assets/garage.png"}
    ]

    # FIX 10: Entry/Exit Variation Patterns
    # (entry_coord, exit_coord)
    patterns = [
        ((0, 5), (20, 15)),   # Left to Right
        ((5, 0), (15, 20)),   # Top to Bottom
        ((0, 0), (20, 20)),   # Corner to Corner
        ((10, 0), (0, 15))    # Top to Left
    ]

    for i in range(1, 31): # 30 Pages
        theme = themes[(i-1) % len(themes)]
        pattern = patterns[(i-1) % len(patterns)]
        
        # FIX 3: Difficulty System (Easy, Medium, Hard)
        if i <= 10:
            diff, stars, size = "Easy", 1, 15
        elif i <= 20:
            diff, stars, size = "Medium", 2, 21
        else:
            diff, stars, size = "Hard", 3, 31

        entry, exit_pt = pattern
        # Adjust pattern to fit grid size
        entry = (min(entry[0], size-1), min(entry[1], size-1))
        exit_pt = (min(exit_pt[0], size-1), min(exit_pt[1], size-1))

        grid = gen.generate(size, size, entry, exit_pt)
        
        page_data = {
            "num": i,
            "grid": grid,
            "theme": theme,
            "difficulty": diff,
            "star_count": stars,
            "entry": entry,
            "exit": exit_pt
        }
        
        pdf.add_maze_page(page_data)

    pdf.output("KDP_Premium_Maze_Book.pdf")
    print("Success: KDP_Premium_Maze_Book.pdf generated.")

if __name__ == "__main__":
    main()
