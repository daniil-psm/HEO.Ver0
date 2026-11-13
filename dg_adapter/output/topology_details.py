# Liest DG-Komponentenwerte für die HEO-Ergebnistopologie.
# Knotenwerte und Ergebniszeilen bleiben unabhängig von Dash und Tabs.

from __future__ import annotations

from typing import Any, Callable

from heo.model.devices import HEATER_SYSTEM_PARTS, building_heater_parts, decentral_device_components
from heo.display.device_labels import decentral_device_name
from heo.topology.model import (
    Topology,
    TopologyEdge,
    TopologyNode,
)
from heo.topology.labels import node_label_variants
from dg_adapter.output.result_series import storage_annual_mwh


# Begrenzt Prozent- und Förderwerte auf den erlaubten Bereich.
def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


HEAT_GENERATOR_CODES = frozenset({
    "STC", "HP", "GROUNDHP", "EB", "CHP", "BOI", "GHP",
    "BCHP", "BBOI", "WCHP", "WBOI", "FC",
})
COOLING_GENERATOR_CODES = frozenset({"CC", "AC"})
COGENERATION_CODES = frozenset({"CHP", "BCHP", "WCHP", "FC"})
STORAGE_CODES = frozenset({"BAT", "TES", "CTES", "H2S", "GS"})


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "ja", "on"}


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def format_result_number(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _dg_device_code(code: str) -> str:
    return "GroundHP" if code == "GROUNDHP" else code


def _sort_key(value: object) -> tuple[int, int | str]:
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)


def _optimization_clusters(
    optimization_data: dict | None,
) -> list[tuple[dict, int]]:
    """Liefert die gewichteten Cluster des ersten Ergebnisjahres."""

    data = optimization_data or {}
    years = data.get("results") or {}
    if not isinstance(years, dict) or not years:
        return []
    first_year = years.get(sorted(years, key=_sort_key)[0])
    if not isinstance(first_year, dict):
        return []
    cluster_ids = [str(item) for item in data.get("clusters") or []]
    weights = data.get("cluster_weights") or {}
    result: list[tuple[dict, int]] = []
    for index, result_key in enumerate(sorted(first_year, key=_sort_key)):
        cluster = first_year.get(result_key)
        if not isinstance(cluster, dict):
            continue
        representative = (
            cluster_ids[index] if index < len(cluster_ids) else str(result_key)
        )
        if isinstance(weights, dict):
            weight = int(_number(
                weights.get(representative, weights.get(str(result_key), 1)), 1
            ))
        elif isinstance(weights, list) and index < len(weights):
            weight = int(_number(weights[index], 1))
        else:
            weight = 1
        result.append((cluster, max(1, weight)))
    return result


def _weighted_profile(
    optimization_data: dict | None,
    extractor: Callable[[dict], object],
    *,
    divisor: float = 1000.0,
) -> list[float]:
    values: list[float] = []
    for cluster, weight in _optimization_clusters(optimization_data):
        raw = extractor(cluster)
        if not isinstance(raw, list):
            continue
        profile = [_number(item) / divisor for item in raw]
        for _ in range(weight):
            values.extend(profile)
    return values


def _device_profile(
    optimization_data: dict | None,
    code: str,
) -> list[float]:
    preferred = {
        "PV": "ts_gen_power", "WT": "ts_gen_power", "WAT": "ts_gen_power",
        **{code: "ts_gen_heat" for code in HEAT_GENERATOR_CODES},
        **{code: "ts_gen_cool" for code in COOLING_GENERATOR_CODES},
        **{code: "ts_dch" for code in STORAGE_CODES},
    }.get(code, "ts_gen_power")
    return _weighted_profile(
        optimization_data,
        lambda cluster: (
            ((cluster.get("energy_hub") or {}).get(_dg_device_code(code)) or {}).get(
                preferred, []
            )
        ),
    )


def _device_annual_mwh(
    optimization_data: dict | None,
    code: str,
) -> float:
    scalar_key = {
        "PV": "gen_power", "WT": "gen_power", "WAT": "gen_power",
        **{code: "gen_heat" for code in HEAT_GENERATOR_CODES},
        **{code: "gen_cool" for code in COOLING_GENERATOR_CODES},
        **{code: "dch" for code in STORAGE_CODES},
    }.get(code, "gen_power")
    total_kwh = 0.0
    for cluster, weight in _optimization_clusters(optimization_data):
        device = ((cluster.get("energy_hub") or {}).get(_dg_device_code(code)) or {})
        total_kwh += _number(device.get(scalar_key)) * weight
    return total_kwh / 1000.0


