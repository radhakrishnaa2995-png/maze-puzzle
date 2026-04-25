from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from maze_generator import make_maze
from solver import solve
from shapes import pick_shape
import random
W,H=A4
PASTELS=[colors.lavender,colors.mistyrose,colors.lightcyan,colors.beige,colors.honeydew]

def draw_maze(c,grid,show=False,path=None):
    cell=14; ox=60; oy=120
    for r,row in enumerate(grid):
        for col,v in enumerate(row):
            x=ox+col*cell; y=oy+r*cell
            if v==1:
                c.rect(x,y,cell,cell,fill=1)
    if show and path:
        c.setStrokeColor(colors.red); c.setLineWidth(2)
        pts=[(ox+cc*cell+cell/2, oy+rr*cell+cell/2) for rr,cc in path]
        for i in range(len(pts)-1): c.line(*pts[i],*pts[i+1])

def build_book(file,pages,seed=1):
    random.seed(seed)
    c=canvas.Canvas(file,pagesize=A4)
    sols=[]
    for p in range(pages+2):
        c.setFillColor(PASTELS[(p+seed)%len(PASTELS)]); c.rect(0,0,W,H,fill=1,stroke=0)
        c.setStrokeColor(colors.black); c.setLineWidth(3); c.rect(15,15,W-30,H-30)
        if p==0:
            c.setFont('Helvetica-Bold',28); c.drawCentredString(W/2,H/2,'Maze Puzzle Book')
        elif p==1:
            c.setFont('Helvetica',18); c.drawString(80,H-80,'Start Easy → Hard')
        else:
            idx=p-2
            grid=make_maze(21,21,seed*100+idx)
            path=solve(grid); sols.append((grid,path))
            c.setFont('Helvetica-Bold',16)
            c.drawString(60,H-50,f'Puzzle {idx+1} - {pick_shape(idx)}')
            draw_maze(c,grid)
        c.showPage()
    for i,(g,path) in enumerate(sols,1):
        c.setFillColor(colors.white); c.rect(0,0,W,H,fill=1,stroke=0)
        c.drawString(60,H-50,f'Solution {i}')
        draw_maze(c,g,True,path)
        c.showPage()
    c.save()
