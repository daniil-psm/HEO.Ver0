# Gemeinsamer Dash-Renderer für kanonische Topologieszenen.
#
# Das Modul löst keine Geometrie auf. Es übersetzt ausschließlich eine bereits
# berechnete heo.topology.core.TopologyScene in einen Renderplan und in
# Dash-Komponenten. Der leere Edge-Host wird vom globalen Asset
# topology_edge_renderer.js mit nativen SVG-Elementen befüllt. So bleiben
# alle Nodes im Dash-DOM, ohne eine zusätzliche Python-SVG-Abhängigkeit oder ein
# isolierendes iframe zu benötigen.

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping, Sequence

from dash import html

from heo.model.devices import central_device_metadata
from ui.components.dashboard_info import main_panel_info_header

from heo.topology.geometry import (
    CANVAS_WIDTH,
    TOPOLOGY_EDGE_STROKE_WIDTH,
    topology_html_node_style,
)
from heo.topology.definitions import (
    COLORS,
    energy_carrier_color,
    energy_carrier_label,
)
from heo.topology.layout import (
    POWER_PILL_PART_IDS,
    PixelSceneGeometry,
    topology_grid_lines,
)
from heo.topology.model import (
    TOPOLOGY_COMPONENT_COLUMNS,
    TOPOLOGY_COMPONENT_ROWS,
    TOPOLOGY_LEGEND_CARRIERS,
    Topology,
    TopologyComponentFlow,
    TopologyComponentModel,
    TopologyComponentParameter,
    TopologyComponentRole,
    TopologyEdge,
    TopologyNode,
    topology_component_models,
    topology_component_node,
    topology_component_ports,
)
from heo.topology.core import TopologyScene
from heo.topology.labels import node_label_variants
from heo.topology.nodes import power_pill_label_ys


TopologyPresentation = Literal["configurator", "system", "sankey", "pfc"]


# Beschreibt Anzahl, Größe, Geschwindigkeit und Richtung der animierten
# Partikel eines Energieflusses.
@dataclass(frozen=True)
class EdgeParticlePlan:
    count: int
    radius: float
    duration: float
    speed: float
    gap: float
    direction: Literal["forward", "reverse"]


# Beschreibt die Teilstücke einer Kante an einem Speicher.
@dataclass(frozen=True)
class StorageEdgeSplit:
    discharged_width: float
    loss_width: float
    discharged_offset_y: float
    loss_offset_y: float


# Bündelt SVG-Pfad, Liniengestaltung, Hover-Metadaten und optionale
# Partikelanimation einer einzelnen Verbindung.
@dataclass(frozen=True)
class EdgeRenderItem:
    id: str
    path: str
    color: str
    width: float
    opacity: float
    linecap: str
    dotted: bool
    scales_with_scene: bool
    hover_focus: bool = False
    anchor: str | None = None
    label: str | None = None
    particles: EdgeParticlePlan | None = None
    storage_split: StorageEdgeSplit | None = None


# Vollständiger, rendererfertiger Plan ohne Layoutentscheidungen.
@dataclass(frozen=True)
class TopologyRenderPlan:
    instance_id: str
    presentation: TopologyPresentation
    canvas_width: float
    canvas_height: float
    nodes: tuple[TopologyNode, ...]
    edges: tuple[EdgeRenderItem, ...]
    geometry: PixelSceneGeometry
    message: str | None = None


# Schätzt die Pfadlänge aus den Abständen aufeinanderfolgender Koordinatenpaare
# und begrenzt das Ergebnis auf mindestens eine Einheit.
def _path_length_estimate(path: str) -> float:
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path)]
    points = list(zip(values[0::2], values[1::2]))
    return max(
        1.0,
        sum(
            math.hypot(x2 - x1, y2 - y1)
            for (x1, y1), (x2, y2) in zip(points, points[1:])
        ),
    )


# Erzeugt die Beschriftung einer Verbindung aus Quell- und Zielknoten.
def _is_central_storage_node(node: TopologyNode | None) -> bool:
    return bool(
        node is not None and node.device_code and not node.parent_id
        and (
            str((central_device_metadata(node.device_code) or {}).get("slot") or "")
            .endswith("storage")
        )
    )


