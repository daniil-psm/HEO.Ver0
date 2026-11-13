"""DG-Ergebnisreihen für Topologie, Sankey und PFC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dg_adapter.shared.device_catalog import central_device_metadata
from heo.topology.model import TopologyEdge


@dataclass(frozen=True)
class ResultCluster:
    """Ein Ergebniscluster mit seiner Zuordnung zum ursprünglichen Jahresblock."""

    year_key: str
    key: str
    number: int
    representative: object
    assignments: tuple[int, ...]
    weight: float
    data: dict[str, Any]


def number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def sort_key(value: object) -> tuple[int, object]:
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)


def result_clusters(optimization_data: dict | None) -> list[ResultCluster]:
    """Liefert die Cluster des ersten simulierten Jahres in stabiler Reihenfolge."""

    data = optimization_data or {}
    years = data.get("results") or {}
    if not isinstance(years, dict) or not years:
        return []

    raw_year_key = sorted(years, key=sort_key)[0]
    year_key = str(raw_year_key)
    year = years.get(raw_year_key)
    if not isinstance(year, dict):
        return []

    representatives = list(data.get("clusters") or [])
    configured_weights = data.get("cluster_weights") or {}
    configured_assignments = data.get("cluster_assignments") or {}
    result: list[ResultCluster] = []

    for index, raw_cluster_key in enumerate(sorted(year, key=sort_key)):
        cluster = year.get(raw_cluster_key)
        if not isinstance(cluster, dict):
            continue
        cluster_key = str(raw_cluster_key)
        representative = (
            representatives[index] if index < len(representatives) else cluster_key
        )

        weight = 1.0
        if isinstance(configured_weights, dict):
            for candidate in (representative, str(representative), raw_cluster_key, cluster_key):
                if candidate in configured_weights:
                    weight = number(configured_weights[candidate]) or 1.0
                    break
        elif isinstance(configured_weights, (list, tuple)) and index < len(configured_weights):
            weight = number(configured_weights[index]) or 1.0

        assignments: tuple[int, ...] = ()
        if isinstance(configured_assignments, dict):
            raw_assignments = None
            for candidate in (representative, str(representative), raw_cluster_key, cluster_key):
                if candidate in configured_assignments:
                    raw_assignments = configured_assignments[candidate]
                    break
            if isinstance(raw_assignments, (list, tuple)):
                assignments = tuple(int(number(item)) for item in raw_assignments)

        result.append(ResultCluster(
            year_key=year_key,
            key=cluster_key,
            number=index + 1,
            representative=representative,
            assignments=assignments,
            weight=weight,
            data=cluster,
        ))
    return result


def time_step_hours(optimization_data: dict | None) -> float:
    time_data = (optimization_data or {}).get("time") or {}
    if isinstance(time_data, dict):
        seconds = number(time_data.get("timeResolution"))
        if seconds > 0:
            return seconds / 3600.0
    return 1.0


def series(value: object) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return []
    return [number(item) for item in value]


def sum_series(*items: list[float]) -> list[float]:
    length = max((len(values) for values in items), default=0)
    return [
        sum(values[index] for values in items if index < len(values))
        for index in range(length)
    ]


def subtract_series(positive: list[float], *negative: list[float]) -> list[float]:
    length = max([len(positive), *(len(values) for values in negative)], default=0)
    return [
        max(
            0.0,
            (positive[index] if index < len(positive) else 0.0)
            - sum(values[index] for values in negative if index < len(values)),
        )
        for index in range(length)
    ]


def signed_difference(positive: list[float], negative: list[float]) -> list[float]:
    length = max(len(positive), len(negative))
    return [
        (positive[index] if index < len(positive) else 0.0)
        - (negative[index] if index < len(negative) else 0.0)
        for index in range(length)
    ]


def device_result(cluster: dict[str, Any], code: str) -> dict[str, Any]:
    metadata = central_device_metadata(code) or {}
    dg_code = str(metadata.get("dg_code") or code)
    hub = cluster.get("energy_hub") or {}
    if isinstance(hub, dict) and isinstance(hub.get(dg_code), dict):
        return hub[dg_code]
    value = cluster.get(dg_code)
    return value if isinstance(value, dict) else {}


def carrier_tokens(carrier: str) -> tuple[str, ...]:
    return {
        "ac": ("power",),
        "power": ("power",),
        "dc": ("power",),
        "heat": ("heat",),
        "dhw": ("heat",),
        "cool": ("cool",),
        "cooling": ("cool",),
        "gas": ("gas",),
        "hydrogen": ("hydrogen",),
        "biomass": ("biom", "biomass"),
        "waste": ("waste",),
        "oil": ("oil",),
    }.get(carrier, (carrier,))


def device_flow_series(
    cluster: dict[str, Any], code: str, direction: str, carrier: str,
) -> list[float]:
    device = device_result(cluster, code)
    for token in carrier_tokens(carrier):
        values = series(device.get(f"ts_{direction}_{token}"))
        if values:
            return values
    return []


def storage_charge_series(cluster: dict[str, Any], code: str) -> list[float]:
    device = device_result(cluster, code)
    return series(device.get("ts_ch"))


def storage_annual_mwh(
    optimization_data: dict | None, code: str,
) -> tuple[float, float, float] | None:
    """Jahresbilanz eines zentralen Speichers aus den DG-Clusterwerten."""

    clusters = result_clusters(optimization_data)
    if not clusters:
        return None
    charged_kwh = discharged_kwh = 0.0
    step_hours = time_step_hours(optimization_data)
    for cluster in clusters:
        device = device_result(cluster.data, code)
        if "ch" in device and "dch" in device:
            charged = number(device["ch"])
            discharged = number(device["dch"])
        elif isinstance(device.get("ts_ch"), (list, tuple)) and isinstance(
            device.get("ts_dch"), (list, tuple)
        ):
            charged = sum(series(device["ts_ch"])) * step_hours / 1000.0
            discharged = sum(series(device["ts_dch"])) * step_hours / 1000.0
        else:
            return None
        charged_kwh += charged * cluster.weight
        discharged_kwh += discharged * cluster.weight
    loss_kwh = charged_kwh - discharged_kwh
    if loss_kwh < -1e-3:
        return None
    return (
        charged_kwh / 1000.0,
        discharged_kwh / 1000.0,
        max(0.0, loss_kwh) / 1000.0,
    )


def storage_signed_series(cluster: dict[str, Any], code: str) -> list[float]:
    """Positiv bedeutet Entladung vom Speicher zum Bus."""

    device = device_result(cluster, code)
    return signed_difference(series(device.get("ts_dch")), series(device.get("ts_ch")))


def building_results(cluster: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    return [
        (int(str(key)), value)
        for key, value in sorted(cluster.items(), key=lambda item: sort_key(item[0]))
        if str(key).isdigit() and isinstance(value, dict)
    ]


def building_load_series(cluster: dict[str, Any]) -> list[float]:
    combined = sum_series(*[
        series(value.get("res_load")) for _index, value in building_results(cluster)
    ])
    return combined or series(cluster.get("P_dem_total"))


def building_net_power_series(cluster: dict[str, Any]) -> list[float]:
    buildings = building_results(cluster)
    if not buildings:
        return signed_difference(
            series(cluster.get("P_dem_total")), series(cluster.get("P_inj_total"))
        )
    return sum_series(*[
        signed_difference(series(value.get("res_load")), series(value.get("res_inj")))
        for _index, value in buildings
    ])


def central_bus_load_series(cluster: dict[str, Any], carrier: str) -> list[float]:
    """Ermittelt die an LOAD abgegebene Restenergie aus der zentralen Busbilanz."""

    if carrier in {"ac", "power", "dc"}:
        return building_load_series(cluster)
    if carrier == "heat":
        explicit = series(cluster.get("P_district_heat_total"))
        if explicit and any(abs(value) > 1e-9 for value in explicit):
            return explicit
        hub = cluster.get("energy_hub") or {}
        generated = sum_series(*[
            series(device.get("ts_gen_heat"))
            for device in hub.values() if isinstance(device, dict)
        ])
        generated = sum_series(
            generated, series(device_result(cluster, "TES").get("ts_dch"))
        )
        return subtract_series(
            generated,
            series(device_result(cluster, "TES").get("ts_ch")),
            series(device_result(cluster, "AC").get("ts_cons_heat")),
        )
    if carrier in {"cool", "cooling"}:
        generated = sum_series(
            device_flow_series(cluster, "CC", "gen", "cooling"),
            device_flow_series(cluster, "AC", "gen", "cooling"),
            series(device_result(cluster, "CTES").get("ts_dch")),
        )
        return subtract_series(
            generated, series(device_result(cluster, "CTES").get("ts_ch"))
        )
    return []


def external_flow_series(cluster: dict[str, Any], node_id: str) -> list[float]:
    if node_id != "GRID":
        carrier = {
            "GAS_IMPORT": "gas",
            "BIOMASS_IMPORT": "biomass",
            "WASTE_IMPORT": "waste",
            "OIL_IMPORT": "oil",
            "H2_IMPORT": "hydrogen",
        }.get(node_id)
        building_key = {
            "gas": "res_gas",
            "biomass": "res_biomass",
            "waste": "res_waste",
            "oil": "res_oil",
            "hydrogen": "res_hydrogen",
        }.get(carrier)
        building_consumption = sum_series(*[
            series(result.get(building_key))
            for _index, result in building_results(cluster)
        ]) if building_key else []
        hub = cluster.get("energy_hub") or {}
        if carrier and isinstance(hub, dict):
            consumed: list[list[float]] = []
            generated: list[list[float]] = []
            charged: list[list[float]] = []
            discharged: list[list[float]] = []
            for raw_code, device in hub.items():
                if not isinstance(device, dict):
                    continue
                metadata = central_device_metadata(str(raw_code)) or {}
                for token in carrier_tokens(carrier):
                    consumed.append(series(device.get(f"ts_cons_{token}")))
                    generated.append(series(device.get(f"ts_gen_{token}")))
                if (
                    str(metadata.get("slot") or "").endswith("storage")
                    and carrier in set(metadata.get("inputs") or ())
                ):
                    charged.append(series(device.get("ts_ch")))
                    discharged.append(series(device.get("ts_dch")))
            balanced = subtract_series(
                sum_series(*consumed, *charged), sum_series(*generated, *discharged)
            )
            combined = sum_series(balanced, building_consumption)
            if combined:
                return combined
        if building_consumption:
            return building_consumption

    key = {
        "GRID": "P_dem_gcp",
        "GAS_IMPORT": "P_gas_total",
        "BIOMASS_IMPORT": "P_biomass_total",
        "WASTE_IMPORT": "P_waste_total",
        "OIL_IMPORT": "P_oil_total",
        "H2_IMPORT": "P_hydrogen_total",
    }.get(node_id)
    return series(cluster.get(key)) if key else []


def edge_series(cluster: dict[str, Any], edge: TopologyEdge) -> list[float]:
    """Nichtnegative Edge-Zeitreihe für die gewichtete Jahresaggregation."""

    if edge.target == "LOAD":
        return central_bus_load_series(cluster, edge.carrier)
    if edge.source == edge.target:
        return external_flow_series(cluster, edge.source)
    if edge.source == "GRID":
        return series(cluster.get("P_dem_gcp"))
    if edge.target == "GRID":
        return series(cluster.get("P_inj_gcp"))

    external_nodes = {
        "GAS_IMPORT", "BIOMASS_IMPORT", "WASTE_IMPORT", "OIL_IMPORT",
        "H2_IMPORT",
    }
    if edge.source in external_nodes:
        if edge.target.endswith("_BUS"):
            return external_flow_series(cluster, edge.source)
        return device_flow_series(cluster, edge.target, "cons", edge.carrier)

    target_metadata = central_device_metadata(edge.target) or {}
    if target_metadata:
        if str(target_metadata.get("slot") or "").endswith("storage"):
            return storage_charge_series(cluster, edge.target)
        return device_flow_series(cluster, edge.target, "cons", edge.carrier)

    source_metadata = central_device_metadata(edge.source) or {}
    if source_metadata:
        if str(source_metadata.get("slot") or "").endswith("storage"):
            return storage_charge_series(cluster, edge.source)
        return device_flow_series(cluster, edge.source, "gen", edge.carrier)
    return []


def _building_edge_series(cluster: dict[str, Any], edge: TopologyEdge) -> list[float]:
    try:
        building_index = int(edge.target.split(":", 1)[1])
    except (IndexError, ValueError):
        return []
    building = cluster.get(str(building_index))
    if not isinstance(building, dict):
        return []

    if edge.carrier in {"ac", "power", "dc"}:
        return signed_difference(
            series(building.get("res_load")), series(building.get("res_inj"))
        )
    if edge.carrier in {"heat", "dhw"}:
        return device_flow_series(building, "DH", "gen", "heat")
    if edge.carrier in {"cool", "cooling"}:
        return device_flow_series(building, "CC", "gen", "cooling")
    return []


def signed_edge_series(cluster: dict[str, Any], edge: TopologyEdge) -> list[float]:
    """Signierte PFC-Zeitreihe; positiv folgt der definierten Edge-Richtung."""

    if edge.source == "LOAD" and edge.target.startswith("BUILDING:"):
        return _building_edge_series(cluster, edge)
    if edge.target == "LOAD":
        if edge.carrier in {"ac", "power", "dc"}:
            return building_net_power_series(cluster)
        return central_bus_load_series(cluster, edge.carrier)
    if edge.source == edge.target:
        if edge.source == "GRID":
            return signed_difference(
                series(cluster.get("P_dem_gcp")), series(cluster.get("P_inj_gcp"))
            )
        return external_flow_series(cluster, edge.source)
    if edge.source == "GRID":
        return signed_difference(
            series(cluster.get("P_dem_gcp")), series(cluster.get("P_inj_gcp"))
        )
    if edge.target == "GRID":
        return signed_difference(
            series(cluster.get("P_inj_gcp")), series(cluster.get("P_dem_gcp"))
        )

    external_nodes = {
        "GAS_IMPORT", "BIOMASS_IMPORT", "WASTE_IMPORT", "OIL_IMPORT",
        "H2_IMPORT",
    }
    if edge.source in external_nodes:
        if edge.target.endswith("_BUS"):
            return external_flow_series(cluster, edge.source)
        return device_flow_series(cluster, edge.target, "cons", edge.carrier)

    source_metadata = central_device_metadata(edge.source) or {}
    if source_metadata:
        if str(source_metadata.get("slot") or "").endswith("storage"):
            return storage_signed_series(cluster, edge.source)
        return device_flow_series(cluster, edge.source, "gen", edge.carrier)

    target_metadata = central_device_metadata(edge.target) or {}
    if target_metadata:
        if str(target_metadata.get("slot") or "").endswith("storage"):
            return [
                -value for value in storage_signed_series(cluster, edge.target)
            ]
        return device_flow_series(cluster, edge.target, "cons", edge.carrier)
    return []
