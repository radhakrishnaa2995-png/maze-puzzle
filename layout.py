from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

styles = getSampleStyleSheet()
puzzle_title_style = ParagraphStyle(
    "PuzzleTitle",
    parent=styles["Heading4"],
    alignment=1,
    fontName="Helvetica-Bold",
    fontSize=12,
    spaceAfter=6,
)

PAGE_BG = HexColor("#dbe5f1")
PAGE_BORDER = HexColor("#1f1f1f")

DIFFICULTY_LABELS = {
    "*": "Beginner",
    "**": "Learner",
    "***": "Skilled",
    "****": "Advanced",
    "*****": "Expert",
}


def format_difficulty_label(marker):
    label = DIFFICULTY_LABELS.get(marker, marker)
    stars = "<font color='#D4AF37'>" + ("★" * len(marker)) + "</font>"
    return f"{label} {stars}"


def draw_page_background(canvas, doc):
    canvas.saveState()

    # Dark border around page edges
    inset = 0
    canvas.setStrokeColor(PAGE_BORDER)
    canvas.setLineWidth(0.8)
    canvas.setLineJoin(1)
    canvas.rect(inset, inset, doc.pagesize[0] - 2 * inset, doc.pagesize[1] - 2 * inset, stroke=1, fill=0)

    canvas.restoreState()


def _format_grid_data(data, hide_zero=False):
    formatted = []
    for row in data:
        formatted.append(["" if hide_zero and str(value) == "0" else str(value) for value in row])
    return formatted


def draw_grid(data, size=32, hide_zero=False):
    grid_data = _format_grid_data(data, hide_zero=hide_zero)
    table = Table(grid_data, colWidths=size, rowHeights=size)

    style = [
        ('INNERGRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('BOX', (0, 0), (-1, -1), 2.0, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
    ]

    for i in range(0, 9, 3):
        style.append(('LINEBEFORE', (i, 0), (i, 8), 2.0, colors.black))
        style.append(('LINEABOVE', (0, i), (8, i), 2.0, colors.black))

    table.setStyle(TableStyle(style))
    return table


def puzzle_block(puzzle_index, puzzle, star):
    difficulty_text = format_difficulty_label(star)
    title = Paragraph(f"Puzzle {puzzle_index}    {difficulty_text}", puzzle_title_style)
    grid = draw_grid(puzzle, size=30, hide_zero=True)

    block = Table([[title], [grid]], colWidths=[288])
    block.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return block


def solution_block(solution_index, solution):
    return Table([
        [Paragraph(f"S{solution_index}", styles["Normal"])],
        [draw_grid(solution, size=19, hide_zero=False)],
    ])


def generate_pdf(puzzles, solutions, levels, stars):
    doc = SimpleDocTemplate(
        "output/sudoku_mix.pdf",
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    elements = []

    # Index page
    elements.append(Paragraph("INDEX", styles["Heading1"]))
    elements.append(Spacer(1, 12))
    difficulty_order = ["*", "**", "***", "****", "*****"]
    for marker in difficulty_order:
        first_idx = next((idx for idx, s in enumerate(stars) if s == marker), None)
        if first_idx is not None:
            page_num = 2 + (first_idx // 2)
            elements.append(Paragraph(f"{format_difficulty_label(marker)} ............ Page {page_num}", styles["Normal"]))
    elements.append(PageBreak())

    # Puzzles: 2 per page (stacked vertically)
    for i in range(0, len(puzzles), 2):
        elements.append(Spacer(1, 12))
        elements.append(puzzle_block(i + 1, puzzles[i], stars[i]))
        elements.append(Spacer(1, 18))

        if i + 1 < len(puzzles):
            elements.append(puzzle_block(i + 2, puzzles[i + 1], stars[i + 1]))

        if i + 2 < len(puzzles):
            elements.append(PageBreak())

    # Solutions only at the end: 4 per page
    elements.append(PageBreak())
    elements.append(Paragraph("Solutions", styles["Heading1"]))
    elements.append(Spacer(1, 8))

    for i in range(0, len(solutions), 4):
        page_blocks = []
        for j in range(4):
            idx = i + j
            if idx < len(solutions):
                page_blocks.append(solution_block(idx + 1, solutions[idx]))
            else:
                page_blocks.append(Spacer(1, 1))

        grid = Table([
            [page_blocks[0], page_blocks[1]],
            [page_blocks[2], page_blocks[3]],
        ], colWidths=[252, 252])
        grid.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        elements.append(grid)

        if i + 4 < len(solutions):
            elements.append(PageBreak())

    doc.build(elements, onFirstPage=draw_page_background, onLaterPages=draw_page_background)
