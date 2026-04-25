from collections import deque

def solve(grid):
    R,C=len(grid),len(grid[0])
    q=deque([((1,0),[])])
    seen={(1,0)}
    end=(R-2,C-1)
    while q:
        (r,c),path=q.popleft()
        if (r,c)==end:return path+[(r,c)]
        for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
            nr,nc=r+dr,c+dc
            if 0<=nr<R and 0<=nc<C and grid[nr][nc]==0 and (nr,nc) not in seen:
                seen.add((nr,nc)); q.append(((nr,nc),path+[(r,c)]))
    return []
