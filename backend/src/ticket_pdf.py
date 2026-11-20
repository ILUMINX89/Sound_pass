"""Generación en memoria de boletas PDF con QR individual."""

from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def build_tickets_pdf(
    *,
    order_code: str,
    buyer_name: str,
    concert: dict,
    tickets: list[dict],
) -> bytes:
    """Construye una página por boleta, sin emitir ni modificar registros.

    concert:
        artist, tour_name, event_date, event_time,
        venue_name, city, address.

    tickets:
        Lista de objetos con public_code y category.
        Los códigos deben provenir de las boletas persistidas en la BD.
    """
    if not tickets:
        raise ValueError("La orden no tiene boletas para generar.")

    codes = [ticket["public_code"] for ticket in tickets]

    if any(not isinstance(code, str) or not code.strip() for code in codes):
        raise ValueError("Todas las boletas necesitan un código válido.")

    if len(set(codes)) != len(codes):
        raise ValueError("La orden contiene códigos de boleta repetidos.")

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Boletas SoundPass - {order_code}",
        author="SoundPass",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TicketBrand",
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6D28D9"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TicketTitle",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TicketField",
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            spaceAfter=8,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="TicketSmall",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            wordWrap="CJK",
            textColor=colors.HexColor("#475569"),
        )
    )

    def safe(value):
        if value is None or str(value).strip() == "":
            return "No informado"
        return escape(str(value))

    def format_date(value):
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        return safe(value)

    def format_time(value):
        if value is None:
            return "Hora por confirmar"
        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")
        return safe(value)

    def field(label, value):
        return Paragraph(
            f"<b>{safe(label)}:</b> {safe(value)}",
            styles["TicketField"],
        )

    story = []

    for index, ticket in enumerate(tickets, start=1):
        if index > 1:
            story.append(PageBreak())

        public_code = ticket["public_code"]

        # El QR identifica una boleta. No contiene datos personales,
        # tokens de sesión ni enlaces a un validador inexistente.
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(f"soundpass:v1:{public_code}")
        qr.make(fit=True)

        qr_buffer = BytesIO()
        qr.make_image(
            fill_color="black",
            back_color="white",
        ).save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        content = [
            Paragraph("SoundPass", styles["TicketBrand"]),
            Paragraph(
                safe(concert.get("artist")),
                styles["TicketTitle"],
            ),
            Paragraph(
                safe(concert.get("tour_name")),
                styles["TicketSmall"],
            ),
            Spacer(1, 8 * mm),
            field("Fecha", format_date(concert.get("event_date"))),
            field(
                "Hora local del recinto",
                format_time(concert.get("event_time")),
            ),
            field("Recinto", concert.get("venue_name")),
            field("Ciudad", concert.get("city")),
            field("Dirección", concert.get("address")),
            field("Comprador", buyer_name),
            field("Categoría", ticket.get("category")),
            field("Orden", order_code),
            field("Boleta", f"{index} de {len(tickets)}"),
            Spacer(1, 4 * mm),
            Image(qr_buffer, width=55 * mm, height=55 * mm),
            Spacer(1, 3 * mm),
            Paragraph(safe(public_code), styles["TicketSmall"]),
            Spacer(1, 5 * mm),
            Paragraph(
                "Conserva esta boleta y evita compartir su código QR.",
                styles["TicketSmall"],
            ),
        ]

        # Mantiene cada boleta en una sola página, incluso con textos largos.
        story.append(
            KeepInFrame(
                document.width,
                document.height - 8 * mm,
                content,
                mode="shrink",
            )
        )

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawCentredString(
            A4[0] / 2,
            9 * mm,
            f"SoundPass | {doc.page} / {len(tickets)}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )

    return output.getvalue()
