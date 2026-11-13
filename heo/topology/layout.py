"""Raster, Slotpositionen und Platzhalter der kanonischen HEO-Topologieszene."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from heo.topology.definitions import (
    INDIVIDUAL_COMPONENT_CONTROLS,
)
from heo.topology.geometry import CANVAS_HEIGHT, CANVAS_WIDTH, distribute_routing_lanes
from heo.topology.model import GridPosition, resolve_overlapping_grid
from heo.topology.layout_plan import TopologyLayoutPlan, plan_topology_layout
from heo.topology.building import BuildingRingPlacement
from heo.topology.sizing import (
    CENTRAL_STACK_STEP, topology_node_content_ratio, topology_node_radius,
)

# Renderer-unabhängige Darstellungsregeln der kanonischen Szene.  Fenster
# dürfen eigene Interaktion und Ergebnisinhalte ergänzen, aber nicht die
# Silhouette der gemeinsamen Topologie verändern.
POWER_PILL_PART_IDS = ("AC_BUS", "DC_BUS", "INVERTER")
TOPOLOGY_NODE_STROKE_WIDTH = 4.0
TOPOLOGY_BADGE_STROKE_WIDTH = 2.0

@dataclass(frozen=True)
class SlotLayout:
    """Geometrie eines geordneten zentralen Komponenten-Stacks."""

    slot: str
    anchor_x: float
    anchor_y: float
    carrier: str
    step_y: float = CENTRAL_STACK_STEP
    radius: float = 55.0
    shape: str = "circle"


@dataclass(frozen=True)
class SlotPlaceholder:
    """Nächste freie Position eines Slots."""

    slot: str
    x: float
    y: float
    carrier: str
    radius: float = 55.0
    shape: str = "circle"
    width: float | None = None
    height: float | None = None


SceneElementRole = Literal["graph-node", "control-anchor", "area-anchor"]
SceneGeometryKind = Literal["circle", "pill", "area", "building", "badge"]


@dataclass(frozen=True)
class ScenePlacement:
    """Aufgelöste Position eines sichtbaren oder interaktiven Scene-Elements."""

    x: float
    y: float
    width: float
    height: float
    z_index: int = 0

    @property
    def left(self) -> float:
        """Linke Grenze des Szenenelements in Pixeln."""

        return self.x - self.width / 2

    @property
    def top(self) -> float:
        """Obere Grenze des Szenenelements in Pixeln."""

        return self.y - self.height / 2

    @property
    def right(self) -> float:
        """Rechte Grenze des Szenenelements in Pixeln."""

        return self.x + self.width / 2

    @property
    def bottom(self) -> float:
        """Untere Grenze des Szenenelements in Pixeln."""

        return self.y + self.height / 2


@dataclass(frozen=True)
class SceneElement:
    """Gemeinsame Layoutdefinition ohne Vermischung der Graph-Semantik.

    Kreis-Nodes, Pillen und Konfiguratoranker nehmen damit am selben
    Bounds- und Layer-Modell teil. Nur ``graph-node`` verweist auf eine
    fachliche Node und darf dadurch Endpunkt einer Edge sein.
    """

    id: str
    role: SceneElementRole
    geometry: SceneGeometryKind
    placement: ScenePlacement
    graph_node_id: str | None = None
    parent_id: str | None = None
    angle: float | None = None


@dataclass(frozen=True)
class ProjectedRoute:
    """Projizierte Route mit normierten Anschlusshöhen, Portversätzen und Spuren in Pixeln."""

    id: str
    source: str
    target: str
    carrier: str
    kind: str
    source_y: float
    target_y: float
    source_offset: float
    target_offset: float
    lanes: dict[str, float]


@dataclass(frozen=True)
class PixelSceneGeometry:
    """Gemeinsame Pixelgeometrie vor der Normierung auf die Canvas-Höhe."""

    layouts: dict[str, SlotLayout]
    device_positions: dict[str, tuple[float, float]]
    reserved_device_positions: dict[str, tuple[float, float]]
    placeholders: dict[str, SlotPlaceholder]
    bounds: dict[str, tuple[float, float]]
    building_groups: dict[str, tuple[int, ...]]
    canvas_height: float
    column_x: dict[str, float]
    cell_width: float
    cell_height: float
    node_diameter: float
    pill_width: float
    grid_padding: float
    column_count: float
    max_row_track: int
    # AC-Porttracks bleiben im Strombus reserviert, obwohl die zugehörigen
    # BHKW-Nodes im Wärmeerzeuger-Stack stehen.
    coupled_track_by_code: dict[str, int]
    coupled_placeholder_track: int | None
    chp_ac_lane_track: int | None
    chp_ac_track_by_code: dict[str, int]
    chp_ac_lane_bounds: tuple[float, float] | None
    external_source_start_track: int
    external_source_track_by_id: dict[str, int]
    dc_port_track_by_code: dict[str, int]
    heat_port_track_by_code: dict[str, int]
    gas_port_track_by_code: dict[str, int]
    logical_track_by_code: dict[str, int]
    elyz_dc_lane_bounds: tuple[float, float] | None
    chp_ac_lane_x: float | None
    chp_ac_lane_x_bounds: tuple[float, float] | None
    chp_ac_local_lane_x_bounds: tuple[float, float] | None
    active_external_source_ids: tuple[str, ...] = ()
    external_source_offset: float = 0.0
    ac_visible: bool = True
    routes: tuple[ProjectedRoute, ...] = ()
    routing_lanes: dict[str, dict[str, float]] = field(default_factory=dict)
    routing_corridors: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    building_rings: dict[int, tuple[BuildingRingPlacement, ...]] = field(default_factory=dict)

    def track_y_px(self, track: int) -> float:
        """Liefert die Pixel-Y-Koordinate eines Halbzeilen-Tracks."""

        return (
            self.grid_padding
            + self.cell_height / 2
            + track * self.cell_height / 2
        )

    def track_y(self, track: int) -> float:
        """Liefert die normierte Y-Koordinate eines Halbzeilen-Tracks."""

        return self.track_y_px(track) / self.canvas_height


@dataclass(frozen=True)
class TopologyGridLine:
    """Renderunabhängige Haupt- oder Zwischengrenze des Topologierasters."""

    orientation: Literal["vertical", "horizontal"]
    kind: Literal["main", "intermediate"]
    position: float


def topology_grid_lines(pixel: PixelSceneGeometry) -> tuple[TopologyGridLine, ...]:
    """Liefert die in allen Fenstern identisch hervorzuhebenden Rasterlinien.

    ``position`` ist relativ zur inneren Rasterfläche. Die konkrete
    HTML-/SVG-Ausgabe bleibt Aufgabe des jeweiligen Renderers.
    """

    lines: list[TopologyGridLine] = []
    for index in range(1, math.ceil(pixel.column_count)):
        lines.append(TopologyGridLine(
            "vertical", "main", index / pixel.column_count
        ))
    for index in range(math.floor(pixel.column_count)):
        lines.append(TopologyGridLine(
            "vertical", "intermediate", (index + 0.5) / pixel.column_count
        ))

    occupied_row_units = 1.0 + pixel.max_row_track / 2.0
    for index in range(1, math.ceil(occupied_row_units)):
        position = index / occupied_row_units
        if position < 1.0:
            lines.append(TopologyGridLine("horizontal", "main", position))
    for index in range(math.ceil(occupied_row_units)):
        position = (index + 0.5) / occupied_row_units
        if position < 1.0:
            lines.append(TopologyGridLine(
                "horizontal", "intermediate", position
            ))
    return tuple(lines)


def _pixel_scene_geometry(
    state: dict[str, Any], buildings: list[dict[str, Any]], *,
    canvas_height: float = CANVAS_HEIGHT, force_dc: bool = False,
    force_cooling: bool = False, include_editing_placeholders: bool = True,
    plan: TopologyLayoutPlan | None = None,
) -> PixelSceneGeometry:
    """Projiziert den gemeinsamen logischen Plan in das responsive Raster."""

    plan = plan or plan_topology_layout(
        state, buildings, force_dc=force_dc, force_cooling=force_cooling,
        include_editing_placeholders=include_editing_placeholders,
    )
    tracks = plan.tracks
    grid = resolve_overlapping_grid(
        canvas_width=CANVAS_WIDTH, canvas_height=canvas_height,
        column_count=plan.column_count, max_row_track=plan.max_row_track,
    )
    radius = topology_node_radius("standard", grid.node_diameter)
    building_radius = topology_node_radius("building", grid.node_diameter)
    pill_width = grid.cell_width * topology_node_content_ratio()

    def point(position: GridPosition) -> tuple[float, float]:
        """Überträgt eine logische Rasterposition relativ zum belegten Spaltenursprung in Pixel."""

        return grid.center(GridPosition(position.column - plan.column_origin, position.row_track))

    def box_pixels(box):
        """Liefert linke, obere, rechte und untere Grenze einer logischen Fläche in Pixeln."""

        left = point(GridPosition(box.left + .5, 0))[0] - grid.cell_width / 2
        right = left + (box.right - box.left) * grid.cell_width
        top = point(GridPosition(0, box.top))[1]
        bottom = point(GridPosition(0, box.bottom))[1]
        return left, top, right, bottom

    # Slot-Anker, Nodes und reservierte Ziele in das gemeinsame Pixelraster übertragen.
    column_x = {name: point(GridPosition(column, 0))[0] for name, column in plan.columns.items()}
    layouts = {}
    for name, slot in plan.slots.items():
        x, y = point(slot.position)
        if name in plan.pill_spans:
            span = plan.pill_spans[name]
            top, bottom = grid.row_bounds(span.first, span.last)
            y = (top + bottom) / 2
        layouts[name] = SlotLayout(
            name, x, y, slot.carrier, step_y=slot.step_tracks * grid.cell_height / 2,
            radius=building_radius if slot.shape == "building" else radius,
            shape=slot.shape,
        )
    positions = {
        key: point(element.position) for key, element in plan.elements.items()
        if element.role == "node" and element.shape != "pill"
    }
    reserved_device_positions = {key: point(pos) for key, pos in plan.reserved_positions.items()}
    # Interaktive Plus-Plätze und Auswahlflächen aus ihren geplanten Zellflächen zeichnen.
    placeholders = {}
    for key, element in plan.elements.items():
        if element.role not in {"control", "area"}:
            continue
        if element.role == "area":
            # other_area folgt den sichtbaren Kreisrändern; sein logischer
            # Platzbedarf bleibt eine Vereinigung ganzer Zellen.
            if key == "other_area":
                children = [plan.elements[k] for k in INDIVIDUAL_COMPONENT_CONTROLS if k in plan.elements]
                centers = [point(item.position) for item in children]
                left = min(x for x, _ in centers) - radius
                right = max(x for x, _ in centers) + radius
                top = min(y for _, y in centers) - radius
                bottom = max(y for _, y in centers) + radius
            else:
                left, top, right, bottom = box_pixels(element.footprint)
            placeholders[key] = SlotPlaceholder(
                key, (left + right) / 2, (top + bottom) / 2, element.carrier,
                radius, width=right - left, height=bottom - top,
            )
        else:
            x, y = point(element.position)
            placeholders[key] = SlotPlaceholder(
                key, x, y, element.carrier,
                building_radius if element.shape == "building" else radius,
                element.shape,
            )
    # Pillen behalten ihre logischen Spannen; Rundungen betreffen nur die sichtbare Kontur.
    bounds = {name: grid.row_bounds(span.first, span.last) for name, span in plan.pill_spans.items()}
    bounds["electric"] = grid.row_bounds(0, 0)
    # Die sichtbare AC-Kappe folgt dem Kreisradius; der Plan reserviert eine
    # vollständige Zelle. DC und AC teilen die volle Inverterzelle.
    ac_span = plan.pill_spans["ac"]
    dc_span = plan.pill_spans.get("dc")
    ac_top = grid.center(GridPosition(0, ac_span.first))[1] - radius
    ac_bottom = (
        grid.row_bounds(dc_span.first, dc_span.first)[1]
        if dc_span is not None
        else grid.center(GridPosition(0, ac_span.last))[1] + radius
    )
    bounds["ac"] = (ac_top, ac_bottom)

    # Anschlusszeilen und Leitungsspuren gemeinsam projizieren, ohne sie neu zu verteilen.
    chp_lane = plan.corridors.get("chp_ac")
    chp_ac_lane_bounds = (
        (point(GridPosition(0, chp_lane.top))[1], point(GridPosition(0, chp_lane.bottom))[1])
        if chp_lane is not None else None
    )
    chp_x = point(GridPosition(plan.columns["dc_source"] - .75, 0))[0] if chp_lane else None
    chp_local_x = point(GridPosition(plan.columns["converter"] + 1.25, 0))[0] if chp_lane else None
    elyz_lane = plan.corridors.get("elyz_dc")
    elyz_bounds = (
        (point(GridPosition(0, elyz_lane.top))[1], point(GridPosition(0, elyz_lane.bottom))[1])
        if elyz_lane is not None else None
    )
    routing_lanes = {}
    for name, group in plan.lane_groups.items():
        box = group.bounds
        start, end = (
            (point(GridPosition(box.left, 0))[0], point(GridPosition(box.right, 0))[0])
            if group.axis == "x" else
            (point(GridPosition(0, box.top))[1], point(GridPosition(0, box.bottom))[1])
        )
        routing_lanes[name] = distribute_routing_lanes(group.keys, start=start, end=end)
    routes = tuple(ProjectedRoute(
        route.id, route.source, route.target, route.carrier, route.kind,
        point(GridPosition(0, route.source_track))[1] / canvas_height,
        point(GridPosition(0, route.target_track))[1] / canvas_height,
        route.source_offset, route.target_offset,
        {parameter: routing_lanes[group][key] for parameter, group, key in route.lanes},
    ) for route in plan.routes)
    # Ringwinkel bleiben unverändert; nur der Radius erhält die responsive Pixelgröße.
    building_rings: dict[int, list[BuildingRingPlacement]] = {}
    for attachment in plan.attachments:
        uid = int(attachment.parent_id.split(":")[1])
        angle = math.radians(attachment.angle)
        building_rings.setdefault(uid, []).append(BuildingRingPlacement(
            attachment.key, attachment.device_code, attachment.carrier,
            attachment.slot_index, attachment.angle,
            math.cos(angle) * building_radius, math.sin(angle) * building_radius,
        ))
    return PixelSceneGeometry(
        ac_visible="AC_BUS" in plan.elements,
        routes=routes, routing_lanes=routing_lanes,
        routing_corridors={name: box_pixels(box) for name, box in plan.corridors.items()},
        building_rings={uid: tuple(ring) for uid, ring in building_rings.items()},
        layouts=layouts, device_positions=positions,
        reserved_device_positions=reserved_device_positions, placeholders=placeholders,
        bounds=bounds, building_groups=plan.building_groups,
        canvas_height=canvas_height, column_x=column_x,
        cell_width=grid.cell_width, cell_height=grid.cell_height,
        node_diameter=grid.node_diameter, pill_width=pill_width,
        grid_padding=grid.padding, column_count=grid.column_count,
        max_row_track=grid.max_row_track,
        coupled_track_by_code=tracks.coupled_track_by_code,
        coupled_placeholder_track=tracks.coupled_placeholder_track,
        chp_ac_lane_track=tracks.chp_ac_lane_track,
        chp_ac_track_by_code=tracks.chp_ac_track_by_code,
        chp_ac_lane_bounds=chp_ac_lane_bounds,
        external_source_start_track=tracks.external_start,
        external_source_track_by_id=tracks.external_source_track_by_id,
        dc_port_track_by_code=tracks.dc_port_track_by_code,
        heat_port_track_by_code=tracks.heat_port_track_by_code,
        gas_port_track_by_code=plan.gas_port_track_by_code,
        logical_track_by_code={
            **{code: pos.row_track for code, pos in plan.reserved_positions.items()},
            **{key: item.position.row_track for key, item in plan.elements.items()},
        },
        elyz_dc_lane_bounds=elyz_bounds,
        chp_ac_lane_x=chp_x,
        chp_ac_lane_x_bounds=(chp_x - grid.cell_width / 4, chp_x + grid.cell_width / 4) if chp_x is not None else None,
        chp_ac_local_lane_x_bounds=(chp_local_x - grid.cell_width / 4, chp_local_x + grid.cell_width / 4) if chp_local_x is not None else None,
        active_external_source_ids=plan.active_external_source_ids,
        external_source_offset=plan.external_source_offset,
    )
