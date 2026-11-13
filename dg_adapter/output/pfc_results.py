# Bereitet Cluster, Kantenzeitreihen und Frames der Powerflow Card auf.

from __future__ import annotations

from dataclasses import replace
from typing import Any


from heo.topology.model import (
    Topology,
    TopologyNode,
    topology_component_models,
)

from heo.topology.pfc_model import FlowSnapshot, ClusterOption, FlowAnimationScale, PfcFrame, clamp
from .pfc_profiles import (
    get_optimization_power_series, get_optimization_snapshot, _find_first_existing_key,
    select_profile_dataframe, weather_store_to_dataframe, build_profile_weather_data,
    demand_store_to_dataframe, profile_tick_step,
)
from .pfc_flows import flow_snapshot_from_optimization, flow_snapshot, flow_snapshot_fallback

from .result_series import (
    ResultCluster,
    device_result,
    number,
    result_clusters,
    series,
    signed_edge_series,
    sum_series,
    time_step_hours,
)


STORAGE_DEVICE_CODES = frozenset({"BAT", "TES", "TES_DHW", "CTES", "H2S", "GS", "EV"})
CONVERTER_DEVICE_CODES = frozenset(
    code.upper()
    for component in topology_component_models("converter")
    for code in component.codes
)
GENERATOR_DEVICE_CODES = frozenset(
    code.upper()
    for component in topology_component_models("generator")
    for code in component.codes
)


# Liest eine vom DG-Ergebnis ausdrücklich gelieferte Clusterbeschreibung.
def _explicit_cluster_description(
    optimization_data: dict | None, cluster: ResultCluster,
) -> str | None:
    metadata = (optimization_data or {}).get("cluster_metadata") or {}
    candidates: list[object] = []
    if isinstance(metadata, dict):
        for key in (cluster.key, cluster.representative, str(cluster.representative)):
            if key in metadata:
                candidates.append(metadata[key])
    elif isinstance(metadata, (list, tuple)) and cluster.number <= len(metadata):
        candidates.append(metadata[cluster.number - 1])

    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("label") or candidate.get("description")
        text = str(candidate or "").strip()
        if text:
            return text
    return None


# Leitet bei Wochenclustern eine jahreszeitliche Bezeichnung ab.
def _seasonal_cluster_description(
    optimization_data: dict | None, cluster: ResultCluster,
) -> str | None:
    data = optimization_data or {}
    time_data = data.get("time") or {}
    if not isinstance(time_data, dict):
        return None
    cluster_seconds = number(time_data.get("clusterLength"))
    data_seconds = number(time_data.get("dataLength"))
    try:
        representative = int(cluster.representative)
    except (TypeError, ValueError):
        return None
    cluster_days = cluster_seconds / 86_400.0
    if not 6.0 <= cluster_days <= 8.0 or data_seconds <= 0:
        return None

    day = ((representative + 0.5) * cluster_seconds / 86_400.0) % 365.25
    if day < 59 or day >= 334:
        season = "Winter"
    elif day < 151:
        season = "Frühlings"
    elif day < 243:
        season = "Sommer"
    else:
        season = "Herbst"
    return f"Durchschnittliche {season}woche"


# Erstellt die auswählbaren Cluster der Powerflow Card.
def cluster_options(optimization_data: dict | None) -> list[ClusterOption]:
    options: list[ClusterOption] = []
    for cluster in result_clusters(optimization_data):
        description = (
            _explicit_cluster_description(optimization_data, cluster)
            or _seasonal_cluster_description(optimization_data, cluster)
        )
        fallback = f"Cluster {cluster.number}"
        if description:
            label = description if description.startswith("Cluster ") else f"{fallback}: {description}"
        else:
            label = fallback
        options.append(ClusterOption(cluster.key, cluster.number, label))
    return options


# Wählt einen vorhandenen Cluster oder den ersten verfügbaren.
def resolve_cluster_key(
    optimization_data: dict | None, selected_key: object,
) -> str | None:
    keys = [cluster.key for cluster in result_clusters(optimization_data)]
    selected = str(selected_key) if selected_key is not None else None
    return selected if selected in keys else (keys[0] if keys else None)


# Formatiert einen Leistungswert für die PFC-Knotenanzeige.
def _format_kw(value: float) -> str:
    rounded = round(value, 1)
    if rounded == 0:
        return "0 kW"
    return f"{rounded:+,.1f} kW".replace(",", "X").replace(".", ",").replace("X", ".")


# Formatiert einen Ladezustand für die PFC-Knotenanzeige.
def _format_soc(value_kwh: float) -> str:
    digits = 2 if 0 < abs(value_kwh) < 1 else 1
    return f"{value_kwh:,.{digits}f} kWh".replace(",", "X").replace(".", ",").replace("X", ".")


# Erkennt einen Speicherknoten anhand seiner Gerätekennung.
def _storage_code(node: TopologyNode) -> str | None:
    code = node.device_code or node.id
    return code if code in STORAGE_DEVICE_CODES else None