def _building_result_context(
    node: TopologyNode, optimization_data: dict | None,
) -> tuple[int, dict] | None:
    """Ordnet eine Gebäude- oder Badge-Node ihrem DG-Ergebnisindex zu."""

    parts = node.id.split(":")
    if len(parts) < 2 or parts[0] != "BUILDING":
        return None
    try:
        uid = int(parts[1])
    except ValueError:
        return None
    data = optimization_data or {}
    snapshot = data.get("topology_snapshot") or {}
    rows = snapshot.get("buildings") if isinstance(snapshot, dict) else None
    if not isinstance(rows, list):
        buildings = (data.get("project_snapshot") or {}).get("buildings") or {}
        rows = buildings.get("rows") if isinstance(buildings, dict) else None
    if not isinstance(rows, list):
        return None
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        if int(_number(row.get("uid"), index)) == uid:
            return int(_number(row.get("result_index"), index)), row
    return None


def _building_device_profile(
    optimization_data: dict | None, result_index: int,
    code: str, series_key: str,
) -> list[float]:
    return _weighted_profile(
        optimization_data,
        lambda cluster: (
            ((cluster.get(str(result_index)) or {}).get(code) or {}).get(series_key, [])
        ),
    )


def _building_device_annual_mwh(
    optimization_data: dict | None, result_index: int,
    code: str, scalar_key: str,
) -> float | None:
    total_kwh = 0.0
    found = False
    for cluster, weight in _optimization_clusters(optimization_data):
        device = (cluster.get(str(result_index)) or {}).get(code) or {}
        if scalar_key in device:
            total_kwh += _number(device[scalar_key]) * weight
            found = True
    return total_kwh / 1000.0 if found else None


def _building_ev_profile(
    optimization_data: dict | None, result_index: int, series_key: str,
) -> list[float]:
    def extract(cluster: dict) -> list[float]:
        ev = (cluster.get(str(result_index)) or {}).get("EV") or {}
        cars = [value for key, value in ev.items() if key.startswith("Car_") and isinstance(value, dict)]
        if not cars:
            return ev.get(series_key, [])
        profiles = []
        for car in cars:
            value = car.get(series_key)
            profiles.append(value if isinstance(value, list) else [])
        return [sum(_number(profile[index]) for profile in profiles if index < len(profile))
                for index in range(max((len(profile) for profile in profiles), default=0))]

    return _weighted_profile(optimization_data, extract)


def _building_ev_annual_mwh(
    optimization_data: dict | None, result_index: int, scalar_key: str,
) -> float | None:
    total_kwh = 0.0
    found = False
    for cluster, weight in _optimization_clusters(optimization_data):
        ev = (cluster.get(str(result_index)) or {}).get("EV") or {}
        cars = [value for key, value in ev.items() if key.startswith("Car_") and isinstance(value, dict)]
        devices = cars or [ev]
        for device in devices:
            if scalar_key in device:
                total_kwh += _number(device[scalar_key]) * weight
                found = True
    return total_kwh / 1000.0 if found else None


def _building_heater_profile(
    optimization_data: dict | None, result_index: int, code: str,
) -> list[float]:
    parts = building_heater_parts(code)

    def extract(cluster: dict) -> list[float]:
        building = cluster.get(str(result_index)) or {}
        profiles = []
        for part in parts:
            series = (building.get(part) or {}).get("ts_gen_heat")
            profiles.append(series if isinstance(series, list) else [])
        return [sum(_number(profile[index]) for profile in profiles if index < len(profile))
                for index in range(max((len(profile) for profile in profiles), default=0))]

    return _weighted_profile(optimization_data, extract)


def _building_heater_annual_mwh(
    optimization_data: dict | None, result_index: int, code: str,
) -> float | None:
    total_kwh = 0.0
    found = False
    for cluster, weight in _optimization_clusters(optimization_data):
        building = cluster.get(str(result_index)) or {}
        for part in building_heater_parts(code):
            device = building.get(part) or {}
            if "gen_heat" in device:
                total_kwh += _number(device["gen_heat"]) * weight
                found = True
    return total_kwh / 1000.0 if found else None


def _building_device_report_entries(
    row: dict, optimization_data: dict | None, codes: set[str],
) -> list[dict]:
    """Findet DG-Gerätewerte über die zum Lauf gehörende Gebäude-ID."""

    data = optimization_data or {}
    building_id = _configured_number(row, "id")
    building_type = str(row.get("building") or "").strip()
    scenario_name = str(data.get("scenario_name") or "").strip()
    if building_id is None or not building_id.is_integer() or not building_type or not scenario_name:
        return []
    report_id = f"{scenario_name}_{int(building_id)}_{building_type}"
    entries = ((data.get("kpi_report") or {}).get("Decentral Devices") or [])
    return [
        entry for entry in entries
        if isinstance(entry, dict)
        and str(entry.get("Building ID") or "") == report_id
        and str(entry.get("Device") or "") in codes
    ]


def _building_dle_report(
    row: dict, optimization_data: dict | None,
) -> dict | None:
    """Findet den DLE-Eintrag über die vom DG verwendete Gebäude-ID."""

    return next(iter(_building_device_report_entries(
        row, optimization_data, {"EH_DHW", "DL"}
    )), None)


