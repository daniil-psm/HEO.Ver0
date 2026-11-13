"""Zentrale Zuordnung der System- und DG-KPIs zu Haupt- und Zusatzbereich.

Systemkennzahlen werden über ihre Summary-Schlüssel adressiert. Für Werte aus
dem DG-Bericht gilt ``report:<Tabellenblatt>:<Originalbezeichnung>``; einzelne
Werte können hier vor der allgemeinen ``report:*``-Regel übersteuert werden.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Literal


KpiDialogView = Literal["main", "more"]


KPI_DIALOG_FIELDS: dict[str, KpiDialogView] = {
    # In Einzel- und Vergleichsansicht unmittelbar sichtbare Systemkennzahlen.
    "annualized_total_cost_eur_per_a": "main",
    "investment_cost_eur": "main",
    "investment_cost_central_devices_eur": "main",
    "average_operation_cost_eur_per_a": "main",
    "average_co2_emissions_t_per_a": "main",
    "average_energy_autonomy_percent": "main",
    "average_demand_cover_percent": "main",
    "electric_peak_demand_kw": "main",
    "maximum_grid_feed_in_kw": "main",
    # Zusätzliche Systemkennzahlen der Einzelansicht.
    "investment_cost_central_eur": "more",
    "investment_cost_decentral_eur": "more",
    "annualized_fixed_cost_decentral_eur_per_a": "more",
    "annualized_fixed_cost_central_eur_per_a": "more",
    "net_energy_demand_mwh_per_a": "more",
    "standard_heat_load_kw": "more",
    "average_supply_cover_percent": "more",
    "observation_time_years": "more",
    # Der vollständige DG-Bericht bleibt zunächst im ausklappbaren Bereich.
    "report:*": "more",
}


def kpi_dialog_view(key: str) -> KpiDialogView:
    """Liefert den Bereich eines KPI-Schlüssels oder DG-Berichtsfelds."""

    if key in KPI_DIALOG_FIELDS:
        return KPI_DIALOG_FIELDS[key]
    for pattern, view in KPI_DIALOG_FIELDS.items():
        if "*" in pattern and fnmatchcase(key, pattern):
            return view
    return "more"
