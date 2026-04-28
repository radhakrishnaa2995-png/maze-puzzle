import random

class MazeGenerator:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.grid = [[1 for _ in range(cols)] for _ in range(rows)]

    def generate(self, entry_pos, exit_pos):
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
                self.grid[curr_y + (ny - curr_y)//2][curr_x + (nx - curr_x)//2] = 0
                self.grid[ny][nx] = 0
                visited.add((nx, ny))
                stack.append((nx, ny))
            else:
                stack.pop()
        
        # Ensure path to entry/exit edges
        self.grid[entry_pos[1]][entry_pos[0]] = 0
        self.grid[exit_pos[1]][exit_pos[0]] = 0
        return self.grid