def _building_device_result_lines(
    row: dict, optimization_data: dict | None, code: str,
) -> list[str]:
    """Optimierte Kapazität und Investition dezentraler Geräte aus dem DG-Lauf."""

    parts = set(decentral_device_components(code))
    if code in HEATER_SYSTEM_PARTS:
        parts.update(building_heater_parts(code))
    entries = _building_device_report_entries(row, optimization_data, parts)
    if not entries:
        return []
    values = _result_config_values(None, optimization_data)
    has_hp = any(str(entry.get("Device")) == "HP" for entry in entries)
    qualified = len(entries) > 1
    lines: list[str] = []
    for entry in entries:
        device_code = str(entry.get("Device") or "")
        capacity = _configured_number(entry, "Capacity")
        if capacity is None:
            continue
        unit = str(entry.get("Unit") or "").strip()
        label = (
            "Nutzbare Speicherkapazität" if unit == "kWh"
            else "Speichervolumen" if unit in {"Liter", "l", "m³"}
            else "Installierte Modulfläche" if unit == "m²"
            else "Nennleistung" if unit in {"kW", "kWp"}
            else "Kapazität"
        )
        suffix = f" {decentral_device_name(device_code)}" if qualified else ""
        lines.append(f"{label}{suffix}: {format_result_number(capacity, 3)} {unit}".rstrip())

        # Der DG rechnet den elektrischen Zusatzheizer einer HP in deren
        # Investition ein. Ihn nochmals anzusetzen würde doppelt zählen.
        if not (device_code == "EH" and has_hp):
            device_values = values.get(f"D_{device_code}") or {}
            price = (
                _configured_number(device_values, "inv_var")
                if isinstance(device_values, dict) else None
            )
            if price is None:
                price = _configured_number(values, f"D_{device_code}__INV_BASE")
            if price is not None:
                lines.append(
                    f"Investition{suffix}: {format_result_number(capacity * price, 2)} €"
                )
        annualized = _configured_number(entry, "Annualized Cost (€/a)")
        if annualized is not None:
            lines.append(
                f"Annualisierte Kosten{suffix}: {format_result_number(annualized, 2)} €/a"
            )
    return lines


def _building_dle_lines(
    row: dict, optimization_data: dict | None,
) -> list[str]:
    entry = _building_dle_report(row, optimization_data)
    if entry is None:
        return []
    lines = []
    capacity = _configured_number(entry, "Capacity")
    if capacity is not None and str(entry.get("Unit") or "kW") == "kW":
        lines.append(f"Elektrische Anschlussleistung: {format_result_number(capacity, 3)} kW")
        values = _result_config_values(None, optimization_data)
        device = values.get("D_EH_DHW") or {}
        price = _configured_number(device, "inv_var") if isinstance(device, dict) else None
        if price is None:
            price = _configured_number(values, "D_EH_DHW__INV_BASE")
        if price is not None:
            lines.append(f"Investition: {format_result_number(capacity * price, 2)} €")
    annualized = _configured_number(entry, "Annualized Cost (€/a)")
    if annualized is not None:
        lines.append(f"Annualisierte Kosten: {format_result_number(annualized, 2)} €/a")
    return lines


