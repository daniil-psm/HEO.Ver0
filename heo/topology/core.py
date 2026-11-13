"""Baut die kanonische HEO-Topologieszene aus Gebäuden, Raster und Kanten."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from heo.topology.building import BuildingRingPlacement, _building_badge_nodes
from heo.topology.definitions import CONFIGURABLE_CENTRAL_CODES, normalize_slot_order, ordered_slot_devices
from heo.topology.geometry import CANVAS_HEIGHT, CANVAS_WIDTH, node_bounds
from heo.topology.layout import (
    PixelSceneGeometry, SceneElement, SceneGeometryKind, ScenePlacement,
    SlotPlaceholder, _pixel_scene_geometry,
)
from heo.topology.layout_plan import plan_topology_layout
from heo.topology.model import (
    Topology, TopologyBounds, TopologyCell, TopologyColumn, TopologyNode,
)
from heo.topology.nodes import _scene_geometry
from heo.topology.edges import _routed_edges
from heo.topology.sizing import topology_node_radius

@dataclass(frozen=True)
class TopologyScene:
    """Vollständig aufgelöste, renderunabhängige Energiesystemszene."""

    topology: Topology
    geometry: PixelSceneGeometry
    placeholders: dict[str, SlotPlaceholder]
    elements: tuple[SceneElement, ...] = ()
    building_rings: dict[int, tuple[BuildingRingPlacement, ...]] = field(
        default_factory=dict
    )


def _scene_elements(
    nodes: Mapping[str, TopologyNode],
    placeholders: Mapping[str, SlotPlaceholder],
    *,
    canvas_height: float,
    building_rings: Mapping[int, Sequence[BuildingRingPlacement]] | None = None,
    include_editing_placeholders: bool = False,
    standard_diameter: float = 0.0,
) -> tuple[SceneElement, ...]:
    """Vereinheitlicht Bounds und Layer, ohne UI-Anker zu Graph-Nodes zu machen."""

    # Graph-Nodes übernehmen ihre fachliche Identität und Zeichenebene in die Szene.
    result: list[SceneElement] = []
    for node_id, node in nodes.items():
        width = node.width or 2 * node.radius
        height = node.height or 2 * node.radius
        geometry: SceneGeometryKind = (
            node.shape
            if node.shape in {"pill", "building", "badge"}
            else "circle"
        )
        result.append(SceneElement(
            id=node_id,
            role="graph-node",
            geometry=geometry,
            placement=ScenePlacement(
                node.x * CANVAS_WIDTH,
                node.y * canvas_height,
                width,
                height,
                node.z_index,
            ),
            graph_node_id=node_id,
            parent_id=node.parent_id,
        ))
    # UI-Anker erhalten eigene Rollen, damit sie keine fachlichen Kantenendpunkte werden.
    for anchor_id, placeholder in placeholders.items():
        width = placeholder.width or 2 * placeholder.radius
        height = placeholder.height or 2 * placeholder.radius
        is_area = placeholder.width is not None or placeholder.height is not None
        result.append(SceneElement(
            id=f"anchor:{anchor_id}",
            role="area-anchor" if is_area else "control-anchor",
            geometry="area" if is_area else (
                "building" if placeholder.shape == "building" else "circle"
            ),
            placement=ScenePlacement(
                placeholder.x,
                placeholder.y,
                width,
                height,
            ),
        ))
    # Freie Ringplätze sind nur im editierbaren Modus interaktiv sichtbar.
    if include_editing_placeholders:
        badge_radius = topology_node_radius("badge", standard_diameter)
        for uid, placements in (building_rings or {}).items():
            parent_id = f"BUILDING:{uid}"
            parent = nodes.get(parent_id)
            if parent is None:
                continue
            for placement in placements:
                if placement.code:
                    continue
                result.append(SceneElement(
                    id=f"anchor:building:{uid}:{placement.key}",
                    role="control-anchor",
                    geometry="badge",
                    placement=ScenePlacement(
                        parent.x * CANVAS_WIDTH + placement.x,
                        parent.y * canvas_height + placement.y,
                        2 * badge_radius,
                        2 * badge_radius,
                        30 + placement.slot_index,
                    ),
                    parent_id=parent_id,
                    angle=placement.angle,
                ))
    return tuple(result)


def _topology_cells(
    state: Mapping[str, Any], nodes: Mapping[str, TopologyNode],
    *, canvas_height: float = CANVAS_HEIGHT,
) -> tuple[TopologyCell, ...]:
    """Sichtbare Slotgruppen für Darstellung und Interaktion zusammenfassen."""

    labels = {
        "dc_source": ("DC-Quellen", "dc", "source"),
        "dc_storage": ("DC-Speicher", "dc", "storage"),
        "heat_source": ("Wärmeerzeuger", "heat", "source"),
        "heat_storage": ("Wärmespeicher", "heat", "storage"),
        "cool_source": ("Kälteerzeuger", "cooling", "source"),
        "cool_storage": ("Kältespeicher", "cooling", "storage"),
    }
    result: list[TopologyCell] = []
    for slot, (title, carrier, role) in labels.items():
        slot_node_ids = [
            code for code in ordered_slot_devices(state, slot) if code in nodes
        ]
        if slot == "heat_source":
            slot_node_ids.extend(
                code for code in ordered_slot_devices(state, "coupled_source")
                if code in nodes
            )
            slot_node_ids.sort(key=lambda code: (nodes[code].y, nodes[code].x))
        node_ids = tuple(slot_node_ids)
        if not node_ids:
            continue
        bounds = [
            node_bounds(nodes[node_id], CANVAS_WIDTH, canvas_height)
            for node_id in node_ids
        ]
        left = min(item.x for item in bounds)
        top = min(item.y for item in bounds)
        right = max(item.x + item.width for item in bounds)
        bottom = max(item.y + item.height for item in bounds)
        result.append(TopologyCell(
            id=slot,
            title=title,
            carrier=carrier,
            role=role,
            node_ids=node_ids,
            bounds=TopologyBounds(left, top, right - left, bottom - top),
        ))
    return tuple(result)


def build_topology_scene(
    configuration: Mapping[str, Any] | None,
    buildings: Sequence[Mapping[str, Any]] | None = None,
    *,
    canvas_height: float = CANVAS_HEIGHT,
    force_dc: bool = False,
    force_cooling: bool = False,
    include_editing_placeholders: bool = True,
    center_parallel_ports: bool = False,
) -> TopologyScene:
    """Baut die kanonische Szene für Konfigurator und Ergebnisansichten.

    Die Funktion kennt weder Dash-Komponenten noch Vorschau- oder Klickzustände.
    Platzhalter für editierbare Plusflächen sind optional. Der Konfigurator
    verwendet sie als eigenes UI-Overlay; Ergebnisansichten lassen sie aus,
    damit ausschließlich tatsächlich vorhandene Komponenten die Geometrie
    von Netz- und Lastpillen bestimmen.
    """

    # Eingaben lokal normalisieren, damit alle folgenden Schritte dieselbe Auswahl sehen.
    state = dict(configuration or {})
    rows = [dict(row) for row in (buildings or [])]
    selected = [
        code for code in state.get("central_devices") or []
        if code in CONFIGURABLE_CENTRAL_CODES
    ]
    state["central_devices"] = selected
    state["slot_order"] = normalize_slot_order(selected, state.get("slot_order"))
    # Logische Belegung vor Pixelprojektion, Nodes und Kanten vollständig auflösen.
    plan = plan_topology_layout(
        state, rows,
        force_dc=force_dc, force_cooling=force_cooling,
        include_editing_placeholders=include_editing_placeholders,
    )
    geometry = _pixel_scene_geometry(state, rows, canvas_height=canvas_height, plan=plan)
    nodes, placeholders = _scene_geometry(
        state,
        rows,
        canvas_height=geometry.canvas_height,
        force_dc=force_dc,
        force_cooling=force_cooling,
        include_editing_placeholders=include_editing_placeholders,
        pixel=geometry,
    )
    # Gebäuderinge und Kanten lesen dieselbe bereits projizierte Geometrie.
    nodes.update(
        _building_badge_nodes(
            rows,
            nodes,
            canvas_height=geometry.canvas_height,
            ring_placements=geometry.building_rings,
            standard_diameter=geometry.node_diameter,
        )
    )
    edges = _routed_edges(
        state,
        rows,
        nodes,
        canvas_height=geometry.canvas_height,
        placeholders=placeholders,
        center_parallel_ports=center_parallel_ports,
        pixel=geometry,
    )
    # Die renderunabhängige Szene bündelt sichtbare Geometrie und interaktive Anker.
    topology = Topology(
        nodes=nodes,
        edges=edges,
        columns=tuple(
            TopologyColumn(name, name.replace("_", " ").title(), x / CANVAS_WIDTH)
            for name, x in geometry.column_x.items()
        ),
        selected_devices=frozenset(selected),
        cells=_topology_cells(state, nodes, canvas_height=geometry.canvas_height),
        mode="canonical",
    )
    return TopologyScene(
        topology,
        geometry,
        placeholders,
        _scene_elements(
            nodes,
            placeholders,
            canvas_height=geometry.canvas_height,
            building_rings=geometry.building_rings,
            include_editing_placeholders=include_editing_placeholders,
            standard_diameter=geometry.node_diameter,
        ),
        geometry.building_rings,
    )


def build_topology(
    configuration: Mapping[str, Any] | None,
    buildings: Sequence[Mapping[str, Any]] | None = None,
    *,
    canvas_height: float = CANVAS_HEIGHT,
    include_editing_placeholders: bool = True,
    center_parallel_ports: bool = False,
) -> Topology:
    """Öffentlicher kanonischer Topologie-Builder ohne UI-Rückgaben."""

    return build_topology_scene(
        configuration,
        buildings,
        canvas_height=canvas_height,
        include_editing_placeholders=include_editing_placeholders,
        center_parallel_ports=center_parallel_ports,
    ).topology