# Erzeugt die Beschriftung einer Topologiekante.
def _edge_label(
    topology: Topology, edge: TopologyEdge, *, bidirectional: bool = False,
) -> str:
    # Liefert den vollständigen Knotennamen ohne Zeilenumbrüche;
    # bei unbekannten Knoten dient deren ID als Ersatz.
    def label(node_id: str) -> str:
        node = topology.nodes.get(node_id)
        if node is None:
            return node_id
        return node_label_variants(node).full.replace("\n", " ")

    if bidirectional:
        source = topology.nodes.get(edge.source)
        target = topology.nodes.get(edge.target)
        if _is_central_storage_node(target):
            return f"{label(edge.target)} ↔ {label(edge.source)}"
        if _is_central_storage_node(source):
            return f"{label(edge.source)} ↔ {label(edge.target)}"
    return f"{label(edge.source)} → {label(edge.target)}"


# Berechnet die Partikelanimation aus Flussbetrag, Pfadlänge und optionaler Skala.
# Sehr kleine Flüsse und fehlende Pfade erhalten keine Animation. Die Anzahl
# wird begrenzt; das Vorzeichen bestimmt die Bewegungsrichtung.
def _pfc_particle_plan(
    edge: TopologyEdge,
    *,
    animation_scale: Any | None,
) -> EdgeParticlePlan | None:
    magnitude = abs(edge.value)
    if magnitude < 0.05 or not edge.path:
        return None
    path_length = _path_length_estimate(edge.path)
    if animation_scale is None:
        duration = max(2.2, 5.2 - magnitude / 24)
        speed = path_length / duration
        gap = 74.0
    else:
        speed = float(animation_scale.speed(edge.value))
        gap = float(animation_scale.gap(edge.value))
    count = int(max(1, min(64, round(path_length / max(1.0, gap)))))
    radius = 4.6
    duration = max(0.35, path_length / max(1.0, speed))
    return EdgeParticlePlan(
        count=count,
        radius=radius,
        duration=duration,
        speed=speed,
        gap=gap,
        direction="forward" if edge.value >= 0 else "reverse",
    )


# Erzeugt ausschließlich Darstellungsmetadaten für vorhandene Pfade.
#
# Bestimmt Linienbreite, Deckkraft und Interaktion passend zur Ansicht.
# Sankey-Kanten skalieren mit der Energiemenge; die Leistungsflussansicht
# erhält Partikelanimationen. Fehlende Pfade lösen einen Fehler aus.
def _edge_items(
    topology: Topology,
    geometry: PixelSceneGeometry,
    presentation: TopologyPresentation,
    *,
    animation_scale: Any | None = None,
    storage_energy_mwh: Mapping[str, tuple[float, float, float]] | None = None,
) -> tuple[EdgeRenderItem, ...]:
    max_value = max((abs(edge.value) for edge in topology.edges), default=0.0)
    result: list[EdgeRenderItem] = []
    for edge in topology.edges:
        if edge.path is None:
            raise ValueError(
                f"Kante {edge.id!r} besitzt keinen kanonisch aufgelösten Pfad"
            )
        magnitude = abs(edge.value)
        storage_split = None
        if presentation == "sankey":
            if magnitude <= 1e-9 or max_value <= 0:
                continue
            ratio = magnitude / max_value
            width = max(1.0, geometry.node_diameter * ratio)
            opacity = 0.62 if magnitude >= 0.05 else 0.18
            linecap = "round"
            scales_with_scene = True
            hover_focus = True
            anchor = f"EDGE:{edge.id}"
            storage_node = next((
                node for node_id in (edge.source, edge.target)
                if (node := topology.nodes.get(node_id)) is not None
                and _is_central_storage_node(node)
            ), None)
            storage_values = (storage_energy_mwh or {}).get(edge.id)
            if storage_node is not None and storage_values is not None:
                charged, discharged, loss = storage_values
                if charged > 0:
                    discharged_width = width * min(1.0, discharged / charged)
                    loss_width = width - discharged_width
                    storage_split = StorageEdgeSplit(
                        discharged_width=discharged_width,
                        loss_width=loss_width,
                        discharged_offset_y=-loss_width / 2,
                        loss_offset_y=discharged_width / 2,
                    )
                    linecap = "butt"
                label = (
                    f"{_edge_label(topology, edge, bidirectional=True)}: "
                    f"eingespeichert {charged:.3f} MWh/a, "
                    f"ausgespeichert {discharged:.3f} MWh/a, "
                    f"Verluste {loss:.3f} MWh/a"
                )
            elif storage_node is not None:
                label = (
                    f"{_edge_label(topology, edge, bidirectional=True)}: "
                    f"eingespeichert {magnitude:.3f} MWh/a"
                )
            else:
                label = f"{_edge_label(topology, edge)}: {magnitude:.1f} MWh/a"
        elif presentation == "pfc":
            width = 2.2 if magnitude >= 0.05 else 1.2
            opacity = 0.66 if magnitude >= 0.05 else 0.24
            linecap = "round"
            scales_with_scene = False
            hover_focus = False
            anchor = None
            label = None
        else:
            width = TOPOLOGY_EDGE_STROKE_WIDTH
            opacity = 1.0
            linecap = "butt"
            scales_with_scene = False
            hover_focus = presentation == "configurator"
            anchor = None
            label = _edge_label(topology, edge) if hover_focus else None
        result.append(EdgeRenderItem(
            id=edge.id,
            path=edge.path,
            color=COLORS.get(edge.carrier, COLORS["neutral"]),
            width=width,
            opacity=opacity,
            linecap=linecap,
            dotted=edge.dotted,
            scales_with_scene=scales_with_scene,
            hover_focus=hover_focus,
            anchor=anchor,
            label=label,
            particles=(
                _pfc_particle_plan(edge, animation_scale=animation_scale)
                if presentation == "pfc" else None
            ),
            storage_split=storage_split,
        ))
    return tuple(result)