# Ordnet HEO-Gebäude-IDs den DG-Ergebnisindizes zu.
def _building_result_keys(optimization_data: dict | None) -> dict[str, str]:
    snapshot = (optimization_data or {}).get("topology_snapshot") or {}
    buildings = snapshot.get("buildings") if isinstance(snapshot, dict) else None
    if not isinstance(buildings, list):
        return {}
    return {
        str(building["id"]): str(building["result_index"])
        for building in buildings
        if isinstance(building, dict)
        and building.get("id") is not None
        and building.get("result_index") is not None
    }


# Liest die Ladezustandsreihe eines Speicherknotens aus einem Cluster.
def _storage_soc_series(
    cluster: ResultCluster,
    node: TopologyNode,
    building_keys: dict[str, str],
) -> list[float]:
    code = _storage_code(node)
    if code is None:
        return []
    data = cluster.data
    if node.id.startswith("BUILDING:"):
        building_id = node.id.split(":", 2)[1]
        # DG-Läufe verwenden teils die Gebäude-ID, teils den Snapshot-Index.
        data = cluster.data.get(building_id)
        direct_device = device_result(data, code) if isinstance(data, dict) else {}
        direct_soc = direct_device.get("ts_soc")
        has_direct_soc = isinstance(direct_soc, (list, tuple)) and bool(direct_soc)
        if code == "EV":
            has_direct_soc = has_direct_soc or any(
                isinstance(vehicle, dict)
                and isinstance(vehicle.get("ts_soc"), (list, tuple))
                and bool(vehicle["ts_soc"])
                for vehicle in direct_device.values()
            )
        if not has_direct_soc:
            data = cluster.data.get(building_keys.get(building_id, building_id))
        if not isinstance(data, dict):
            return []
    device = device_result(data, code)
    if code == "EV":
        individual = [
            series(vehicle.get("ts_soc"))
            for vehicle in device.values() if isinstance(vehicle, dict)
        ]
        values = sum_series(*individual) if individual else series(device.get("ts_soc"))
    else:
        values = series(device.get("ts_soc"))
    return [value / 1_000.0 for value in values]


# Formatiert den Zeitpunkt eines PFC-Zeitschritts.
def format_pfc_time(step_index: int, step_hours: float) -> str:
    """Formatiert einen PFC-Index als lesbaren Zeitpunkt im Cluster."""

    total_minutes = int(round(max(0, step_index) * max(0.0, step_hours) * 60))
    day = total_minutes // (24 * 60) + 1
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"Tag {day}, {hour:02d}:{minute:02d}"


# Baut die Zeitmarken für den PFC-Slider.
def pfc_timeline_marks(step_count: int, step_hours: float) -> dict[int, str]:
    """Erzeugt wenige, gleichmäßig lesbare Marken für den Cluster-Zeitbalken."""

    count = max(0, int(step_count or 0))
    if count <= 1:
        return {0: "Beginn"}

    maximum = count - 1
    duration_hours = count * max(0.0, float(step_hours or 0.0))
    marks: dict[int, str] = {}

    if 0.0 < duration_hours <= 30.0:
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            index = min(maximum, int(round(maximum * fraction)))
            total_minutes = int(round(index * step_hours * 60))
            marks[index] = f"{(total_minutes // 60) % 24:02d}:{total_minutes % 60:02d}"
        return marks

    if 0.0 < duration_hours <= 8.0 * 24.0:
        day_step = 24.0 / step_hours if step_hours > 0 else 0.0
        day_count = max(1, int(round(duration_hours / 24.0)))
        for day_index in range(day_count):
            index = min(maximum, int(round(day_index * day_step)))
            marks[index] = f"Tag {day_index + 1}"
        marks.setdefault(maximum, "Ende")
        return marks

    for fraction in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        index = min(maximum, int(round(maximum * fraction)))
        marks[index] = format_pfc_time(index, step_hours)
    return marks


# Bereitet Leistungsbeschriftungen für sichtbare Topologieknoten vor.
def _node_value_texts(
    topology: Topology,
    available_edge_ids: set[str],
) -> dict[str, str]:
    """Zeigt die betragsgrößte vorhandene Portleistung mit Knotenvorzeichen."""

    outgoing_nodes = {
        edge.source for edge in topology.edges if edge.source != edge.target
    }
    incoming_nodes = {
        edge.target for edge in topology.edges if edge.source != edge.target
    }
    producer_nodes: set[str] = set()
    for node in topology.nodes.values():
        if node.role != "source" or node.id == "GRID":
            continue
        code = (node.device_code or node.id).upper()
        if code in CONVERTER_DEVICE_CODES:
            continue
        if code not in GENERATOR_DEVICE_CODES and (
            node.id in outgoing_nodes and node.id in incoming_nodes
        ):
            continue
        producer_nodes.add(node.id)
    grid_has_regular_edge = any(
        edge.id in available_edge_ids
        and edge.source != edge.target
        and "GRID" in {edge.source, edge.target}
        for edge in topology.edges
    )
    values: dict[str, list[float]] = {node_id: [] for node_id in topology.nodes}
    for edge in topology.edges:
        if edge.id not in available_edge_ids:
            continue
        if edge.source == edge.target:
            # Die externe GRID-Schleife beschreibt den Netzbezug. Die
            # reguläre GRID-AC-Kante gibt dessen Richtung am Netzknoten an.
            if edge.source == "GRID" and grid_has_regular_edge:
                continue
            if edge.source in values:
                values[edge.source].append(
                    -edge.value if edge.source == "GRID" else edge.value
                )
            continue
        for node_id, direction in ((edge.source, 1), (edge.target, -1)):
            if node_id not in values:
                continue
            polarity = 1 if node_id in producer_nodes else -1
            values[node_id].append(direction * edge.value * polarity)
    return {
        node_id: (
            _format_kw(max(items, key=abs))
            if items and not _storage_code(topology.nodes[node_id]) else ""
        )
        for node_id, items in values.items()
    }