def _building_component_details(
    node: TopologyNode, optimization_data: dict | None,
) -> tuple[list[str], list[float]]:
    context = _building_result_context(node, optimization_data)
    if context is None:
        return ["Keine gebäudespezifischen Ergebnisdaten verfügbar"], []
    result_index, row = context
    if node.shape == "building":
        lines: list[str] = []
        area = _configured_number(row, "area")
        if area is not None:
            lines.append(f"Gebäudefläche: {format_result_number(area, 1)} m²")
        load = _weighted_profile(
            optimization_data,
            lambda cluster: (cluster.get(str(result_index)) or {}).get("res_load", []),
        )
        feed_in = _weighted_profile(
            optimization_data,
            lambda cluster: (cluster.get(str(result_index)) or {}).get("res_inj", []),
        )
        hours = _number(((optimization_data or {}).get("time") or {}).get("timeResolution"), 3600) / 3600
        if load:
            lines.extend([
                f"Max. Strombezug: {format_result_number(max(load), 1)} kW",
                f"Jährlicher Strombezug: {format_result_number(sum(load) * hours / 1000, 1)} MWh",
            ])
        if feed_in and max(feed_in) > 0:
            lines.extend([
                f"Max. Stromeinspeisung: {format_result_number(max(feed_in), 1)} kW",
                f"Jährliche Stromeinspeisung: {format_result_number(sum(feed_in) * hours / 1000, 1)} MWh",
            ])
        thermal_imports = (
            ((optimization_data or {}).get("building_thermal_imports") or {})
            .get(str(result_index)) or {}
        )
        for carrier, name in (("heat", "Wärme"), ("cool", "Kälte")):
            values = thermal_imports.get(carrier) or {}
            peak = _configured_number(values, "peak_kw")
            annual = _configured_number(values, "annual_mwh")
            if peak is not None and peak > 0:
                lines.append(f"Max. {name}bezug: {format_result_number(peak, 1)} kW")
            if annual is not None and annual > 0:
                lines.append(f"Jährlicher {name}bezug: {format_result_number(annual, 1)} MWh")
        return lines or ["Keine gebäudespezifischen Ergebnisdaten verfügbar"], load

    code = "EH_DHW" if node.device_code == "DL" else node.device_code or ""
    if code == "EV":
        charge = _building_ev_profile(optimization_data, result_index, "ts_ch")
        discharge = _building_ev_profile(optimization_data, result_index, "ts_dch")
        charged_mwh = _building_ev_annual_mwh(optimization_data, result_index, "ch")
        discharged_mwh = _building_ev_annual_mwh(optimization_data, result_index, "dch")
        lines = _building_device_result_lines(row, optimization_data, code)
        if charge:
            lines.append(f"Max. Ladeleistung im Betrieb: {format_result_number(max(charge), 1)} kW")
        if charged_mwh is not None:
            lines.append(f"Jährliche Ladeenergie: {format_result_number(charged_mwh, 1)} MWh")
        if discharge:
            lines.append(f"Max. Entladeleistung im Betrieb: {format_result_number(max(discharge), 1)} kW")
        if discharged_mwh is not None:
            lines.append(f"Jährliche Entladeenergie: {format_result_number(discharged_mwh, 1)} MWh")
        return lines or ["Keine komponentenspezifischen Ergebnisdaten verfügbar"], charge or discharge

    output = (
        ("ts_gen_heat", "gen_heat", "Wärmeleistung", "Wärmeerzeugung") if code in
        HEATER_SYSTEM_PARTS or code in {"STC", "EH_DHW"}
        else ("ts_gen_cool", "gen_cool", "Kälteleistung", "Kälteerzeugung") if code == "CC"
        else ("ts_gen_power", "gen_power", "elektrische Leistung", "Stromerzeugung") if code == "PV"
        else ("ts_dch", "dch", "Entladeleistung", "Entladeenergie") if code in {"BAT", "TES", "TES_DHW"}
        else None
    )
    if output is None:
        return ["Keine komponentenspezifischen Ergebnisdaten verfügbar"], []
    series_key, scalar_key, peak_label, annual_label = output
    if code in HEATER_SYSTEM_PARTS:
        profile = _building_heater_profile(optimization_data, result_index, code)
        annual_mwh = _building_heater_annual_mwh(optimization_data, result_index, code)
    else:
        profile = _building_device_profile(optimization_data, result_index, code, series_key)
        annual_mwh = _building_device_annual_mwh(
            optimization_data, result_index, code, scalar_key
        )
    lines = (
        _building_dle_lines(row, optimization_data)
        if code == "EH_DHW"
        else _building_device_result_lines(row, optimization_data, code)
    )
    if profile:
        lines.append(f"Max. {peak_label} im Betrieb: {format_result_number(max(profile), 1)} kW")
    if annual_mwh is not None:
        lines.append(f"Jährliche {annual_label}: {format_result_number(annual_mwh, 1)} MWh")
    if code in {"PV", "STC"}:
        for key, label in (("beta_PV", "Neigung"), ("gamma_PV", "Ausrichtung (Azimut)")):
            angle = _configured_number(row, key)
            if angle is not None:
                lines.append(f"{label}: {format_result_number(angle, 1)} °")
    if code in {"BAT", "TES", "TES_DHW"}:
        charge = _building_device_profile(optimization_data, result_index, code, "ts_ch")
        if charge:
            lines.append(f"Max. Ladeleistung im Betrieb: {format_result_number(max(charge), 1)} kW")
    return lines or ["Keine komponentenspezifischen Ergebnisdaten verfügbar"], profile


def central_storage_annual_mwh(
    optimization_data: dict | None,
    code: str,
) -> tuple[float, float, float] | None:
    if code not in STORAGE_CODES:
        return None
    return storage_annual_mwh(optimization_data, code)


def central_storage_annual_lines(values: tuple[float, float, float]) -> list[str]:
    charged, discharged, loss = values
    return [
        f"Eingespeicherte Energie: {format_result_number(charged, 3)} MWh/a",
        f"Ausgespeicherte Energie: {format_result_number(discharged, 3)} MWh/a",
        f"Verlustenergie: {format_result_number(loss, 3)} MWh/a",
    ]


