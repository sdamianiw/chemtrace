"""Generate synthetic invoice PDFs for ChemTrace testing.

Dev-only script. Requires: pip install reportlab
Output: data/sample_invoices/Invoice_Diesel_Feb2024_RuhrChem.pdf
        data/sample_invoices/Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_invoices"


def _build_header_table(rows: list[list[str]]) -> Table:
    """Build a two-column header table (label: value) without visible grid."""
    t = Table(rows, colWidths=[55 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _build_data_table(header: list[str], rows: list[list[str]]) -> Table:
    """Build a data table with grid lines (extractable by pdfplumber)."""
    data = [header] + rows
    t = Table(data)
    t.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        # Grid for pdfplumber extraction
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_diesel_invoice() -> Path:
    """Generate Invoice_Diesel_Feb2024_RuhrChem.pdf."""
    output_path = OUTPUT_DIR / "Invoice_Diesel_Feb2024_RuhrChem.pdf"
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    # Vendor name (bold heading)
    vendor_style = ParagraphStyle(
        "VendorName",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=10,
    )
    story.append(Paragraph("NRW Energie Versorgung GmbH", vendor_style))
    story.append(Spacer(1, 4 * mm))

    # Header fields
    header_rows = [
        ["Customer:", "RuhrChem Lubricants GmbH"],
        ["Site:", "Essen Blending Plant"],
        ["Address:", "Vogelheimer Strasse 120, 45329 Essen, Germany"],
        ["Invoice number:", "DI-2024-001"],
        ["Invoice date:", "2024-03-08"],
        ["Billing period:", "2024-02-01 to 2024-02-29"],
        ["Currency:", "EUR"],
    ]
    story.append(_build_header_table(header_rows))
    story.append(Spacer(1, 6 * mm))

    # Line items table
    table_header = [
        "Line", "Meter ID", "Energy type", "From", "To",
        "Consumption (litres)", "Unit price (EUR/litre)", "Amount (EUR)",
    ]
    table_rows = [
        ["1", "D-ESSEN-FLEET-01", "Diesel - Internal logistics",
         "2024-02-01", "2024-02-29", "8,500", "1.4200", "12,070.00"],
    ]
    story.append(_build_data_table(table_header, table_rows))
    story.append(Spacer(1, 6 * mm))

    # Footer totals
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
    )
    footer_text = (
        "Subtotal energy charges: 12,070.00 EUR<br/>"
        "Network &amp; levies (approx. 5%): 603.50 EUR<br/>"
        "VAT 19%: 2,407.97 EUR<br/>"
        "Total amount due: 15,081.47 EUR"
    )
    story.append(Paragraph(footer_text, footer_style))
    story.append(Spacer(1, 6 * mm))

    # Notes
    notes_style = ParagraphStyle(
        "Notes",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#555555"),
    )
    notes = (
        "Notes: Consumption values are based on fleet tracking records. "
        "Diesel consumption falls under Scope 1 direct emissions. "
        "Emission factors are applied separately according to the "
        "customer's chosen methodology."
    )
    story.append(Paragraph(notes, notes_style))

    doc.build(story)
    return output_path


def generate_stadtwerke_invoice() -> Path:
    """Generate Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf."""
    output_path = OUTPUT_DIR / "Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf"
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    # Vendor name
    vendor_style = ParagraphStyle(
        "VendorName",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=10,
    )
    story.append(Paragraph("Stadtwerke Essen AG", vendor_style))
    story.append(Spacer(1, 4 * mm))

    # Header fields (German)
    header_rows = [
        ["Kunde:", "RuhrChem Lubricants GmbH"],
        ["Standort:", "Essen Blending Plant"],
        ["Adresse:", "Vogelheimer Strasse 120, 45329 Essen, Germany"],
        ["Rechnungsnummer:", "SWE-2024-0847"],
        ["Rechnungsdatum:", "15.03.2024"],
        ["Abrechnungszeitraum:", "01.02.2024 - 28.02.2024"],
        ["Waehrung:", "EUR"],
    ]
    story.append(_build_header_table(header_rows))
    story.append(Spacer(1, 6 * mm))

    # Line items table (German headers)
    table_header = [
        "Zeile", "Zaehler-ID", "Energieart", "Von", "Bis",
        "Verbrauch (kWh)", "Stueckpreis (EUR/kWh)", "Betrag (EUR)",
    ]
    table_rows = [
        ["1", "E-ESSEN-PLANT-01", "Strom - Produktion",
         "2024-02-01", "2024-02-28", "415,300", "0.1810", "75,169.30"],
    ]
    story.append(_build_data_table(table_header, table_rows))
    story.append(Spacer(1, 6 * mm))

    # Footer totals (German)
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
    )
    footer_text = (
        "Zwischensumme: 75,169.30 EUR<br/>"
        "Netzentgelte &amp; Umlagen (ca. 12%): 9,020.32 EUR<br/>"
        "MwSt 19%: 15,996.03 EUR<br/>"
        "Gesamt: 100,185.65 EUR"
    )
    story.append(Paragraph(footer_text, footer_style))
    story.append(Spacer(1, 6 * mm))

    # Notes (German)
    notes_style = ParagraphStyle(
        "Notes",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#555555"),
    )
    notes = (
        "Hinweise: Die Verbrauchswerte basieren auf Zaehlerstaenden und "
        "koennen geschaetzte Zeitraeume enthalten. Die mit diesem Verbrauch "
        "verbundenen Emissionen fallen unter Scope 2 (marktbasiert) und werden "
        "separat berechnet."
    )
    story.append(Paragraph(notes, notes_style))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p1 = generate_diesel_invoice()
    print(f"Generated: {p1}")
    p2 = generate_stadtwerke_invoice()
    print(f"Generated: {p2}")