# Berechnet Kantenreihen, Speicherzustände und globale Skala einmal je Ergebnis.
def prepare_pfc_series(
    optimization_data: dict | None,
    topology: Topology,
) -> dict[str, Any]:
    """Berechnet alle PFC-Reihen und die globale Skala einmal je Ergebnis."""

    options = {option.key: option for option in cluster_options(optimization_data)}
    storage_nodes = [node for node in topology.nodes.values() if _storage_code(node)]
    building_keys = _building_result_keys(optimization_data)
    positive_values: list[float] = []
    prepared_clusters: list[dict[str, Any]] = []
    for cluster in result_clusters(optimization_data):
        edge_series: dict[str, list[float]] = {}
        for edge in topology.edges:
            values_kw = [
                value / 1_000.0
                for value in signed_edge_series(cluster.data, edge)
            ]
            edge_series[edge.id] = values_kw
            positive_values.extend(
                abs(value) for value in values_kw if abs(value) > 1e-9
            )
        option = options.get(cluster.key)
        storage_soc = {
            node.id: values
            for node in storage_nodes
            if (values := _storage_soc_series(cluster, node, building_keys))
        }
        prepared_clusters.append({
            "key": cluster.key,
            "number": cluster.number,
            "label": option.label if option else f"Cluster {cluster.number}",
            "step_count": max(
                (
                    len(values)
                    for values in (*edge_series.values(), *storage_soc.values())
                ),
                default=0,
            ),
            "edges": edge_series,
            "storage_soc": storage_soc,
        })
    return {
        "step_hours": time_step_hours(optimization_data),
        "minimum_kw": min(positive_values, default=0.0),
        "maximum_kw": max(positive_values, default=0.0),
        "clusters": prepared_clusters,
    }


# Setzt einen PFC-Frame aus vorbereiteten Reihen und gewähltem Zeitschritt zusammen.
def build_pfc_frame(
    optimization_data: dict | None,
    topology: Topology,
    selected_key: object = None,
    tick: int = 0,
    *,
    prepared: dict[str, Any] | None = None,
) -> tuple[Topology, PfcFrame]:
    """Belegt die Ergebnis-Topology mit einem Cluster-Zeitschritt.

    Die vorbereiteten Reihen können für alle Wiedergabe-Ticks wiederverwendet
    werden; ohne sie bleibt der bisherige direkte Aufruf möglich.
    """

    data = prepared if prepared is not None else prepare_pfc_series(
        optimization_data, topology
    )
    clusters = data["clusters"]
    selected = str(selected_key) if selected_key is not None else None
    cluster = next((item for item in clusters if item["key"] == selected), None)
    if cluster is None:
        cluster = clusters[0] if clusters else None
    scale = FlowAnimationScale(
        minimum_kw=data["minimum_kw"],
        maximum_kw=data["maximum_kw"],
    )
    if cluster is None:
        empty_topology = replace(
            topology,
            edges=[replace(edge, value=0.0) for edge in topology.edges],
        )
        return empty_topology, PfcFrame(
            cluster_key=None,
            cluster_number=None,
            cluster_label="",
            step_index=0,
            step_count=0,
            step_hours=data["step_hours"],
            title="Keine Cluster verfügbar",
            node_values={},
            animation_scale=scale,
        )

    step_count = cluster["step_count"]
    step_index = int(tick or 0) % max(1, step_count)
    edges = []
    for edge in topology.edges:
        values = cluster["edges"].get(edge.id, [])
        value = values[step_index % len(values)] if values else 0.0
        edges.append(replace(edge, value=value))
    current_topology = replace(topology, edges=edges)
    label = cluster["label"]
    step_hours = data["step_hours"]
    title = f"{label} · {format_pfc_time(step_index, step_hours)}"
    available_edge_ids = {
        edge_id for edge_id, values in cluster["edges"].items() if values
    }
    node_values = _node_value_texts(current_topology, available_edge_ids)
    for node_id, values in cluster.get("storage_soc", {}).items():
        if values:
            node_values[node_id] = _format_soc(values[step_index % len(values)])
    return current_topology, PfcFrame(
        cluster_key=cluster["key"],
        cluster_number=cluster["number"],
        cluster_label=label,
        step_index=step_index,
        step_count=step_count,
        step_hours=step_hours,
        title=title,
        node_values=node_values,
        animation_scale=scale,
    )