def _thermal_bus_profile(
    optimization_data: dict | None,
    *,
    cooling: bool,
) -> list[float]:
    production_codes = (
        ("CC", "AC")
        if cooling else ("HP", "EB", "STC", "BOI", "BBOI", "GHP")
    )
    production_key = "ts_gen_cool" if cooling else "ts_gen_heat"
    storage_code = "CTES" if cooling else "TES"

    def extract(cluster: dict) -> list[float]:
        hub = cluster.get("energy_hub") or {}
        profiles: list[list[Any]] = []
        for code in production_codes:
            series = (hub.get(code) or {}).get(production_key)
            if isinstance(series, list):
                profiles.append(series)
        storage = hub.get(storage_code) or {}
        discharge = storage.get("ts_dch") if isinstance(storage.get("ts_dch"), list) else []
        charge = storage.get("ts_ch") if isinstance(storage.get("ts_ch"), list) else []
        length = max(
            [len(series) for series in profiles]
            + [len(discharge), len(charge), 0]
        )
        return [
            max(
                0.0,
                sum(
                    _number(series[index])
                    for series in profiles if index < len(series)
                )
                + (_number(discharge[index]) if index < len(discharge) else 0.0)
                - (_number(charge[index]) if index < len(charge) else 0.0),
            )
            for index in range(length)
        ]

    return _weighted_profile(optimization_data, extract)


def _system_load_series(
    optimization_data: dict | None,
) -> dict[str, list[float]]:
    return {
        "electric": _weighted_profile(
            optimization_data,
            lambda cluster: cluster.get("P_dem_total", []),
        ),
        "heat": _thermal_bus_profile(optimization_data, cooling=False),
        "cooling": _thermal_bus_profile(optimization_data, cooling=True),
    }


def _result_config_values(
    config_state: dict | None, optimization_data: dict | None,
) -> dict:
    """Verwendet die beim Lauf eingefrorenen Parameter vor dem aktuellen Entwurf."""

    snapshot = ((optimization_data or {}).get("project_snapshot") or {}).get("config") or {}
    snapshot_values = snapshot.get("values") if isinstance(snapshot, dict) else None
    if isinstance(snapshot_values, dict) and snapshot_values:
        return snapshot_values
    return (config_state or {}).get("values") or {}


def _configured_number(values: dict, key: str) -> float | None:
    raw = values.get(key)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _thermal_storage_volume_m3(
    code: str, capacity_kwh: float, values: dict,
) -> float | None:
    if code not in {"TES", "CTES"}:
        return None
    delta_t = _configured_number(values, f"C_{code}__DELTA_T")
    density = _configured_number(values, "RHO_WATER")
    heat_capacity = _configured_number(values, "C_P_WATER")
    if not delta_t or not density or not heat_capacity:
        return None
    # DG: c_p in kJ/(kg·K), rho in kg/m³, cap in kWh.
    return capacity_kwh * 3600.0 / (density * heat_capacity * delta_t)


def _component_investment(code: str, values: dict, capacity: float) -> float:
    base = _number(values.get(f"C_{code}__INV_BASE"))
    subsidy = clamp(
        _number(values.get(f"C_{code}__INV_SUBSIDY_RATE")), 0.0, 1.0
    )
    # Bei TES/CTES steht INV_BASE in €/m³, die optimierte Kapazität in kWh.
    volume = _thermal_storage_volume_m3(code, capacity, values)
    return (volume if volume is not None else capacity) * base * (1.0 - subsidy)


def _device_series_peak(
    optimization_data: dict | None, code: str, series_key: str,
) -> float | None:
    """Maximaler modellierter Leistungswert des ersten Ergebnisjahres in kW."""

    peaks = []
    for cluster, _ in _optimization_clusters(optimization_data):
        series = ((cluster.get("energy_hub") or {}).get(_dg_device_code(code)) or {}).get(series_key)
        if isinstance(series, list) and series:
            peaks.append(max(_number(value) for value in series))
    return max(peaks) / 1000.0 if peaks else None


def _cop_at_peak(
    optimization_data: dict | None, code: str, output_key: str,
) -> float | None:
    """Betriebs-COP am Zeitschritt mit der höchsten Wärme-/Kälteabgabe."""

    peak_output = -1.0
    peak_input = 0.0
    for cluster, _ in _optimization_clusters(optimization_data):
        device = (cluster.get("energy_hub") or {}).get(_dg_device_code(code)) or {}
        outputs = device.get(output_key)
        inputs = device.get("ts_cons_power")
        if not isinstance(outputs, list) or not isinstance(inputs, list):
            continue
        for output, input_power in zip(outputs, inputs):
            output_value = _number(output)
            input_value = _number(input_power)
            if output_value > peak_output and input_value > 0:
                peak_output, peak_input = output_value, input_value
    return peak_output / peak_input if peak_input > 0 else None


