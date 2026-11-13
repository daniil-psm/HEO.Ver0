# Aggregiert DG-Jahresflüsse für Kanten der HEO-Topologie.

from __future__ import annotations
from dataclasses import replace
from heo.model.devices import central_device_metadata
from heo.topology.model import Topology
from dg_adapter.output.result_series import (
    edge_series, result_clusters, storage_annual_mwh, time_step_hours,
)

def annual_edge_values(
    optimization_data: dict | None,
    topology: Topology,
) -> dict[str, float]:
    """Aggregiert Jahresflüsse; Speicherbreiten entsprechen der Ladeenergie."""

    clusters = result_clusters(optimization_data)
    step_hours = time_step_hours(optimization_data)
    values: dict[str, float] = {}
    for edge in topology.edges:
        storage_nodes = [
            node for node_id in (edge.source, edge.target)
            if (node := topology.nodes.get(node_id)) is not None
            and node.device_code and not node.parent_id
            and (
                str((central_device_metadata(node.device_code) or {}).get("slot") or "")
                .endswith("storage")
            )
        ]
        if len(storage_nodes) == 1:
            storage_values = storage_annual_mwh(
                optimization_data, storage_nodes[0].device_code,
            )
            if storage_values is not None:
                values[edge.id] = storage_values[0]
                continue
        energy_wh = sum(
            sum(edge_series(cluster.data, edge)) * step_hours * cluster.weight
            for cluster in clusters
        )
        values[edge.id] = max(0.0, energy_wh / 1_000_000.0)
    return values


def topology_with_annual_edge_values(
    optimization_data: dict | None,
    topology: Topology,
) -> Topology:
    values = annual_edge_values(optimization_data, topology)
    return replace(
        topology,
        edges=[replace(edge, value=values.get(edge.id, 0.0)) for edge in topology.edges],
    )
