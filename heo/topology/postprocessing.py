"""Baut aus normalisierten Ergebnisdaten die zentrale HEO-Topologieszene."""

from __future__ import annotations

from dataclasses import replace

from heo.topology.model import Topology
from heo.topology.core import (
    TopologyScene,
    build_topology_scene,
)
from heo.topology.definitions import normalize_slot_order


def configuration_from_results(normalized: dict) -> dict:
    """Übersetzt normalisierte Geräte und Gebäude in den Szenenvertrag."""

    selected = [
        str(device.get("code") or "")
        for device in normalized.get("central_devices") or []
        if device.get("code")
    ]
    buildings = list(normalized.get("buildings") or [])
    has_electric_connection = any(
        "ac" in set(building.get("central_carriers") or []) for building in buildings
    )
    return {
        "model": "heo-topology-v2",
        "central_devices": selected,
        "slot_order": normalize_slot_order(selected),
        "grid_enabled": has_electric_connection,
    }


def build_postprocessing_scene(
    normalized: dict | None,
    *,
    include_buildings: bool = True,
    center_parallel_ports: bool = False,
) -> TopologyScene:
    """Erstellt die Ergebnisansicht ohne DG-Formate oder Dash-Komponenten."""

    if not normalized:
        empty_scene = build_topology_scene(
            {"central_devices": [], "grid_enabled": False}, [],
            include_editing_placeholders=False,
            center_parallel_ports=center_parallel_ports,
        )
        return replace(
            empty_scene,
            topology=Topology(
                nodes={}, edges=[], mode="postprocessing",
                message="Noch keine abgeschlossenen Optimierungsergebnisse geladen.",
            ),
        )
    configuration = configuration_from_results(normalized)
    buildings = (normalized.get("buildings") or []) if include_buildings else []
    scene = build_topology_scene(
        configuration, buildings,
        include_editing_placeholders=False,
        center_parallel_ports=center_parallel_ports,
    )
    return replace(scene, topology=replace(scene.topology, mode="postprocessing"))