def _network_temperature_lines(code: str, values: dict) -> list[str]:
    lines: list[str] = []
    if code in HEAT_GENERATOR_CODES | {"TES"}:
        generation = str(values.get("GENERATION") or "")
        mode = str(values.get("TEMPERATURE_MODE") or "")
        if generation:
            for key, label in (
                ("T_HOT_HEATING_NETWORK", "Wärmenetz-Vorlauf"),
                ("T_COLD_HEATING_NETWORK", "Wärmenetz-Rücklauf"),
            ):
                mapping = values.get(key)
                if not isinstance(mapping, dict):
                    continue
                if mode == "constant":
                    temperature = _configured_number(mapping.get("constant") or {}, generation)
                    if temperature is not None:
                        lines.append(f"{label}: {format_result_number(temperature, 1)} °C")
                elif mode == "heating_curve":
                    curve = mapping.get("heating_curve") or {}
                    temperatures = [
                        _configured_number(curve.get(bound) or {}, generation)
                        for bound in ("min", "max")
                    ]
                    if all(value is not None for value in temperatures):
                        low, high = sorted(temperatures)
                        lines.append(
                            f"{label} (Heizkurve): "
                            f"{format_result_number(low, 1)}–{format_result_number(high, 1)} °C"
                        )
    if code in COOLING_GENERATOR_CODES | {"CTES"}:
        for key, label in (
            ("T_COLD_COOLING_NETWORK", "Kältenetz-Vorlauf"),
            ("T_HOT_COOLING_NETWORK", "Kältenetz-Rücklauf"),
        ):
            temperature = _configured_number(values, key)
            if temperature is not None:
                lines.append(f"{label}: {format_result_number(temperature, 1)} °C")
    return lines


def _network_design_lines(
    optimization_data: dict | None, network_code: str,
) -> list[str]:
    """Zeigt DG-Trassen, Nennweiten und Investition am passenden Netzknoten."""

    design = (optimization_data or {}).get("network_design") or {}
    network = design.get(network_code) if isinstance(design, dict) else None
    if not isinstance(network, dict):
        return []
    lines: list[str] = []
    for key, label in (
        ("distribution_length_m", "Länge Verteilnetz"),
        ("service_length_m", "Länge Hausanschlüsse"),
    ):
        value = _configured_number(network, key)
        if value is not None:
            lines.append(f"{label}: {format_result_number(value, 1)} m")
    for key, label in (
        ("distribution_dn", "Nennweite Verteilnetz"),
        ("service_dn", "Nennweite Hausanschlüsse"),
    ):
        value = _configured_number(network, key)
        if value is not None:
            lines.append(f"{label}: DN {format_result_number(value)}")
    investment = _configured_number(network, "investment_eur")
    if investment is not None:
        name = "Wärmenetz" if network_code == "heating" else "Kältenetz"
        lines.append(f"Investition {name}: {format_result_number(investment)} €")
    substations = _configured_number(design, "substations_investment_eur")
    if substations is not None:
        lines.append(
            "Investition Übergabestationen (gemeinsam): "
            f"{format_result_number(substations)} €"
        )
    return lines


def _design_parameter_lines(
    code: str, result: dict, values: dict, optimization_data: dict | None,
) -> list[str]:
    """Auslegungswerte und klar bezeichnete Betriebsmaxima einer Anlage."""

    lines: list[str] = []
    capacity = _number(result.get("value"))
    prefix = f"C_{code}__"

    def add_number(key: str, label: str, unit: str, decimals: int = 1) -> float | None:
        number = _configured_number(values, prefix + key)
        if number is not None:
            lines.append(f"{label}: {format_result_number(number, decimals)} {unit}".rstrip())
        return number

    def add_efficiency(key: str, label: str) -> float | None:
        efficiency = _configured_number(values, prefix + key)
        if efficiency is not None:
            lines.append(f"{label}: {format_result_number(efficiency * 100, 1)} %")
        return efficiency

    if code in {"PV", "STC"}:
        area = _configured_number(result, "area_m2")
        if area is not None:
            label = "Installierte Modulfläche" if code == "PV" else "Kollektorfläche"
            lines.append(f"{label}: {format_result_number(area, 1)} m²")
        add_number("BETA", "Neigung", "°")
        add_number("GAMMA", "Ausrichtung (Azimut)", "°")
        add_efficiency("ETA", "Modulwirkungsgrad" if code == "PV" else "Kollektorwirkungsgrad")

    if code in {"WAT", "ELYZ", "SAB"}:
        add_efficiency("ETA", "Wirkungsgrad")

    if code in COGENERATION_CODES:
        eta_el = add_efficiency("ETA_EL", "Elektrischer Wirkungsgrad")
        eta_th = add_efficiency("ETA_TH", "Thermischer Wirkungsgrad")
        if eta_el and eta_th:
            lines.insert(0, f"Thermische Nennleistung: {format_result_number(capacity * eta_th / eta_el, 1)} kW")
    elif code in {"BOI", "BBOI", "WBOI", "EB", "AC"}:
        eta_th = add_efficiency("ETA_TH", "Thermischer Wirkungsgrad")
        if eta_th and code == "EB":
            lines.insert(0, f"Elektrische Anschlussleistung: {format_result_number(capacity / eta_th, 1)} kW")
        elif eta_th and code == "AC":
            lines.insert(0, f"Thermische Antriebsleistung: {format_result_number(capacity / eta_th, 1)} kW")

    if code in {"HP", "GROUNDHP", "CC", "GHP"}:
        cop_key = "COP_CONST" if code == "HP" else "COP"
        constant = code in {"CC", "HP"} and _truthy(values.get(prefix + "CCOP_FEASIBLE"))
        cop = _configured_number(values, prefix + cop_key)
        if cop and (constant or code == "GHP"):
            lines.append(f"Auslegungs-COP: {format_result_number(cop, 2)}")
            input_label = "Gas-Anschlussleistung" if code == "GHP" else "Elektrische Anschlussleistung"
            lines.append(f"{input_label} (bei Auslegungs-COP): {format_result_number(capacity / cop, 1)} kW")
        elif code in {"HP", "GROUNDHP", "CC"}:
            output_key = "ts_gen_cool" if code == "CC" else "ts_gen_heat"
            operating_cop = _cop_at_peak(optimization_data, code, output_key)
            if operating_cop is not None:
                lines.append(f"COP bei Betriebsspitze: {format_result_number(operating_cop, 2)}")
        if code == "HP" and not constant and (
            _truthy(values.get(prefix + "ASHP_MODEL_FEASIBLE"))
            or _truthy(values.get(prefix + "ASHP_CARNOT_FEASIBLE"))
        ):
            add_number("ASHP_SUPPLY_TEMP", "Wärmepumpen-Vorlauf", "°C")
        if code in {"HP", "GROUNDHP", "CC"}:
            peak = _device_series_peak(optimization_data, code, "ts_cons_power")
            if peak is not None:
                lines.append(f"Max. elektrische Aufnahme im Betrieb: {format_result_number(peak, 1)} kW")

    if code in STORAGE_CODES:
        if code in {"TES", "CTES"}:
            volume = _thermal_storage_volume_m3(code, capacity, values)
            if volume is not None:
                lines.append(f"Speichervolumen: {format_result_number(volume, 1)} m³")
            add_number("DELTA_T", "Nutzbare Temperaturspreizung", "K")
        for series_key, label in (
            ("ts_ch", "Max. Ladeleistung im Betrieb"),
            ("ts_dch", "Max. Entladeleistung im Betrieb"),
        ):
            peak = _device_series_peak(optimization_data, code, series_key)
            if peak is not None:
                lines.append(f"{label}: {format_result_number(peak, 1)} kW")
        add_efficiency("STO_LOSS", "Speicherverlust pro Stunde")
        add_efficiency("SOC_INIT", "Anfangsladezustand")

    lines.extend(_network_temperature_lines(code, values))
    return lines


