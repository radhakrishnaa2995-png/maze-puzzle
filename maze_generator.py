import random

def make_maze(rows, cols, seed=None):
    random.seed(seed)
    grid=[[1]*cols for _ in range(rows)]
    def carve(r,c):
        grid[r][c]=0
        dirs=[(2,0),(-2,0),(0,2),(0,-2)]
        random.shuffle(dirs)
        for dr,dc in dirs:
            nr,nc=r+dr,c+dc
            if 0<nr<rows and 0<nc<cols and grid[nr][nc]==1:
                grid[r+dr//2][c+dc//2]=0
                carve(nr,nc)
    carve(1,1)
    grid[1][0]=0; grid[rows-2][cols-1]=0
    return grid
