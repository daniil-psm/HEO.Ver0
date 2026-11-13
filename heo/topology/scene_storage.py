"""Serialisiert die HEO-Ergebnistopologie für den PFC-Store und stellt sie wieder her."""

from __future__ import annotations

from dataclasses import asdict
from .layout import PixelSceneGeometry, ProjectedRoute, SlotLayout, SlotPlaceholder
from .building import BuildingRingPlacement
from .model import Topology, TopologyEdge, TopologyNode, TopologyPort, TopologySegment

def pack_pfc_scene(scene) -> dict:
    """Hält nur die statische, bereits aufgelöste Ergebnis-Topologie vor."""

    return {
        "nodes": [asdict(node) for node in scene.topology.nodes.values()],
        "edges": [asdict(edge) for edge in scene.topology.edges],
        "geometry": asdict(scene.geometry),
        "mode": scene.topology.mode,
        "message": scene.topology.message,
    }

def unpack_pfc_scene(data: dict) -> tuple[Topology, PixelSceneGeometry]:
    """Baut Knoten, Kanten und Geometrie aus dem gespeicherten PFC-Zustand neu auf."""

    def node_from_data(raw: dict) -> TopologyNode:
        """Stellt eine Node einschließlich ihrer typisierten Lastsegmente wieder her."""

        return TopologyNode(**{
            **raw,
            "segments": tuple(
                TopologySegment(**segment) for segment in raw.get("segments", ())
            ),
        })

    def port_from_data(raw: dict | None) -> TopologyPort | None:
        """Stellt einen gespeicherten Anschluss wieder her oder liefert None."""

        return TopologyPort(**raw) if raw else None

    def edge_from_data(raw: dict) -> TopologyEdge:
        """Stellt eine Kante einschließlich ihrer typisierten Quell- und Zielports wieder her."""

        return TopologyEdge(**{
            **raw,
            "source_port": port_from_data(raw.get("source_port")),
            "target_port": port_from_data(raw.get("target_port")),
        })

    # JSON-Dicts wieder in die gemeinsamen Graph-Datentypen überführen.
    topology = Topology(
        nodes={
            node["id"]: node_from_data(node)
            for node in data["nodes"]
        },
        edges=[edge_from_data(edge) for edge in data["edges"]],
        mode=data["mode"],
        message=data["message"],
    )
    # Der Store enthält die bereits berechnete Geometrie; erneute Layoutplanung würde sie verändern.
    geometry = dict(data["geometry"])
    geometry["layouts"] = {
        key: SlotLayout(**value) for key, value in geometry["layouts"].items()
    }
    geometry["placeholders"] = {
        key: SlotPlaceholder(**value)
        for key, value in geometry["placeholders"].items()
    }
    # JSON wandelt Tupel in Listen um; die Geometrieschnittstelle erwartet wieder Tupel.
    for name in (
        "device_positions", "reserved_device_positions", "bounds",
        "building_groups",
    ):
        geometry[name] = {
            key: tuple(value) for key, value in geometry[name].items()
        }
    for name in (
        "chp_ac_lane_bounds", "elyz_dc_lane_bounds",
        "chp_ac_lane_x_bounds", "chp_ac_local_lane_x_bounds",
    ):
        if geometry[name] is not None:
            geometry[name] = tuple(geometry[name])
    geometry["active_external_source_ids"] = tuple(
        geometry["active_external_source_ids"]
    )
    # Ältere gespeicherte Szenen können noch ohne Routen, Ringe oder Korridore vorliegen.
    geometry["routes"] = tuple(ProjectedRoute(**route) for route in geometry.get("routes", ()))
    geometry["building_rings"] = {
        int(uid): tuple(BuildingRingPlacement(**item) for item in items)
        for uid, items in geometry.get("building_rings", {}).items()
    }
    geometry["routing_corridors"] = {
        key: tuple(value) for key, value in geometry.get("routing_corridors", {}).items()
    }
    return topology, PixelSceneGeometry(**geometry)
