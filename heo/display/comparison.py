"""HEO-Bezeichnungen, Hilfetexte und Zahlenformate für DG-Ergebnisvergleiche."""

from __future__ import annotations

import math
import re
from typing import Any

from .number_format import format_german_number
from .kpi_dialog_layout import kpi_dialog_view

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
OBJECTIVE_PRESENTATION = {
    "economic": {
        "label": "Ökonomischer Optimierungsfokus",
        "short_label": "Ökonomisch",
        "color": "#f2b43c",
    },
    "ecological": {
        "label": "Ökologischer Optimierungsfokus",
        "short_label": "Ökologisch",
        "color": "#63d58b",
    },
}

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
KPI_PRESENTATION = (
    ("annualized_total_cost_eur_per_a", "Jährliche Gesamtkosten", "€/a", 0),
    ("investment_cost_eur", "Investition gesamt", "€", 0),
    ("average_operation_cost_eur_per_a", "Mittlere Betriebskosten", "€/a", 0),
    ("average_co2_emissions_t_per_a", "CO₂-Emissionen", "t/a", 2),
    (
        "average_energy_autonomy_percent",
        "Zeitlicher Autarkiegrad",
        "%",
        1,
    ),
    (
        "average_demand_cover_percent",
        "Elektrischer Bedarfsdeckungsgrad",
        "%",
        1,
    ),
    ("electric_peak_demand_kw", "Spitzen-Netzbezug", "kW", 1),
    ("maximum_grid_feed_in_kw", "Maximale Netzeinspeisung", "kW", 1),
)

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
KPI_HELP = {
    "annualized_total_cost_eur_per_a": "Jährliche Gesamtkosten aus annualisierten Fixkosten und mittleren Betriebskosten des Energiesystems.",
    "investment_cost_eur": "Investitionssumme der zentralen und dezentralen Anlagen einschließlich des zentralen Netzes.",
    "investment_cost_central_devices_eur": "Investitionssumme der zentralen Anlagen; Netze und dezentrale Anlagen sind hier nicht enthalten.",
    "average_operation_cost_eur_per_a": "Mittlere jährliche Betriebskosten des gesamten Energiesystems über die betrachteten Stützjahre.",
    "average_co2_emissions_t_per_a": "Mittlere jährliche CO₂-Emissionen des gesamten Energiesystems über die betrachteten Stützjahre.",
    "average_energy_autonomy_percent": "Anteil der Zeitschritte ohne Strombezug aus dem öffentlichen Netz.",
    "average_demand_cover_percent": "Anteil des bilanzierten elektrischen Restbedarfs, der zeitgleich durch Strom aus dem Quartier gedeckt wird.",
    "electric_peak_demand_kw": "Höchste elektrische Bezugsleistung am Netzanschlusspunkt.",
    "maximum_grid_feed_in_kw": "Höchste elektrische Einspeiseleistung am Netzanschlusspunkt.",
    "investment_cost_central_eur": "Investitionssumme der zentralen Anlagen und des zentralen Netzes.",
    "investment_cost_decentral_eur": "Investitionssumme der dezentralen Anlagen in den Gebäuden.",
    "annualized_fixed_cost_decentral_eur_per_a": "Auf ein Jahr umgelegte Fixkosten der dezentralen Anlagen.",
    "annualized_fixed_cost_central_eur_per_a": "Auf ein Jahr umgelegte Fixkosten der zentralen Anlagen und des Netzes.",
    "net_energy_demand_mwh_per_a": "Summe des jährlichen Wärme-, Kälte-, Strom-, Warmwasser- und Elektromobilitätsbedarfs.",
    "standard_heat_load_kw": "Summe der für die Heizung angesetzten Norm-Heizlasten der Gebäude.",
    "average_supply_cover_percent": "Anteil der bilanzierten Stromeinspeisung, der zeitgleich im Quartier genutzt wird.",
    "observation_time_years": "Zeitraum, über den die Wirtschaftlichkeit der Anlagen bewertet wird.",
}

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
SUMMARY_DETAILS = (
    ("investment_cost_central_eur", "Investition zentral inkl. Netz", "€", 0),
    ("investment_cost_decentral_eur", "Investition dezentral", "€", 0),
    ("annualized_fixed_cost_decentral_eur_per_a", "Fixkosten dezentral, annualisiert", "€/a", 0),
    ("annualized_fixed_cost_central_eur_per_a", "Fixkosten zentral, annualisiert", "€/a", 0),
    ("net_energy_demand_mwh_per_a", "Nettoenergiebedarf", "MWh/a", 1),
    ("standard_heat_load_kw", "Norm-Heizlast", "kW", 1),
    ("average_supply_cover_percent", "Elektrischer Angebotsdeckungsgrad", "%", 1),
    ("observation_time_years", "Betrachtungszeitraum", "Jahre", 0),
)

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
DG_LABELS = {
    "Peak Demand district": "Spitzen-Netzbezug",
    "Peak Injection district": "Maximale Netzeinspeisung",
    "Peak to Valley": "Spitzen-Tal-Differenz",
    "Electricity Injection to Grid": "Stromeinspeisung ins Netz",
    "Electricity Demand from Grid": "Strombezug aus dem Netz",
    "Electricity Injection within District": "Stromeinspeisung im Quartier",
    "Electricity Demand within District": "Strombedarf im Quartier",
    "Demand Cover Factor": "Elektrischer Bedarfsdeckungsgrad",
    "Supply Cover Factor": "Elektrischer Angebotsdeckungsgrad",
    "Autonomy": "Zeitlicher Autarkiegrad",
    "Operation Costs": "Betriebskosten",
    "Average Operation Costs": "Mittlere Betriebskosten",
    "CO2 Emissions": "CO₂-Emissionen",
    "Average CO2 Emissions": "Mittlere CO₂-Emissionen",
    "Revenue from Electricity Feed-in": "Erlös aus Stromeinspeisung",
    "Sum design Heat Load": "Norm-Heizlast",
    "Sum design Cooling Load": "Norm-Kühllast",
    "Heating demand": "Heizwärmebedarf",
    "Cooling demand": "Kältebedarf",
    "Electricity demand (Plug loads)": "Strombedarf (Geräte)",
    "EV demand": "Elektromobilitätsbedarf",
    "DHW demand": "Warmwasserbedarf",
    "Heat demand Peak": "Spitzen-Heizwärmebedarf",
    "DHW demand Peak": "Spitzen-Warmwasserbedarf",
    "Cooling demand Peak": "Spitzen-Kältebedarf",
    "EV demand Peak": "Spitzen-Elektromobilitätsbedarf",
    "Yearly ICE Fuel Consumption": "Kraftstoffverbrauch Verbrenner",
    "Annualized Fixed Costs Decentral": "Fixkosten dezentral, annualisiert",
    "Annualized Fixed Costs Central": "Fixkosten zentral, annualisiert",
    "Residential Area": "Wohnfläche",
    "Mixed Area": "Gemischt genutzte Fläche",
    "Non-Residential Area": "Nichtwohnfläche",
    "Number of Flats in district": "Wohnungen im Quartier",
    "Number of Occupants in district": "Bewohner im Quartier",
    "Grid Electricity Consumption": "Strombezug aus dem Netz",
    "Buildings Electricity Consumption": "Strombedarf der Gebäude",
    "Grid Electricity Injection": "Stromeinspeisung ins Netz",
    "Buildings Electricity Injection": "Stromeinspeisung der Gebäude",
    "Total CO2 Emissions": "CO₂-Emissionen gesamt",
}

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
DG_WORDS = {
    "Gas": "Gas", "Biomass": "Biomasse", "Waste": "Abfall", "Hydrogen": "Wasserstoff",
    "Oil": "Öl", "District Heat": "Fernwärme", "Electricity": "Strom",
    "Consumption": "Verbrauch", "Costs": "Kosten", "Grid": "Netz", "Heat": "Wärme",
}

