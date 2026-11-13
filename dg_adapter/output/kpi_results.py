# Liest DG-KPI-Berichte und berechnet Kennzahlen der Optimierungsvarianten.

from __future__ import annotations

import csv
import json
import math
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..input.config_service import DG_ROOT, DG_SCENARIOS_DIR
from ..shared.dg_paths import seed_control_dir

MANIFEST_FILENAME = "manifest.json"
PREPARED_SCENARIO_FILENAME = "prepared_scenario.p"

# Normalisiert einen einzelnen DG-Berichtswert.
def _scalar(value: Any) -> str | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    return text or None


# Liest alle belegten KPI-Zeilen aus XLSX oder CSV.
def read_dg_kpi_report(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Return every populated KPI row; an absent report is an empty report."""

    if not path.is_file():
        report = {}
        for sheet, suffix in (("Static KPIs", "static"), ("Yearly KPIs", "yearly")):
            csv_path = path.with_name(f"{path.stem}_{suffix}.csv")
            if not csv_path.is_file():
                continue
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = []
                for row in csv.DictReader(handle, delimiter=";"):
                    entry = {}
                    for key, value in row.items():
                        if not key or not value:
                            continue
                        try:
                            entry[key] = float(value.replace(",", "."))
                        except ValueError:
                            entry[key] = value
                    if entry:
                        rows.append(entry)
                report[sheet] = rows
        return report
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    report: dict[str, list[dict[str, Any]]] = {}
    try:
        for sheet_name in ("Static KPIs", "Yearly KPIs", "Decentral Devices", "Central Devices"):
            if sheet_name not in workbook:
                continue
            rows = workbook[sheet_name].values
            headers = next(rows, None)
            if not headers:
                continue
            entries = []
            for row in rows:
                entry = {
                    str(header): scalar
                    for header, value in zip(headers, row)
                    if header is not None and (scalar := _scalar(value)) is not None
                }
                if entry:
                    entries.append(entry)
            report[sheet_name] = entries
    finally:
        workbook.close()
    return report


# Liest zentrale Anlageninvestitionen aus der EHDO-Lösung.
def central_device_investment_from_solution(path: Path) -> float | None:
    """Read central equipment CAPEX from EHDO; excludes heat grid and buildings."""

    if not path.is_file():
        return None
    total = 0.0
    found = False
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line.startswith("inv["):
                continue
            name, separator, value = line.partition("]")
            if not separator or not name[4:]:
                continue
            try:
                number = float(value.strip())
            except ValueError:
                continue
            if math.isfinite(number):
                total += number
                found = True
    return total if found else None


# Wandelt einen DG-Kennwert nach Möglichkeit in eine Zahl um.
def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Sammelt Zahlen aus den DG-Jahreswerten.
def _mapping_values(value: Any) -> list[float]:
    if not isinstance(value, dict):
        return []
    numbers = [_number(item) for item in value.values()]
    return [item for item in numbers if item is not None]


# Berechnet den Mittelwert vorhandener Jahreswerte.
def _mapping_average(value: Any) -> float | None:
    numbers = _mapping_values(value)
    return sum(numbers) / len(numbers) if numbers else None


# Berechnet den größten vorhandenen Jahreswert.
def _mapping_maximum(value: Any) -> float | None:
    numbers = _mapping_values(value)
    return max(numbers) if numbers else None


# Berechnet HEO-Kennzahlen aus einer DG-Optimierungsvariante.
def _variant_summary(data: Any) -> dict[str, float | None]:
    kpis = getattr(data, "KPIs", None)
    central_devices = getattr(data, "centralDevices", None) or {}
    central_capacities = central_devices.get("capacities", {})
    central_investment = _number(central_capacities.get("total_inv_cost"))
    if not central_devices:
        central_investment = 0.0
    decentral_investment = 0.0
    decentral_complete = getattr(kpis, "decentral_individual_devices_annualized_cost", None) is not None
    device_data = getattr(data, "decentral_device_data", None) or {}
    for devices in (getattr(kpis, "decentral_individual_devices_annualized_cost", None) or {}).values():
        has_hp = "HP" in devices
        for device, details in devices.items():
            capacity = _number(details.get("cap"))
            if capacity is None:
                decentral_complete = False
                continue
            if device == "T_reduction_measures":
                price = _number(device_data.get("HP", {}).get("measures_inv_fix"))
            elif device == "EH" and has_hp:
                continue  # DG includes this electric heater in the heat pump investment.
            else:
                price = _number(device_data.get(device, {}).get("inv_var"))
            if price is None:
                decentral_complete = False
            else:
                decentral_investment += capacity * price
    if not decentral_complete:
        decentral_investment = None
    fixed_decentral = _number(getattr(kpis, "annual_fixed_costs_decentral", None))
    fixed_central = _number(getattr(kpis, "annual_fixed_costs_central", None))
    operation = _number(getattr(kpis, "avg_operationCosts", None))
    fixed_values = (fixed_decentral, fixed_central)
    annualized_total = (
        sum(value for value in (*fixed_values, operation) if value is not None)
        if any(value is not None for value in (*fixed_values, operation))
        else None
    )
    demand_values = (
        _number(getattr(kpis, "total_heating_demand", None)),
        _number(getattr(kpis, "total_cooling_demand", None)),
        _number(getattr(kpis, "total_electricity_demand", None)),
        _number(getattr(kpis, "total_dhw_demand", None)),
        _number(getattr(kpis, "total_EV_demand", None)),
    )
    net_energy_demand = (
        sum(value for value in demand_values if value is not None) / 1_000_000
        if any(value is not None for value in demand_values)
        else None
    )
    return {
        "investment_cost_eur": (
            central_investment + decentral_investment
            if central_investment is not None and decentral_investment is not None
            else None
        ),
        "investment_cost_central_eur": central_investment,
        "investment_cost_decentral_eur": decentral_investment,
        "annualized_total_cost_eur_per_a": annualized_total,
        "annualized_fixed_cost_decentral_eur_per_a": fixed_decentral,
        "annualized_fixed_cost_central_eur_per_a": fixed_central,
        "average_operation_cost_eur_per_a": operation,
        "average_co2_emissions_t_per_a": _number(
            getattr(kpis, "avg_co2_emissions", None)
        ),
        "net_energy_demand_mwh_per_a": net_energy_demand,
        "standard_heat_load_kw": (
            value / 1_000
            if (value := _number(getattr(kpis, "totalheatload", None))) is not None
            else None
        ),
        "electric_peak_demand_kw": _mapping_maximum(
            getattr(kpis, "peakDemand", None)
        ),
        "maximum_grid_feed_in_kw": _mapping_maximum(
            getattr(kpis, "peakInjection", None)
        ),
        "average_energy_autonomy_percent": (
            value * 100
            if (value := _mapping_average(
                getattr(kpis, "energy_autonomy_year", None)
            )) is not None
            else None
        ),
        "average_supply_cover_percent": (
            value * 100
            if (value := _mapping_average(getattr(kpis, "scf_year", None)))
            is not None
            else None
        ),
        "average_demand_cover_percent": (
            value * 100
            if (value := _mapping_average(getattr(kpis, "dcf_year", None)))
            is not None
            else None
        ),
        "observation_time_years": _number(
            getattr(data, "ecoData", {}).get("observation_time")
        ),
    }


# Liest für ältere Ergebnisbundles die zugehörige DG-Vorbereitung.
def _load_prepared_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


# Liest Kostenannahmen für ältere Ergebnisbundles.
@lru_cache(maxsize=8)
def _legacy_investment_context(
    scenario_name: str, profile_hash: str, *,
    _scenarios_root: Path = DG_SCENARIOS_DIR,
    _dg_root: Path = DG_ROOT,
    _pickle_loader=None,
) -> tuple[float, dict[str, float], dict[str, float]] | None:
    """Read the matching local DG preparation once for older investment reports."""

    seed_dir = seed_control_dir(_scenarios_root / scenario_name)
    manifest_path = seed_dir / MANIFEST_FILENAME
    prepared_path = seed_dir / PREPARED_SCENARIO_FILENAME
    if not manifest_path.is_file() or not prepared_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("profile_hash") != profile_hash:
            return None
        import sys

        if str(_dg_root) not in sys.path:
            sys.path.insert(0, str(_dg_root))
        prepared = (_pickle_loader or _load_prepared_pickle)(prepared_path)
        data = prepared.data
        heat_grid_cost = _number(getattr(data, "heat_grid_data", {}).get("costs")) or 0.0
        prices = {
            device: price
            for device, parameters in getattr(data, "decentral_device_data", {}).items()
            if (price := _number(parameters.get("inv_var"))) is not None
        }
        hp_measure_price = _number(data.decentral_device_data.get("HP", {}).get("measures_inv_fix"))
        if hp_measure_price is not None:
            prices["T_reduction_measures"] = hp_measure_price
        measures = {
            str(building.get("unique_name")): float(building["envelope"].heatload) / 1000
            for building in data.district
            if getattr(building.get("envelope"), "hp_measures", False)
        }
        return heat_grid_cost, prices, measures
    except (OSError, ValueError, AttributeError, KeyError, TypeError, ImportError, pickle.UnpicklingError):
        return None


# Ergänzt fehlende Gesamtinvestitionen aus älteren DG-Berichten.
def _legacy_total_investment(
    scenario_name: str,
    profile_hash: str,
    report: dict[str, Any],
    central_equipment_investment: float,
    *,
    _context_loader=None,
) -> float | None:
    context = (_context_loader or _legacy_investment_context)(scenario_name, profile_hash)
    if context is None or "Decentral Devices" not in report:
        return None
    heat_grid_cost, prices, measures = context
    decentral = 0.0
    devices_by_building: dict[str, set[str]] = {}
    for item in report["Decentral Devices"]:
        building = str(item.get("Building ID", ""))
        device = str(item.get("Device", ""))
        devices_by_building.setdefault(building, set()).add(device)
    for item in report["Decentral Devices"]:
        building = str(item.get("Building ID", ""))
        device = str(item.get("Device", ""))
        if device == "EH" and "HP" in devices_by_building[building]:
            continue
        capacity = _number(item.get("Capacity"))
        price = prices.get(device)
        if capacity is None or price is None:
            return None
        decentral += capacity * price
    for building, devices in devices_by_building.items():
        if "HP" in devices and building in measures:
            price = prices.get("T_reduction_measures")
            if price is None:
                return None
            decentral += measures[building] * price
    return central_equipment_investment + heat_grid_cost + decentral
