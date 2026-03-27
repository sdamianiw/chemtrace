"""Configurable regex patterns and column aliases for PDF invoice parsing.

Adding support for a new invoice format = add patterns here. No code changes needed.
"""

from __future__ import annotations

# Regex patterns applied to full extracted page text.
# Each key maps to a list of patterns tried in order (first match wins).
PATTERNS: dict[str, list[str]] = {
    # Header fields
    "invoice_number": [
        r"Invoice\s+number\s*:\s*(\S+)",
        r"Invoice\s+no\.?\s*:\s*(\S+)",
        r"Rechnungsnummer\s*:\s*(\S+)",
    ],
    "invoice_date": [
        r"Invoice\s+date\s*:\s*(\d{4}-\d{2}-\d{2})",
        r"Rechnungsdatum\s*:\s*(\d{2}\.\d{2}\.\d{4})",
    ],
    "billing_period": [
        # ISO format: "Billing period: 2024-01-01 to 2024-01-31"
        r"Billing\s+period\s*:\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
        # German format: "Abrechnungszeitraum: 01.01.2024 – 31.01.2024"
        r"Abrechnungszeitraum\s*:\s*(\d{2}\.\d{2}\.\d{4})\s*[-\u2013bis]+\s*(\d{2}\.\d{2}\.\d{4})",
    ],
    "customer": [
        r"Customer\s*:\s*(.+)",
        r"Kunde\s*:\s*(.+)",
    ],
    "site": [
        r"Site\s*:\s*(.+)",
        r"Standort\s*:\s*(.+)",
    ],
    "address": [
        r"Address\s*:\s*(.+)",
        r"Adresse\s*:\s*(.+)",
    ],
    "currency": [
        r"Currency\s*:\s*(\w+)",
        r"W[äa]hrung\s*:\s*(\w+)",
    ],

    # Footer totals — match amount before optional "EUR" suffix
    "subtotal": [
        r"Subtotal\s+energy\s+charges\s*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"Subtotal\s*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"Zwischensumme\s*:\s*([\d.,]+)\s*(?:EUR)?",
    ],
    "network_levies": [
        r"Network\s*&\s*levies[^:]*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"Netzentgelte[^:]*:\s*([\d.,]+)\s*(?:EUR)?",
    ],
    "vat": [
        r"VAT\s+\d+%\s*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"MwSt\.?\s+\d+%\s*:\s*([\d.,]+)\s*(?:EUR)?",
    ],
    "total": [
        r"Total\s+amount\s+due\s*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"Total\s*:\s*([\d,]+\.?\d*)\s*(?:EUR)?",
        r"Gesamtbetrag\s*:\s*([\d.,]+)\s*(?:EUR)?",
        r"Gesamt\s*:?\s*([\d.,]+)\s*(?:EUR)?",
    ],

    # Energy type keyword classification (applied to lowercase cell text)
    "energy_type_keywords": {
        "electricity": ["electricity", "strom", "electric"],
        "natural_gas": ["natural gas", "erdgas", "process heat"],
        "diesel": ["diesel", "kraftstoff", "fuel", "logistics"],
    },
}

# Column name aliases for dynamic table column mapping.
# Keys are canonical field names; values are substrings matched case-insensitively
# against the table header row. First match wins.
COLUMN_ALIASES: dict[str, list[str]] = {
    "meter_id": ["meter id", "meter-id", "zählernummer", "zaehlernummer", "zaehler-id"],
    "energy_type": ["energy type", "energieart", "energietyp"],
    "period_from": ["from", "von"],
    "period_to": ["to", "bis"],
    "consumption": ["consumption", "verbrauch"],
    "unit_price": ["unit price", "einheitspreis", "stueckpreis", "stückpreis"],
    "amount": ["amount", "betrag", "summe"],
}