def numeric_value(value: Any) -> float | None:
    """Liefert einen endlichen Zahlenwert oder None bei fehlender oder ungültiger Eingabe."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def comparison_summary(bundle: dict[str, Any] | None) -> dict[str, Any]:
    """Liefert das Summary-Dict eines Ergebnisbündels oder ein leeres Dict."""

    summary = (bundle or {}).get("summary")
    return summary if isinstance(summary, dict) else {}

def objective_heading(scenario_name: str, objective: str) -> str:
    """Bildet die Überschrift aus Szenarioname und Optimierungsfokus."""

    scenario = str(scenario_name or "Szenario").strip() or "Szenario"
    presentation = OBJECTIVE_PRESENTATION[objective]
    label = presentation["label"]
    return f"{scenario} - {label[0].lower()}{label[1:]}"

def formatted_kpi(value: Any, unit: str, decimals: int) -> str:
    """Formatiert einen KPI mit deutscher Zahlendarstellung oder einem Strich bei fehlendem Wert."""

    number = numeric_value(value)
    if number is None:
        return "–"
    rounded = round(number, decimals)
    # Solver-Toleranzen können fachlich nullwertige Ergebnisse als sehr kleine
    # negative Zahlen liefern. Nach dem Runden darf daraus kein „-0“ werden.
    if rounded == 0:
        rounded = 0
    kind = "integer" if decimals == 0 else "decimal"
    formatted = format_german_number(rounded, kind=kind)
    return f"{formatted} {unit}".rstrip()

def _dg_label(raw: str) -> tuple[str, str, int, float]:
    """Liefert deutsche Bezeichnung, Einheit, Dezimalstellen und Skalierung einer DG-Berichtszeile."""

    match = re.fullmatch(r"(.+?) \(([^()]*)\)", raw)
    name, unit = (match.group(1), match.group(2)) if match else (raw, "")
    translated = DG_LABELS.get(name)
    if translated is None:
        translated = name
        for english, german in DG_WORDS.items():
            translated = re.sub(rf"\b{re.escape(english)}\b", german, translated)
    translated = translated.replace(" Unsubsidized", " ohne Förderung")
    if unit in {"-", "Time Fraction"}:
        return translated, "%" if unit == "Time Fraction" or name.endswith("Factor") else "", 1, 100 if unit == "Time Fraction" or name.endswith("Factor") else 1
    return translated, unit, 0 if unit in {"€", "€/a", "liters/a"} else 1, 1

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
DG_REPORT_HELP = {
    "Peak Demand district": "Höchste elektrische Bezugsleistung des Quartiers am Netzanschlusspunkt.",
    "Peak Injection district": "Höchste elektrische Einspeiseleistung des Quartiers am Netzanschlusspunkt.",
    "Peak to Valley": "Differenz zwischen höchstem und niedrigstem Wert des elektrischen Netzlastprofils.",
    "Electricity Injection to Grid": "Jährlich in das öffentliche Stromnetz eingespeiste Energie.",
    "Electricity Demand from Grid": "Jährlich aus dem öffentlichen Stromnetz bezogene Energie.",
    "Electricity Injection within District": "Jährliche Stromeinspeisung der Gebäude innerhalb des Quartiers.",
    "Electricity Demand within District": "Jährlicher bilanzieller Strombedarf innerhalb des Quartiers.",
    "Demand Cover Factor": KPI_HELP["average_demand_cover_percent"],
    "Supply Cover Factor": KPI_HELP["average_supply_cover_percent"],
    "Autonomy": KPI_HELP["average_energy_autonomy_percent"],
    "Operation Costs": "Betriebskosten des gesamten Energiesystems im angegebenen Stützjahr.",
    "Average Operation Costs": KPI_HELP["average_operation_cost_eur_per_a"],
    "CO2 Emissions": "CO₂-Emissionen des gesamten Energiesystems im angegebenen Stützjahr.",
    "Average CO2 Emissions": KPI_HELP["average_co2_emissions_t_per_a"],
    "Revenue from Electricity Feed-in": "Erlös aus der Einspeisung von Strom in das öffentliche Netz.",
    "Sum design Heat Load": KPI_HELP["standard_heat_load_kw"],
    "Sum design Cooling Load": "Summe der für die Kühlung angesetzten Norm-Kühllasten der Gebäude.",
    "Yearly ICE Fuel Consumption": "Jährlicher Kraftstoffverbrauch der Fahrzeuge mit Verbrennungsmotor.",
    "Residential Area": "Gesamte Wohnfläche der Gebäude im Quartier.",
    "Mixed Area": "Gesamte gemischt genutzte Gebäudefläche im Quartier.",
    "Non-Residential Area": "Gesamte Nichtwohnfläche der Gebäude im Quartier.",
    "Number of Flats in district": "Anzahl der Wohnungen im Quartier.",
    "Number of Occupants in district": "Anzahl der Bewohnerinnen und Bewohner im Quartier.",
    "Capacity": "Optimierte Nennleistung oder Speicherkapazität dieser Anlage.",
    "Grid Electricity Consumption": "Strombezug aus dem öffentlichen Netz über den gesamten Betrachtungszeitraum.",
    "Buildings Electricity Consumption": "Strombedarf der Gebäude über den gesamten Betrachtungszeitraum.",
    "Grid Electricity Injection": "Stromeinspeisung in das öffentliche Netz über den gesamten Betrachtungszeitraum.",
    "Buildings Electricity Injection": "Stromeinspeisung der Gebäude über den gesamten Betrachtungszeitraum.",
    "Total CO2 Emissions": "CO₂-Emissionen des gesamten Energiesystems über den gesamten Betrachtungszeitraum.",
}

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
DG_CARRIER_NAMES = {
    "Grid Electricity": "Netzstrom",
    "District Heat": "Fernwärme",
    "Biomass": "Biomasse",
    "Waste": "Abfall",
    "Hydrogen": "Wasserstoff",
    "Gas": "Gas",
    "Oil": "Öl",
}

# Zentrale HEO-Texte und Zuordnungen für Ergebniskennzahlen.
DG_DEVICE_METRIC_HELP = {
    "gen_heat": "Erzeugte Wärmeenergie",
    "gen_cool": "Erzeugte Kälteenergie",
    "gen_power": "Erzeugte elektrische Energie",
    "cons_power": "Aufgenommene elektrische Energie",
    "cons_gas": "Verbrauchte Gasenergie",
    "ch": "Geladene Energie",
    "dch": "Entladene Energie",
}

def _dg_description(raw: str, sheet: str) -> str:
    """Liefert den deutschen Hilfetext zu einer DG-Kennzahl und ihrem Berichtszeitraum."""

    name = re.sub(r" \([^()]*\)$", "", raw)
    if name in DG_REPORT_HELP:
        return DG_REPORT_HELP[name]
    period = "über den gesamten Betrachtungszeitraum" if sheet == "Static KPIs" else "im angegebenen Stützjahr"
    if name.startswith("Annualized Fixed Costs "):
        scope = "zentralen" if "Central" in name else "dezentralen"
        subsidy = " ohne Förderung" if "Unsubsidized" in name else ""
        return f"Auf ein Jahr umgelegte Fixkosten der {scope} Anlagen{subsidy}."
    if name.startswith("Annualized Cost"):
        subsidy = " ohne Förderung" if "Unsubsidized" in name else " mit Förderung"
        return f"Auf ein Jahr umgelegter Kostenanteil der angegebenen Anlage{subsidy}."
    if name.startswith("Total CO2 Emissions "):
        carrier = name.removeprefix("Total CO2 Emissions ")
        source = DG_CARRIER_NAMES.get(carrier, carrier)
        return f"CO₂-Emissionen aus dem Einsatz von {source} über den gesamten Betrachtungszeitraum."
    if name.startswith("CO2 Emissions "):
        carrier = name.removeprefix("CO2 Emissions ")
        source = DG_CARRIER_NAMES.get(carrier, carrier)
        return f"CO₂-Emissionen aus dem Einsatz von {source} {period}."
    if name.endswith(" Consumption"):
        carrier = name.removesuffix(" Consumption")
        source = DG_CARRIER_NAMES.get(carrier, carrier)
        return f"Verbrauch von {source} {period}."
    if name.endswith(" Costs"):
        carrier = name.removesuffix(" Costs")
        source = DG_CARRIER_NAMES.get(carrier, carrier)
        return f"Jährliche Kosten für {source} im angegebenen Stützjahr."
    if name.endswith(" demand Peak") or name.endswith(" Demand Peak"):
        return "Höchste für diesen Bedarf ermittelte Leistung im Quartier."
    if " demand" in name or name.endswith(" demand"):
        return "Jährlicher Energiebedarf dieser Nutzung im Quartier."
    metric = name.removeprefix("Avg. ") if name.startswith("Avg. ") else re.sub(r"^Year \S+ ", "", name)
    if metric in DG_DEVICE_METRIC_HELP:
        suffix = "im Jahresmittel" if name.startswith("Avg. ") else "im angegebenen Stützjahr"
        return f"{DG_DEVICE_METRIC_HELP[metric]} der angegebenen Anlage {suffix}."
    if sheet in {"Central Devices", "Decentral Devices"}:
        return "Ergebniswert der angegebenen Anlage aus dem DG-Bericht."
    return "Kennzahl des Quartiers aus dem DG-Ergebnisbericht."


def _report_item(
    raw: str, value: Any, sheet: str, *, prefix: str = "",
    label_override: str | None = None, unit_override: str | None = None,
) -> dict[str, Any]:
    """Bereitet eine DG-Berichtszeile ohne Dash-Komponenten für die HEO-Karte auf."""

    label, unit, decimals, scale = _dg_label(raw)
    if unit_override:
        unit = unit_override
    return {
        "label": label_override if label_override is not None else f"{prefix}{label}",
        "parameter_key": f"report:{sheet}:{prefix}{raw}",
        "value": value * scale if numeric_value(value) is not None else value,
        "unit": unit,
        "decimals": decimals,
        "description": _dg_description(raw, sheet),
        "view": kpi_dialog_view(f"report:{sheet}:{raw}"),
    }


def report_items(report: dict[str, Any]) -> tuple[list[dict], list[tuple[str, bool, list[dict]]]]:
    """Ordnet DG-Berichtszeilen in Hauptkarten und weitere HEO-Abschnitte ein."""

    # Globale und jährliche Kennzahlen zuerst auf Hauptkarten und Zusatzabschnitte verteilen.
    main: list[dict] = []
    sections: list[tuple[str, bool, list[dict]]] = []
    for sheet, heading in (("Static KPIs", "Feste DG-Kennzahlen"), ("Yearly KPIs", "DG-Kennzahlen je Stützjahr")):
        cards: list[dict] = []
        for entry in report.get(sheet, []):
            raw_label = entry.get("KPI")
            if not raw_label:
                continue
            raw = str(raw_label)
            if sheet == "Static KPIs":
                value = entry.get("Value")
                if value is None:
                    continue
                item = _report_item(raw, value, sheet)
                (main if item["view"] == "main" else cards).append(item)
                continue
            values = [(str(year).replace("Year ", ""), value) for year, value in entry.items() if str(year).startswith("Year ")]
            if not values:
                continue
            if len(values) > 1 and all(value == values[0][1] for _, value in values):
                values = [(" / ".join(year for year, _ in values), values[0][1])]
            for year, value in values:
                year_label = f"Stützjahre {year}" if " / " in year else f"Jahr {year}"
                item = _report_item(
                    raw, value, sheet,
                    label_override=f"{_dg_label(raw)[0]} · {year_label}",
                )
                (main if item["view"] == "main" else cards).append(item)
        if cards:
            sections.append((heading, False, cards))
    # Gerätekennzahlen behalten ihren Gebäude-/Gerätebezug, damit gleiche KPI-Namen unterscheidbar sind.
    for sheet, heading in (("Decentral Devices", "Dezentrale Anlagen"), ("Central Devices", "Zentrale Anlagen")):
        cards = []
        for entry in report.get(sheet, []):
            prefix = " · ".join(str(entry[key]) for key in ("Building ID", "Device") if key in entry)
            for key, value in entry.items():
                if key in {"Building ID", "Device", "Unit"}:
                    continue
                item = _report_item(
                    str(key), value, sheet, prefix=f"{prefix} · ",
                    unit_override=str(entry["Unit"]) if key == "Capacity" and entry.get("Unit") else None,
                )
                (main if item["view"] == "main" else cards).append(item)
        if cards:
            sections.append((heading, True, cards))
    return main, sections


def summary_items(bundle: dict[str, Any] | None) -> tuple[list[dict], list[dict]]:
    """Bereitet Zusammenfassungskennzahlen inklusive Investitionsfallback für HEO auf."""

    summary = comparison_summary(bundle)
    main: list[dict] = []
    more: list[dict] = []
    for key, label, unit, decimals in (*KPI_PRESENTATION, *SUMMARY_DETAILS):
        if key == "investment_cost_eur" and numeric_value(summary.get(key)) is None:
            key = "investment_cost_central_devices_eur"
            label = "Investition zentrale Anlagen (ohne Netz)"
        view = kpi_dialog_view(key)
        if view == "more" and numeric_value(summary.get(key)) is None:
            continue
        item = {
            "label": label, "value": summary.get(key), "unit": unit,
            "parameter_key": f"kpi:{key}",
            "decimals": decimals, "description": KPI_HELP[key],
        }
        (main if view == "main" else more).append(item)
    return main, more

