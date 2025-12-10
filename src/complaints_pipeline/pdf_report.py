from __future__ import annotations

from io import BytesIO
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .schema import PDF_SECTIONS


def build_pdf_bytes(title: str, fields: Dict[str, Any]) -> bytes:
    """Generate a PDF in the same section order as QAF-12-01 (rev 04)."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    c.setTitle(title)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title)

    y = height - 80

    def new_line(pad=14):
        nonlocal y
        y -= pad
        if y < 60:
            c.showPage()
            y = height - 60

    def draw_text(text: str, font="Helvetica", size=11):
        nonlocal y
        c.setFont(font, size)
        # Wrap naive by char count
        max_chars = 105
        line = str(text)
        while len(line) > max_chars:
            c.drawString(50, y, line[:max_chars])
            new_line()
            line = "    " + line[max_chars:]
        c.drawString(50, y, line)
        new_line()

    for section_title, keys in PDF_SECTIONS:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, section_title)
        new_line(18)

        for k in keys:
            val = fields.get(k, "")
            draw_text(f"{k}: {val}")

        new_line(10)

    c.showPage()
    c.save()
    return buf.getvalue()
