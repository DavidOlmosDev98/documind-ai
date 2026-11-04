"""Generate the fictitious, two-page reference document used by demos and tests."""

from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
fonts = Path("/usr/share/fonts/truetype/dejavu")
if fonts.exists():
    pdfmetrics.registerFont(TTFont("Body", str(fonts / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("Heading", str(fonts / "DejaVuSans-Bold.ttf")))
else:
    pdfmetrics.registerFont(pdfmetrics.Font("Body", "Helvetica", "WinAnsiEncoding"))
    pdfmetrics.registerFont(
        pdfmetrics.Font("Heading", "Helvetica-Bold", "WinAnsiEncoding")
    )

path = ROOT / "examples" / "guia-equipo.pdf"
path.parent.mkdir(exist_ok=True)
c = canvas.Canvas(str(path), pagesize=(595, 842))
c.setTitle("Guía del equipo Nébula — Documento ficticio")


def page(number, title, sections):
    c.setFillColor(HexColor("#7460b0"))
    c.setFont("Heading", 10)
    c.drawString(52, 785, "NÉBULA / GUÍA DEL EQUIPO")
    c.setFillColor(HexColor("#24302c"))
    c.setFont("Heading", 24)
    c.drawString(52, 728, title)
    y = 679
    import textwrap

    for heading, body in sections:
        c.setFont("Heading", 13)
        c.drawString(52, y, heading)
        y -= 29
        c.setFont("Body", 11)
        for line in textwrap.wrap(body, width=74):
            c.drawString(52, y, line)
            y -= 20
        y -= 31
    c.setFillColor(HexColor("#8d968f"))
    c.setFont("Body", 9)
    c.drawString(
        52, 50, "Documento ficticio para demostración. No representa una empresa real."
    )
    c.drawRightString(543, 50, str(number))
    c.showPage()


page(
    1,
    "Trabajar con equilibrio.",
    [
        (
            "Vacaciones y descansos",
            "El equipo dispone de 22 días laborables de vacaciones al año. Las vacaciones se solicitan con al menos 10 días de anticipación a través del portal de personas. La aprobación corresponde al responsable del equipo.",
        ),
        (
            "Trabajo remoto",
            "El trabajo remoto está permitido hasta 3 días por semana. Los martes y jueves son días presenciales de colaboración. El horario de coincidencia del equipo es de 10:00 a 14:00.",
        ),
        (
            "Equipamiento",
            "Cada integrante recibe una computadora portátil y un monitor. El presupuesto anual para accesorios de trabajo es de 200 euros. Los gastos requieren comprobante y aprobación previa.",
        ),
    ],
)
page(
    2,
    "Aprender y cuidarnos.",
    [
        (
            "Formación y aprendizaje",
            "El presupuesto de formación es de 600 euros por persona al año. Puede utilizarse en cursos, libros y conferencias relacionados con el puesto. Se requiere la aprobación del responsable antes de realizar la compra.",
        ),
        (
            "Soporte técnico",
            "Las incidencias técnicas se reportan en el portal de soporte. El horario de atención es de lunes a viernes de 9:00 a 18:00. Para incidencias críticas se debe contactar al responsable de guardia.",
        ),
        (
            "Reembolsos",
            "Los reembolsos aprobados se procesan en un plazo de 15 días naturales. La solicitud debe incluir el comprobante y la categoría del gasto. No se aceptan solicitudes sin comprobante.",
        ),
    ],
)
c.save()
print(path)
