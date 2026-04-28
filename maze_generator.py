import random

class MazeGenerator:
    def __init__(self):
        pass

    def generate(self, width, height, entry, exit_pt, loops=0.15):
        # Grid: 1 is wall, 0 is path
        grid = [[1 for _ in range(width)] for _ in range(height)]
        
        def walk(x, y):
            grid[y][x] = 0
            drs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            random.shuffle(drs)
            for dx, dy in drs:
                nx, ny = x + dx * 2, y + dy * 2
                if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == 1:
                    grid[y + dy][x + dx] = 0
                    walk(nx, ny)

        walk(entry[0], entry[1])
        
        # FIX 2: Force real openings at edges
        grid[entry[1]][entry[0]] = 0
        grid[exit_pt[1]][exit_pt[0]] = 0

        # FIX 6: Add loops (10-15%) to make it less "boring grid"
        for _ in range(int(width * height * loops)):
            rx, ry = random.randint(1, width-2), random.randint(1, height-2)
            if grid[ry][rx] == 1:
                # Check if it connects two paths
                if (grid[ry-1][rx] == 0 and grid[ry+1][rx] == 0) or \
                   (grid[ry][rx-1] == 0 and grid[ry][rx+1] == 0):
                    grid[ry][rx] = 0
                    
        return grid
