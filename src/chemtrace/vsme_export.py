"""VSME B3 XLSX export: aggregate invoices.csv into EFRAG VSME template.

Reads monthly energy/emissions records, aggregates to annual totals,
converts units to MWh, classifies into Scope 1/2, and fills the
official EFRAG VSME Digital Template v1.2.0 via openpyxl named ranges.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# EFRAG Fuel Conversion Parameters, Row 16 (Gas/Diesel oil)
# NCV: 43 TJ/Gg, Density: 0.84 kg/L
# 43 TJ/Gg x 0.84 kg/L = 36.12 MJ/L / 3600 MJ/MWh = 0.010033 MWh/L
DIESEL_MWH_PER_LITRE = 0.010033

SCOPE1_TYPES = frozenset({"natural_gas", "diesel"})
SCOPE2_TYPES = frozenset({"electricity"})

REQUIRED_COLUMNS = {"energy_type", "consumption_kwh", "emissions_tco2"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VSMEExportResult:
    """Result of a VSME B3 export operation."""

    output_path: Path
    records_count: int
    period_start: str           # YYYY-MM
    period_end: str             # YYYY-MM
    total_energy_mwh: float
    scope1_tco2eq: float
    scope2_tco2eq: float
    turnover_eur: float | None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _write_named_range(
    wb: openpyxl.Workbook,
    name: str,
    value: object,
    warnings: list[str],
) -> None:
    """Write *value* to the cell identified by named range *name*.

    If the named range is not found or writing fails, a warning is
    appended instead of raising an exception (forward compatibility).
    """
    try:
        dn = wb.defined_names[name]
    except KeyError:
        msg = f"Named range '{name}' not found in template -- skipped"
        logger.warning(msg)
        warnings.append(msg)
        return

    for sheet_title, cell_coord in dn.destinations:
        try:
            wb[sheet_title][cell_coord].value = value
            logger.info("Wrote %s = %s to %s!%s", name, value, sheet_title, cell_coord)
        except Exception as exc:
            msg = f"Failed to write named range '{name}' ({sheet_title}!{cell_coord}): {exc}"
            logger.warning(msg)
            warnings.append(msg)


def _detect_period_range(
    df: pd.DataFrame,
    warnings: list[str],
) -> tuple[str, str]:
    """Return (period_start, period_end) as YYYY-MM strings.

    Appends a warning if the data spans more than 12 months.
    """
    periods = pd.concat([
        df["billing_period_from"].dropna(),
        df["billing_period_to"].dropna(),
    ])
    periods = periods[periods.astype(str).str.strip() != ""]

    if periods.empty:
        warnings.append("No billing period data found in CSV")
        return ("unknown", "unknown")

    period_start = str(periods.min())
    period_end = str(periods.max())

    # Check span length
    try:
        start_parts = period_start.split("-")
        end_parts = period_end.split("-")
        months = (int(end_parts[0]) - int(start_parts[0])) * 12 + (
            int(end_parts[1]) - int(start_parts[1])
        )
        if months > 12:
            warnings.append(
                f"Data spans {months} months ({period_start} to {period_end}). "
                "VSME is annual reporting. Consider filtering input."
            )
    except (IndexError, ValueError):
        pass  # Non-standard format; skip span check

    return (period_start, period_end)


def _aggregate_data(
    df: pd.DataFrame,
    warnings: list[str],
) -> dict:
    """Aggregate monthly records into annual totals.

    Returns a dict with keys: electricity_mwh, gas_mwh, diesel_mwh,
    total_mwh, scope1, scope2, records_count.
    """
    agg = (
        df.groupby("energy_type", as_index=False)
        .agg({"consumption_kwh": "sum", "emissions_tco2": "sum"})
    )
    agg_dict: dict[str, dict[str, float]] = {}
    for _, row in agg.iterrows():
        agg_dict[row["energy_type"]] = {
            "consumption_kwh": float(row["consumption_kwh"]),
            "emissions_tco2": float(row["emissions_tco2"]),
        }

    # Unit conversions (energy_type determines unit of consumption_kwh)
    electricity_mwh = agg_dict.get("electricity", {}).get("consumption_kwh", 0.0) / 1000.0
    gas_mwh = agg_dict.get("natural_gas", {}).get("consumption_kwh", 0.0) / 1000.0
    diesel_mwh = agg_dict.get("diesel", {}).get("consumption_kwh", 0.0) * DIESEL_MWH_PER_LITRE

    # Warn about unknown energy types
    known_types = SCOPE1_TYPES | SCOPE2_TYPES
    for etype, vals in agg_dict.items():
        if etype not in known_types:
            warnings.append(
                f"Unknown energy type '{etype}' with {vals['consumption_kwh']:.1f} "
                "consumption excluded from MWh total"
            )

    total_mwh = electricity_mwh + gas_mwh + diesel_mwh

    # Scope classification
    scope1 = sum(
        agg_dict[t]["emissions_tco2"] for t in agg_dict if t in SCOPE1_TYPES
    )
    scope2 = sum(
        agg_dict[t]["emissions_tco2"] for t in agg_dict if t in SCOPE2_TYPES
    )

    return {
        "electricity_mwh": electricity_mwh,
        "gas_mwh": gas_mwh,
        "diesel_mwh": diesel_mwh,
        "total_mwh": total_mwh,
        "scope1": scope1,
        "scope2": scope2,
        "records_count": len(df),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_vsme_b3(
    csv_path: Path,
    template_path: Path,
    output_path: Path,
    turnover: float | None = None,
) -> VSMEExportResult:
    """Export aggregated energy/emissions data into a VSME B3 XLSX file.

    Parameters
    ----------
    csv_path : Path
        Path to the invoices CSV produced by ``chemtrace parse``.
    template_path : Path
        Path to the blank EFRAG VSME Digital Template v1.2.0 XLSX.
    output_path : Path
        Destination path for the filled XLSX file.
    turnover : float | None
        Annual turnover in EUR (optional, for GHG intensity calc).

    Returns
    -------
    VSMEExportResult
        Summary of the export including computed totals and any warnings.
    """
    warnings: list[str] = []

    # --- Validate inputs ---
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No data found at {csv_path}. Run 'chemtrace parse' first."
        )
    if not template_path.exists():
        raise FileNotFoundError(
            f"VSME template not found at {template_path}. "
            "Reinstall ChemTrace or check data/vsme_templates/."
        )

    df = pd.read_csv(csv_path)
    if len(df) == 0:
        raise ValueError("CSV contains no records. Run 'chemtrace parse' first.")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # --- Aggregate & compute ---
    data = _aggregate_data(df, warnings)
    period_start, period_end = _detect_period_range(df, warnings)

    # --- Fill template ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, output_path)
    wb = openpyxl.load_workbook(output_path)

    # Named ranges
    _write_named_range(wb, "TotalEnergyConsumption", round(data["total_mwh"], 2), warnings)
    _write_named_range(
        wb, "EnergyConsumptionFromElectricity_NonRenewableEnergyMember",
        round(data["electricity_mwh"], 2), warnings,
    )
    _write_named_range(
        wb, "EnergyConsumptionFromElectricity_RenewableEnergyMember", 0, warnings,
    )
    _write_named_range(
        wb, "EnergyConsumptionFromSelfGeneratedElectricity_RenewableEnergyMember", 0, warnings,
    )
    _write_named_range(
        wb, "EnergyConsumptionFromSelfGeneratedElectricity_NonRenewableEnergyMember", 0, warnings,
    )
    _write_named_range(
        wb, "GrossScope1GreenhouseGasEmissions", round(data["scope1"], 2), warnings,
    )
    _write_named_range(
        wb, "GrossLocationBasedScope2GreenhouseGasEmissions", round(data["scope2"], 2), warnings,
    )
    if turnover is not None:
        _write_named_range(wb, "Turnover", turnover, warnings)

    # Boolean gates (direct cell access)
    wb["Environmental Disclosures"]["G10"] = True   # has energy breakdown
    wb["Environmental Disclosures"]["G29"] = False  # no Scope 3 disclosure
    wb["Fuel Converter"]["D23"] = False             # bypass fuel converter

    wb.save(output_path)
    wb.close()
    logger.info("VSME B3 export saved to %s", output_path)

    return VSMEExportResult(
        output_path=output_path,
        records_count=data["records_count"],
        period_start=period_start,
        period_end=period_end,
        total_energy_mwh=round(data["total_mwh"], 2),
        scope1_tco2eq=round(data["scope1"], 2),
        scope2_tco2eq=round(data["scope2"], 2),
        turnover_eur=turnover,
        warnings=warnings,
    )