# Erzeugt den gemeinsamen Renderplan aus genau einer kanonischen Szene.
def build_topology_render_plan(
    scene: TopologyScene,
    *,
    presentation: TopologyPresentation,
    instance_id: str,
    animation_scale: Any | None = None,
    storage_energy_mwh: Mapping[str, tuple[float, float, float]] | None = None,
) -> TopologyRenderPlan:
    return TopologyRenderPlan(
        instance_id=str(instance_id),
        presentation=presentation,
        canvas_width=CANVAS_WIDTH,
        canvas_height=scene.geometry.canvas_height,
        nodes=tuple(sorted(
            scene.topology.nodes.values(),
            key=lambda node: (node.z_index, node.id),
        )),
        edges=_edge_items(
            scene.topology,
            scene.geometry,
            presentation,
            animation_scale=animation_scale,
            storage_energy_mwh=storage_energy_mwh,
        ),
        geometry=scene.geometry,
        message=scene.topology.message,
    )


# Gemeinsames, aus der Szenengeometrie abgeleitetes Raster.
def topology_grid_component(geometry: PixelSceneGeometry) -> html.Div:
    usable_width = CANVAS_WIDTH - 2 * geometry.grid_padding
    usable_height = geometry.canvas_height - 2 * geometry.grid_padding
    return html.Div(
        className="topology-grid-overlay topology-visual-layer",
        title="Dynamisches Topologie-Raster",
        style={
            "left": f"{geometry.grid_padding / CANVAS_WIDTH * 100:.4f}%",
            "top": f"{geometry.grid_padding / geometry.canvas_height * 100:.4f}%",
            "width": f"{usable_width / CANVAS_WIDTH * 100:.4f}%",
            "height": f"{usable_height / geometry.canvas_height * 100:.4f}%",
        },
        children=[
            html.Div(
                className=(
                    "topology-grid-line "
                    f"is-{line.orientation} is-{line.kind}"
                ),
                style={
                    "left" if line.orientation == "vertical" else "top":
                    f"{line.position * 100:.5f}%"
                },
            )
            for line in topology_grid_lines(geometry)
        ],
    )