def system_node_value(
    node: TopologyNode,
    config_state: dict | None,
    optimization_data: dict | None,
) -> str:
    """Fachlicher Dimensionswert für eine Ergebnis-Node."""

    values = _result_config_values(config_state, optimization_data)
    capacities = (
        (optimization_data or {}).get("capacities", {}).get("devices", {})
    )
    code = node.device_code
    if code:
        result = capacities.get(_dg_device_code(code)) or {}
        if "value" not in result:
            return "ausgewählt"
        value = _number(result.get("value"))
        unit = (
            "kWp" if code == "PV"
            else "kWh" if code in {"TES", "CTES"}
            else str(result.get("unit") or "kW")
        )
        dimension = f"{value:.1f}".replace(".", ",") + f" {unit}"
        return dimension
    node_id = node.id.lower()
    if node_id == "grid":
        if _truthy(values.get("ENABLE_TRAFOMAX_W")):
            return f"{_number(values.get('TRAFOMAX_W')) / 1000:.0f} kW"
        return "Netzanschluss"
    if node_id == "load":
        peaks = _system_load_series(optimization_data)
        if any(peaks.values()):
            return (
                f"Strom {format_result_number(max(peaks['electric'], default=0.0), 1)} kW\n"
                f"Wärme {format_result_number(max(peaks['heat'], default=0.0), 1)} kW\n"
                f"Kälte {format_result_number(max(peaks['cooling'], default=0.0), 1)} kW"
            )
        return "Strom\nWärme · Kälte"
    if node_id in {"converter", "inverter"}:
        return "AC ↔ DC"
    return "Verteilung"


