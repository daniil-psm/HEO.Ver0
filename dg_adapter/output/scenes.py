# Übersetzt rohe DG-Optimierungsergebnisse in eine HEO-Ergebnistopologieszene.

from __future__ import annotations

from heo.topology.model import Topology
from heo.topology.postprocessing import build_postprocessing_scene

from .topology_results import normalize_topology_results


# Normalisiert vorhandene DG-Ergebnisse und baut daraus eine HEO-Szene.
# Für noch nicht berechnete Szenarien liefert HEO die leere Ausgangsszene.
def build_result_scene(
    optimization_data: dict | None,
    building_state: dict | None = None,
    *,
    include_buildings: bool = True,
    center_parallel_ports: bool = False,
):
    normalized = (
        normalize_topology_results(optimization_data, building_state)
        if optimization_data and (optimization_data.get("results") or {})
        else None
    )
    return build_postprocessing_scene(
        normalized,
        include_buildings=include_buildings,
        center_parallel_ports=center_parallel_ports,
    )


# Liefert nur das fachliche Topologiemodell zu rohen DG-Ergebnissen.
def build_result_topology(
    optimization_data: dict | None,
    building_state: dict | None = None,
) -> Topology:
    return build_result_scene(optimization_data, building_state).topology