# Leerer, sicher serialisierter Host für das native Browser-SVG.
def topology_edge_host(plan: TopologyRenderPlan) -> html.Div:
    payload = json.dumps(
        [asdict(edge) for edge in plan.edges],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return html.Div(
        className=(
            "topology-edge-host topology-visual-layer "
            f"is-{plan.presentation}"
        ),
        role="img",
        **{
            "aria-label": "Energieflüsse",
            "data-topology-edge-plan": payload,
            "data-topology-canvas-width": f"{plan.canvas_width:g}",
            "data-topology-canvas-height": f"{plan.canvas_height:g}",
        },
    )


# Gemeinsame HTML-Node; Interaktion ist eine reine View-Policy.
def topology_node_component(
    node: TopologyNode,
    *,
    canvas_height: float,
    interactive: bool,
    value: str | None = None,
    component_id: Any | None = None,
    extra_classes: Sequence[str] = (),
    extra_attributes: Mapping[str, Any] | None = None,
) -> Any:
    labels = node_label_variants(node)
    classes = [
        "topology-node-surface",
        "topology-scene-node",
        f"topology-scene-node-{node.shape}",
        *extra_classes,
    ]
    if node.shape == "pill":
        classes.append("topology-scene-node-pill")
    if value is not None:
        classes.append("energy-pfc-node")
    show_inline_label = node.id not in POWER_PILL_PART_IDS[:2]
    attributes: dict[str, Any] = {
        "data-topology-anchor": node.id,
        "data-topology-parent": node.parent_id or "",
        "data-topology-label-full": labels.full,
        "data-topology-label-wrapped": labels.wrapped,
        "data-topology-label-short": labels.short,
    }
    if not show_inline_label:
        # AC und DC erhalten ihr sichtbares Label als separat positionierten
        # Text in ``topology_node_layer``. Die Markierung verhindert, dass die
        # responsive Browserlogik zusätzlich das absichtlich leere Inline-
        # Label des großen Pillensegments befüllt.
        attributes["data-topology-label-external"] = "true"
    if interactive:
        attributes["data-topology-action"] = "result-node"
    attributes.update(extra_attributes or {})
    children = [
        html.Span(
            labels.wrapped if show_inline_label else "",
            className="topology-node-label",
        ),
        html.Span(value, className="energy-pfc-node-value")
        if value else None,
    ]
    common = dict(
        className=" ".join(classes),
        style=topology_html_node_style(node, canvas_height=canvas_height),
        title=labels.full.replace("\n", " "),
        children=children,
        **attributes,
    )
    if component_id is not None:
        common["id"] = component_id
    if interactive:
        return html.Button(type="button", n_clicks=0, **common)
    return html.Div(**common)


# Rendert die zentralen Topology-Farben als einzeilige Legende.
def topology_carrier_legend(
    carriers: Sequence[str] = TOPOLOGY_LEGEND_CARRIERS,
) -> html.Div:
    return html.Div(
        className="topology-carrier-legend",
        role="list",
        **{"aria-label": "Legende der Energieträger"},
        children=[
            html.Div(
                className="topology-carrier-legend-item",
                role="listitem",
                style={"--topology-carrier-color": energy_carrier_color(carrier)},
                children=[
                    html.Span(className="topology-carrier-legend-line", **{"aria-hidden": "true"}),
                    html.Span(energy_carrier_label(carrier)),
                ],
            )
            for carrier in carriers
        ],
    )


# Zeichnet einen Anschluss der Komponentendokumentation mit der Farbe
# des Energieträgers sowie der vorgegebenen Höhe und Pfeilrichtung.
def _topology_documentation_port(
    flow: TopologyComponentFlow,
    *,
    side: Literal["input", "output"],
    y: float,
    direction: Literal["left", "right"] = "right",
) -> html.Div:
    return html.Div(
        className=(
            f"topology-component-port is-{side} is-direction-{direction}"
        ),
        **{"aria-label": f"{side}: {flow.label}"},
        style={
            "--topology-port-color": energy_carrier_color(flow.carrier),
            "--topology-port-y": f"{y * 100:.3f}%",
        },
        children=[
            html.Span(className="topology-component-port-line", **{"aria-hidden": "true"}),
        ],
    )


# Rendert die kanonische Unterstrichnotation als echtes Tiefzeichen.
def _topology_parameter_symbol(
    parameter: TopologyComponentParameter,
) -> html.Span:
    base, separator, subscript = parameter.symbol.partition("_")
    children: list[Any] = [base]
    if separator and subscript:
        children.append(html.Sub(subscript))
    return html.Span(
        children,
        className="topology-component-parameter-symbol",
        **{"aria-label": parameter.symbol},
    )


# Schreibt den ersten Buchstaben klein und lässt den restlichen Text unverändert.
def _lowercase_initial(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


# Kompakte Symbolzeile mit ausführlicher Hover-/Fokusdarstellung.
def _topology_component_parameters(
    parameters: Sequence[TopologyComponentParameter],
) -> html.Div:
    compact_children: list[Any] = []
    for index, parameter in enumerate(parameters):
        if index:
            compact_children.append(html.Span(", ", **{"aria-hidden": "true"}))
        compact_children.append(_topology_parameter_symbol(parameter))

    return html.Div(
        className="topology-component-parameters",
        children=[
            html.Div(
                compact_children,
                className="topology-component-parameters-compact",
            ),
            html.Div(
                className="topology-component-parameters-details",
                children=[
                    html.Div(
                        className="topology-component-parameter-detail",
                        children=[
                            _topology_parameter_symbol(parameter),
                            html.Span(
                                f": {_lowercase_initial(parameter.name)}",
                                className="topology-component-parameter-name",
                            ),
                        ],
                    )
                    for parameter in parameters
                ],
            ),
        ],
    )


# Gemeinsamer, nicht interaktiver Komponentenblock aus Topology-Daten.
#
# Leitet Knoten und Anschlusspositionen aus dem Komponentenmodell ab.
# Ordnet bidirektionale Flüsse auf beiden Seiten an und ergänzt Titel,
# Komponentencode und Parameterbeschreibungen.
def topology_component_block(
    component: TopologyComponentModel,
    *,
    title_prefix: str = "",
    anchor_id: str | None = None,
    extra_classes: Sequence[str] = (),
    focusable: bool = True,
) -> html.Article:
    node = topology_component_node(component)
    input_ports = topology_component_ports(component, "input")
    output_ports = topology_component_ports(component, "output")
    if component.bidirectional:
        left_ports = (
            (component.inputs[0], "input", input_ports[0].y, "right"),
            (component.outputs[1], "output", output_ports[1].y, "left"),
        )
        right_ports = (
            (component.outputs[0], "output", output_ports[0].y, "right"),
            (component.inputs[1], "input", input_ports[1].y, "left"),
        )
    else:
        left_ports = tuple(
            (flow, "input", port.y, "right")
            for flow, port in zip(component.inputs, input_ports)
        )
        right_ports = tuple(
            (flow, "output", port.y, "right")
            for flow, port in zip(component.outputs, output_ports)
        )
    display_title = f"{title_prefix}{component.title}"
    display_label = f"{display_title} ({component.heo_code_label})"
    return html.Article(
        className=" ".join(("topology-component-block", *extra_classes)),
        tabIndex=0 if focusable else -1,
        style={"--node-color": node.color},
        **{
            "aria-label": display_label,
            "data-topology-anchor": anchor_id or node.id,
            "data-topology-role": component.role,
            "data-topology-column": component.column,
        },
        children=[
            html.Div(
                className="topology-component-ports is-input",
                children=[
                    _topology_documentation_port(
                        flow, side=side, y=y, direction=direction
                    )
                    for flow, side, y, direction in left_ports
                ],
            ),
            html.Div(
                className=(
                    "topology-node-surface topology-component-node "
                    "topology-scene-node-pill"
                ),
                title=display_label,
                children=[
                    html.Div(
                        className=(
                            "topology-component-node-heading topology-node-label"
                        ),
                        children=[
                            html.Span(
                                display_title,
                                className="topology-component-node-title",
                            ),
                            html.Span(
                                f"({component.heo_code_label})",
                                className="topology-component-node-code",
                            ),
                        ],
                    ),
                    _topology_component_parameters(component.parameters),
                ],
            ),
            html.Div(
                className="topology-component-ports is-output",
                children=[
                    _topology_documentation_port(
                        flow, side=side, y=y, direction=direction
                    )
                    for flow, side, y, direction in right_ports
                ],
            ),
        ],
    )


# Wärmepumpe mit einem aus dem Originalmodell geklonten Backup-Block.
def _heat_pump_system_block(
    component: TopologyComponentModel,
    components_by_id: Mapping[str, TopologyComponentModel],
) -> html.Div:
    backup = components_by_id.get(component.backup_component_id or "")
    children: list[Any] = [
        topology_component_block(
            component,
            extra_classes=("topology-component-heat-pump-primary",),
        )
    ]
    if backup is not None:
        children.append(html.Div(
            className="topology-component-backup-reveal",
            children=topology_component_block(
                backup,
                title_prefix="Backup-Erzeuger - ",
                anchor_id=f"DOC:{component.id}:BACKUP:{backup.id}",
                extra_classes=("topology-component-backup",),
                focusable=False,
            ),
        ))
    return html.Div(
        className="topology-component-heat-pump-system",
        **{"data-topology-heat-pump": component.id},
        children=children,
    )


# Einheitliche Matrixzelle, auch für kombinierte Output-Bereiche.
def _topology_component_matrix_cell(
    role: TopologyComponentRole,
    column: str,
    components: Sequence[TopologyComponentModel],
    *,
    extra_classes: Sequence[str] = (),
    children: Sequence[Any] | None = None,
) -> html.Div:
    classes = [
        "topology-component-matrix-cell",
        *extra_classes,
    ]
    if not components:
        classes.append("is-empty")
    rendered_children = (
        list(children)
        if children is not None
        else [
            *(topology_component_block(component) for component in components),
        ]
    )
    return html.Div(
        className=" ".join(classes),
        **{
            "data-topology-role": role,
            "data-topology-column": column,
        },
        children=rendered_children,
    )


# Fasst thermische Wandler unter einer Gruppenüberschrift zusammen.
# Wärmepumpen werden dabei zusammen mit ihrem verfügbaren Backup-Erzeuger gezeigt.
def _thermal_converter_section(
    group: str,
    label: str,
    components: Sequence[TopologyComponentModel],
) -> html.Section:
    components_by_id = {
        component.id: component
        for component in topology_component_models()
    }
    return html.Section(
        className=f"topology-component-thermal-group is-{group}",
        **{"data-topology-thermal-group": group},
        children=[
            html.H4(label, className="topology-component-thermal-group-heading"),
            *(
                _heat_pump_system_block(component, components_by_id)
                if group == "heat_pump_system"
                else topology_component_block(component)
                for component in components
            ),
        ],
    )


# Teilt RW/TWW-Wandler in exklusive und gemeinsame Outputs.
def _thermal_converter_matrix_group() -> html.Div:
    candidates = (
        *topology_component_models("converter", "heat"),
        *topology_component_models("converter", "dhw"),
    )

    # Sammelt die Energieträger aller Ausgänge einer Komponente.
    def output_carriers(component: TopologyComponentModel) -> set[str]:
        return {flow.carrier for flow in component.outputs}

    dual = tuple(
        component for component in candidates
        if {"heat", "dhw"}.issubset(output_carriers(component))
    )
    heat_only = tuple(
        component for component in candidates
        if "heat" in output_carriers(component) and component not in dual
    )
    dhw_only = tuple(
        component for component in candidates
        if "dhw" in output_carriers(component) and component not in dual
    )
    thermal_sections = tuple(
        _thermal_converter_section(
            group,
            label,
            tuple(component for component in dual if component.thermal_group == group),
        )
        for group, label in (
            ("heat_generator", "Alleinige Wärmeerzeuger"),
            ("heat_pump_system", "Wärmepumpen-Systeme (WP)"),
            ("chp_system", "Blockheizkraftwerke (BHKW)"),
        )
    )
    return html.Div(
        className="topology-component-matrix-thermal-converters",
        **{"data-topology-role": "converter"},
        children=[
            _topology_component_matrix_cell(
                "converter", "heat", heat_only,
                extra_classes=("is-heat-only",),
            ),
            _topology_component_matrix_cell(
                "converter", "dhw", dhw_only,
                extra_classes=("is-dhw-only",),
            ),
            _topology_component_matrix_cell(
                "converter", "heat-dhw", dual,
                extra_classes=("is-dual-output",),
                children=thermal_sections,
            ),
        ],
    )


# AC/DC-Wandler mit einem gemeinsamen Feld für den Inverter.
def _electrical_converter_matrix_group() -> html.Div:
    ac_components = topology_component_models("converter", "ac")
    inverter = tuple(
        component for component in ac_components if component.bidirectional
    )
    ac_only = tuple(
        component for component in ac_components if not component.bidirectional
    )
    dc_only = topology_component_models("converter", "dc")
    return html.Div(
        className="topology-component-matrix-electrical-converters",
        **{"data-topology-role": "converter"},
        children=[
            _topology_component_matrix_cell(
                "converter",
                "ac-dc",
                inverter,
                extra_classes=("is-bidirectional-converter",),
            ),
            _topology_component_matrix_cell("converter", "ac", ac_only),
            _topology_component_matrix_cell("converter", "dc", dc_only),
        ],
    )


# Gemeinsame RW-/TWW-Zelle für Quellen und Erzeuger.
def _shared_thermal_output_matrix_cell(
    role: TopologyComponentRole,
) -> html.Div:
    components_by_id = {
        component.id: component
        for column in ("heat", "dhw")
        for component in topology_component_models(role, column)
    }
    return _topology_component_matrix_cell(
        role,
        "heat-dhw",
        tuple(components_by_id.values()),
        extra_classes=("is-shared-thermal-output",),
    )


# Rendert das kanonische Rollen-/Hauptoutput-Raster der DG-Komponenten.
def topology_component_matrix() -> html.Div:
    cells: list[Any] = [
        html.Div("Rolle", className="topology-component-matrix-corner")
    ]
    cells.extend(
        html.Div(label, className="topology-component-matrix-column-heading")
        for _column, label in TOPOLOGY_COMPONENT_COLUMNS
    )
    for role, role_label in TOPOLOGY_COMPONENT_ROWS:
        cells.append(html.Div(role_label, className="topology-component-matrix-row-heading"))
        column_index = 0
        while column_index < len(TOPOLOGY_COMPONENT_COLUMNS):
            column, _column_label = TOPOLOGY_COMPONENT_COLUMNS[column_index]
            if role == "converter" and column == "ac":
                cells.append(_electrical_converter_matrix_group())
                column_index += 2
                continue
            if role == "converter" and column == "heat":
                cells.append(_thermal_converter_matrix_group())
                column_index += 2
                continue
            if role in {"source", "generator"} and column == "heat":
                cells.append(_shared_thermal_output_matrix_cell(role))
                column_index += 2
                continue
            cells.append(_topology_component_matrix_cell(
                role,
                column,
                topology_component_models(role, column),
            ))
            column_index += 1
    return html.Div(
        className="topology-component-matrix-scroll",
        tabIndex=0,
        **{"aria-label": "Komponentenmatrix; horizontal scrollbar"},
        children=html.Div(className="topology-component-matrix", children=cells),
    )


# Vollständige Topology-Dokumentation für eine Dashboard-Rückseite.
def topology_documentation_page(title: str, introduction: str) -> html.Div:
    return html.Div(
        className="dashboard-info-copy topology-documentation",
        children=[
            main_panel_info_header(title, introduction),
            html.H3("Energiesystem-Topologie", className="topology-documentation-title"),
            topology_carrier_legend(),
            topology_component_matrix(),
        ],
    )


# Gemeinsame Node-Schicht einschließlich Strompillenlabels.
#
# Positioniert zunächst die gemeinsamen AC-/DC-Beschriftungen und ihre Werte.
# Rendert anschließend alle Knoten mit der gewünschten Interaktivität,
# ohne Werte auf den Stromsegmenten doppelt anzuzeigen.
def topology_node_layer(
    plan: TopologyRenderPlan,
    *,
    interactive: bool,
    interactive_node_ids: Sequence[str] = (),
    node_values: Mapping[str, str] | None = None,
) -> html.Div:
    values = node_values or {}
    selected_nodes = frozenset(interactive_node_ids)
    nodes_by_id = {node.id: node for node in plan.nodes}
    labels_y = power_pill_label_ys(
        nodes_by_id,
        canvas_height=plan.canvas_height,
    )
    power_labels: list[Any] = []
    for node_id in POWER_PILL_PART_IDS[:2]:
        node = nodes_by_id.get(node_id)
        if node is None or node_id not in labels_y:
            continue
        labels = node_label_variants(node)
        power_labels.append(html.Span(
            labels.wrapped,
            className="topology-power-pill-label",
            style={
                "left": f"{node.x * 100:.3f}%",
                "top": f"{labels_y[node_id] * 100:.3f}%",
                # Das externe Label wird gegen die tatsächliche Pillenbreite
                # vermessen, nicht gegen die Breite der gesamten Node-Schicht.
                "width": (
                    f"{(node.width or node.radius * 2) / plan.canvas_width * 92:.3f}%"
                ),
            },
            **{
                "data-topology-label-full": labels.full,
                "data-topology-label-wrapped": labels.wrapped,
                "data-topology-label-short": labels.short,
            },
        ))
        if values.get(node_id):
            power_labels.append(html.Span(
                values[node_id],
                className="topology-power-pill-value",
                style={
                    "left": f"{node.x * 100:.3f}%",
                    "top": f"{(labels_y[node_id] + 0.027) * 100:.3f}%",
                },
            ))
    return html.Div(
        className=(
            "energy-html-node-layer topology-visual-layer"
            + ("" if interactive or selected_nodes else " is-static")
        ),
        children=[
            topology_node_component(
                node,
                canvas_height=plan.canvas_height,
                interactive=interactive or node.id in selected_nodes,
                # AC-/DC-Segmente tragen ihr Label und ihren PFC-Wert als
                # gemeinsam positionierte Pillen-Texte unterhalb dieser
                # Liste. Ein zweiter Wert im Segment würde ihn überlagern.
                value=(
                    values.get(node.id)
                    if node_values is not None
                    and node.id not in POWER_PILL_PART_IDS[:2]
                    else None
                ),
            )
            for node in plan.nodes
        ] + power_labels,
    )


# Uniform skalierter Innenrahmen; verhindert Badge- und Portdrift.
def topology_scene_frame(
    plan: TopologyRenderPlan,
    *,
    children: Sequence[Any],
) -> html.Div:
    return html.Div(
        className="topology-scene-frame",
        style={"--topology-canvas-aspect": f"{plan.canvas_width / plan.canvas_height:.10f}"},
        **{
            "data-topology-canvas-width": f"{plan.canvas_width:g}",
            "data-topology-canvas-height": f"{plan.canvas_height:g}",
        },
        children=list(children),
    )


# Rendert alle Ansichten mit derselben Layer- und Skalierungsstruktur.
#
# Setzt Raster, Verbindungen, Knoten und Dekorationen in den skalierten Rahmen.
# Ergänzt außerhalb dieses Rahmens die Einblendungen und eine optionale Meldung.
def render_topology_scene(
    plan: TopologyRenderPlan,
    *,
    interactive_nodes: bool = False,
    interactive_node_ids: Sequence[str] = (),
    node_values: Mapping[str, str] | None = None,
    overlays: Sequence[Any] = (),
    decorations: Sequence[Any] = (),
    root_classes: Sequence[str] = (),
) -> html.Div:
    frame = topology_scene_frame(
        plan,
        children=[
            topology_grid_component(plan.geometry),
            topology_edge_host(plan),
            topology_node_layer(
                plan,
                interactive=interactive_nodes,
                interactive_node_ids=interactive_node_ids,
                node_values=node_values,
            ),
            *decorations,
        ],
    )
    return html.Div(
        className=" ".join((
            "topology-renderer topology-visual-root",
            f"topology-view-{plan.presentation}",
            *root_classes,
        )),
        **{
            "data-topology-instance": plan.instance_id,
            "data-topology-presentation": plan.presentation,
        },
        children=[
            frame,
            *overlays,
            html.Div(plan.message, className="energy-html-empty-message")
            if plan.message else None,
        ],
    )