def system_component_details(
    node: TopologyNode,
    config_state: dict | None,
    optimization_data: dict | None,
) -> tuple[list[str], list[float]]:
    """Nur dem gewählten Element zuordenbare Werte und dessen Jahresprofil."""

    capacities = (
        (optimization_data or {}).get("capacities", {}).get("devices", {})
    )
    code = node.device_code
    if node.shape in {"badge", "building"}:
        return _building_component_details(node, optimization_data)
    if code:
        result = capacities.get(_dg_device_code(code)) or {}
        capacity = _number(result.get("value"))
        values = _result_config_values(config_state, optimization_data)
        capacity_unit = str(result.get("unit") or "")
        is_storage = (
            code in STORAGE_CODES
            or capacity_unit.lower() in {"kwh", "mwh", "m³", "m3"}
        )
        dimension_label = (
            "Nutzbare Speicherkapazität" if is_storage
            else "Elektrische Nennleistung" if code in COGENERATION_CODES
            else "Nennleistung"
        )
        investment = _component_investment(code, values, capacity)
        annual_mwh = _device_annual_mwh(optimization_data, code)
        profile = _device_profile(optimization_data, code)
        lines = [
            f"{dimension_label}: "
            f"{system_node_value(node, config_state, optimization_data).replace(chr(10), ' · ')}",
        ]
        if profile and code in HEAT_GENERATOR_CODES | COOLING_GENERATOR_CODES:
            output_label = (
                "Wärmeleistung" if code in HEAT_GENERATOR_CODES else "Kälteleistung"
            )
            lines.append(
                f"Max. {output_label} im Betrieb: "
                f"{format_result_number(max(profile), 1)} kW"
            )
        lines.extend(_design_parameter_lines(code, result, values, optimization_data))
        lines.append(f"Investition: {format_result_number(investment)} €")
        if code not in STORAGE_CODES:
            lines.append(f"Jahresenergie: {format_result_number(annual_mwh, 1)} MWh")
        return lines, profile

    load = _system_load_series(optimization_data)
    node_id = node.id.lower()
    if node_id == "grid":
        profile = _weighted_profile(
            optimization_data,
            lambda cluster: cluster.get("P_dem_gcp", []),
        )
        return [
            f"Spitzenbezug: {format_result_number(max(profile, default=0.0), 1)} kW",
            f"Energiebezug: {format_result_number(sum(profile) / 1000.0, 1)} MWh",
        ], profile
    if node_id == "load":
        return [
            f"Stromspitze: {format_result_number(max(load['electric'], default=0.0), 1)} kW",
            f"Wärmespitze: {format_result_number(max(load['heat'], default=0.0), 1)} kW",
            f"Kältespitze: {format_result_number(max(load['cooling'], default=0.0), 1)} kW",
        ], load["electric"]
    if node_id in {"heat_bus", "heat_grid"}:
        return [
            f"Spitzenleistung: {format_result_number(max(load['heat'], default=0.0), 1)} kW",
            *(_network_design_lines(optimization_data, "heating") if node_id == "heat_grid" else []),
        ], load["heat"]
    if node_id in {"cooling_bus", "cool_grid"}:
        return [
            f"Spitzenleistung: {format_result_number(max(load['cooling'], default=0.0), 1)} kW",
            *(_network_design_lines(optimization_data, "cooling") if node_id == "cool_grid" else []),
        ], load["cooling"]
    if node_id in {"converter", "inverter"}:
        profile = _weighted_profile(
            optimization_data,
            lambda cluster: cluster.get("P_dem_gcp", []),
        )
        return ["Kopplung Wechsel-/Gleichstrom", "Bidirektionaler Betrieb"], profile
    if node_id == "ac_bus":
        return [
            "Wechselstromverteilung",
            f"Lastspitze: {format_result_number(max(load['electric'], default=0.0), 1)} kW",
        ], load["electric"]
    if node_id == "dc_bus":
        pv_profile = _device_profile(optimization_data, "PV")
        return [
            "Gleichstromverteilung",
            f"PV-Spitze: {format_result_number(max(pv_profile, default=0.0), 1)} kW",
        ], pv_profile
    return ["Systemkomponente"], []



# Reduziert eine Jahresdauerlinie auf höchstens die gewünschte Punktzahl.
def duration_curve_sample(
    values: list[float],
    points: int = 160,
) -> list[float]:
    ordered = sorted((_number(value) for value in values), reverse=True)
    if len(ordered) <= points:
        return ordered
    return [
        ordered[round(index * (len(ordered) - 1) / (points - 1))]
        for index in range(points)
    ]

# Erkennt einen zentralen Speicher an den Endpunkten einer Topologiekante.
def central_storage_code_on_edge(
    topology: Topology, edge: TopologyEdge,
) -> str | None:
    codes = {
        node.device_code
        for node_id in (edge.source, edge.target)
        if (node := topology.nodes.get(node_id)) is not None
        and not node.parent_id
        and node.device_code in STORAGE_CODES
    }
    return next(iter(codes)) if len(codes) == 1 else None

# Bildet aus HEO-Knotenbezeichnungen den angezeigten Kantentitel.
def edge_display_title(topology: Topology, edge: TopologyEdge) -> str:
    def label(node_id: str) -> str:
        node = topology.nodes.get(node_id)
        return (
            node_label_variants(node).full.replace("\n", " ")
            if node is not None else node_id
        )

    source_label = label(edge.source)
    target_label = label(edge.target)
    storage_code = central_storage_code_on_edge(topology, edge)
    if storage_code:
        storage_node = topology.nodes.get(edge.source)
        if storage_node is not None and storage_node.device_code == storage_code:
            return f"{source_label} ↔ {target_label}"
        return f"{target_label} ↔ {source_label}"
    return source_label if edge.source == edge.target else f"{source_label} → {target_label}"
