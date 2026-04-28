import random

class MazeGenerator:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        # Grid: 0=path, 1=wall
        self.grid = [[1 for _ in range(cols)] for _ in range(rows)]
        self.entry = None
        self.exit = None

    def generate(self, entry_pos, exit_pos, loop_factor=0.15):
        """Generates a maze using DFS with added loops for professional feel."""
        self.entry = entry_pos
        self.exit = exit_pos
        
        # Initialize grid with walls
        self.grid = [[1 for _ in range(self.cols)] for _ in range(self.rows)]
        
        stack = [entry_pos]
        self.grid[entry_pos[1]][entry_pos[0]] = 0
        visited = {entry_pos}

        while stack:
            curr_x, curr_y = stack[-1]
            neighbors = []
            
            for dx, dy in [(0, 2), (0, -2), (2, 0), (-2, 0)]:
                nx, ny = curr_x + dx, curr_y + dy
                if 0 <= nx < self.cols and 0 <= ny < self.rows:
                    if (nx, ny) not in visited:
                        neighbors.append((nx, ny))

            if neighbors:
                nx, ny = random.choice(neighbors)
                # Remove wall between
                self.grid[curr_y + (ny - curr_y)//2][curr_x + (nx - curr_x)//2] = 0
                self.grid[ny][nx] = 0
                visited.add((nx, ny))
                stack.append((nx, ny))
            else:
                stack.pop()

        # Add controlled loops to prevent "boring" long straight lines
        self._add_loops(loop_factor)
        
        # Ensure entry and exit are carved out
        self.grid[entry_pos[1]][entry_pos[0]] = 0
        self.grid[exit_pos[1]][exit_pos[0]] = 0
        
        return self.grid

    def _add_loops(self, factor):
        """Break random walls to create loops/alternative paths."""
        for y in range(1, self.rows - 1):
            for x in range(1, self.cols - 1):
                if self.grid[y][x] == 1 and random.random() < factor:
                    # Check if breaking this wall connects two paths
                    if (self.grid[y-1][x] == 0 and self.grid[y+1][x] == 0) or \
                       (self.grid[y][x-1] == 0 and self.grid[y][x+1] == 0):
                        self.grid[y][x] = 0
