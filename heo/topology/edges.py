"""Zeichnet die im gemeinsamen Layoutplan festgelegten Kanten und Anschlüsse."""
from __future__ import annotations

from typing import Any

from heo.topology.geometry import CANVAS_HEIGHT, TOPOLOGY_EDGE_STROKE_WIDTH
from heo.topology.layout import PixelSceneGeometry, SlotPlaceholder, _pixel_scene_geometry
from heo.topology.model import TopologyEdge, TopologyNode, TopologyPort
from heo.topology.routing import (
    _akm_heat_path, _chp_ac_path, _dc_elyz_path,
    _external_source_viewport_path, _ports_path,
    _rounded_dc_path, _rounded_hvh_path, _rounded_resource_path,
)


def _routed_edges(
    state: dict[str, Any], buildings: list[dict[str, Any]],
    nodes: dict[str, TopologyNode], *, canvas_height: float = CANVAS_HEIGHT,
    preview_node_ids: set[str] | None = None,
    placeholders: dict[str, SlotPlaceholder] | None = None,
    center_parallel_ports: bool = False,
    pixel: PixelSceneGeometry | None = None,
) -> list[TopologyEdge]:
    """Projiziert geplante Ports auf Node-Ränder und zeichnet gerundete Pfade."""

    pixel = pixel or _pixel_scene_geometry(state, buildings, canvas_height=canvas_height)
    canvas_height = pixel.canvas_height
    preview = preview_node_ids or set()
    spacing = TOPOLOGY_EDGE_STROKE_WIDTH / canvas_height if center_parallel_ports else 0.0
    edges = []
    # Pfadtypen verwenden ausschließlich ihre bereits projizierten Ports und Spuren.
    for route in pixel.routes:
        if route.source not in nodes or route.target not in nodes:
            continue
        source, target = nodes[route.source], nodes[route.target]
        source_y = route.source_y + route.source_offset * spacing
        target_y = route.target_y + route.target_offset * spacing
        kwargs = dict(source_y=source_y, target_y=target_y, canvas_height=canvas_height)
        if route.kind == "external":
            path = _external_source_viewport_path(source, route.carrier, canvas_height=canvas_height, source_y=source_y)
        elif route.kind == "straight":
            path = _ports_path(source, target, route.carrier, **kwargs)
        elif route.kind == "dc":
            path = _rounded_dc_path(source, target, **kwargs, **route.lanes)
        elif route.kind == "hvh":
            path = _rounded_hvh_path(source, target, route.carrier, **kwargs, **route.lanes)
        elif route.kind == "akm":
            path = _akm_heat_path(source, target, **kwargs, **route.lanes)
        elif route.kind == "chp":
            path = _chp_ac_path(source, target, **kwargs, **route.lanes)
        elif route.kind == "elyz":
            path = _dc_elyz_path(source, target, **kwargs, **route.lanes)
        elif route.kind == "resource":
            path = _rounded_resource_path(source, target, route.carrier, target_y=target_y,
                                          canvas_height=canvas_height, **route.lanes)
        else:
            raise ValueError(f"Unbekannter geplanter Pfadtyp: {route.kind}")
        # Graph-Portmetadaten folgen denselben Seiten und Höhen wie der sichtbare Pfad.
        carrier = {"power": "ac", "cool": "cooling"}.get(route.carrier, route.carrier)
        if route.kind == "external":
            # Die externe Eintrittskante beginnt tatsächlich am Viewportrand.
            source_x, source_side, target_side = 0.0, "right", "left"
        elif route.kind == "akm":
            source_x, source_side, target_side = source.x, "left", "left"
        elif route.kind in {"dc", "hvh", "chp", "elyz", "resource"}:
            source_x, source_side, target_side = source.x, "right", "left"
        else:
            source_x = source.x
            source_side, target_side = ("right", "left") if target.x >= source.x else ("left", "right")
        edges.append(TopologyEdge(
            id=route.id, source=route.source, target=route.target, carrier=carrier,
            source_port=TopologyPort(f"{route.id}:source", carrier, source_side, source_x, source_y),
            target_port=TopologyPort(f"{route.id}:target", carrier, target_side, target.x, target_y),
            routing="horizontal_tangent", path=path,
            dotted=route.source in preview or route.target in preview,
        ))
    return edges
