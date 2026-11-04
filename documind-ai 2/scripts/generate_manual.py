"""Generate docs/manual.pdf. Requires: python -m pip install reportlab"""

from pathlib import Path
from html import escape
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Preformatted,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

font_dir = Path("/usr/share/fonts/truetype/dejavu")
if font_dir.exists():
    pdfmetrics.registerFont(TTFont("BodyFont", str(font_dir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("BoldFont", str(font_dir / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("MonoFont", str(font_dir / "DejaVuSansMono.ttf")))
else:
    pdfmetrics.registerFont(pdfmetrics.Font("BodyFont", "Helvetica", "WinAnsiEncoding"))
    pdfmetrics.registerFont(
        pdfmetrics.Font("BoldFont", "Helvetica-Bold", "WinAnsiEncoding")
    )
    pdfmetrics.registerFont(pdfmetrics.Font("MonoFont", "Courier", "WinAnsiEncoding"))
styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="BodyES",
        fontName="BodyFont",
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#34483c"),
        spaceAfter=9,
    )
)
styles.add(
    ParagraphStyle(
        name="HeadingES",
        fontName="BoldFont",
        fontSize=15,
        leading=21,
        textColor=colors.HexColor("#254c3b"),
        spaceBefore=19,
        spaceAfter=10,
        keepWithNext=True,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverES",
        fontName="BoldFont",
        fontSize=29,
        leading=36,
        textColor=colors.HexColor("#254c3b"),
        spaceAfter=22,
    )
)
styles.add(
    ParagraphStyle(
        name="CodeES",
        fontName="MonoFont",
        fontSize=8,
        leading=13,
        backColor=colors.HexColor("#f1f5eb"),
        borderPadding=9,
        spaceBefore=7,
        spaceAfter=14,
    )
)
flow = []
code = []
in_code = False
for line in (ROOT / "docs/manual.md").read_text().splitlines():
    if line.startswith("```"):
        if in_code:
            flow.append(KeepTogether([Preformatted("\n".join(code), styles["CodeES"])]))
            code = []
        in_code = not in_code
        continue
    if in_code:
        code.append(line)
        continue
    if not line.strip():
        continue
    if line.startswith("# "):
        flow.append(Paragraph("GUÍA PRÁCTICA · EDICIÓN 1.0", styles["BodyES"]))
        flow.append(Paragraph(escape(line[2:]), styles["CoverES"]))
        flow.append(
            Paragraph(
                "Del PDF a la evidencia: aprende a construir un asistente con fuentes.",
                styles["BodyES"],
            )
        )
        flow.append(Spacer(1, 16))
        continue
    if line.startswith("## "):
        flow.append(Paragraph(escape(line[3:]), styles["HeadingES"]))
    else:
        flow.append(Paragraph(escape(line).replace("→", "&rarr;"), styles["BodyES"]))


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor("#dfe7d7"))
    canvas.line(45, 43, A4[0] - 45, 43)
    canvas.setFont("BodyFont", 8)
    canvas.setFillColor(colors.HexColor("#819075"))
    canvas.drawString(45, 29, "DOCUMIND AI | Manual de desarrollo")
    canvas.drawRightString(A4[0] - 45, 29, str(doc.page))


SimpleDocTemplate(
    str(ROOT / "docs/manual.pdf"),
    pagesize=A4,
    rightMargin=47,
    leftMargin=47,
    topMargin=42,
    bottomMargin=60,
    title="Documind AI - Manual de desarrollo",
    author="Documind AI",
).build(flow, onFirstPage=footer, onLaterPages=footer)
print(ROOT / "docs/manual.pdf")
