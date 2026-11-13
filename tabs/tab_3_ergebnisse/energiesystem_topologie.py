"""Dash-Darstellung der HEO-Ergebnistopologie.

Die zentrale Szene liegt in heo.topology; DG-Kennwerte liefert der Output-Adapter.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from dash import html

from dg_adapter.output.topology_details import (
    duration_curve_sample, central_storage_code_on_edge, edge_display_title, central_storage_annual_lines, central_storage_annual_mwh, format_result_number, system_component_details,
)
from heo.display.device_labels import decentral_device_name
from heo.display.result_dialog_layout import result_dialog_view
from heo.display.result_details import overlay_field_from_line
from heo.topology.definitions import COLORS
from heo.topology.layout import PixelSceneGeometry
from heo.topology.model import (
    Topology,
    TopologyEdge,
    TopologyNode,
)
from heo.topology.core import TopologyScene
from heo.topology.labels import node_label_variants
from ui.components.form_overlay import (
    OVERLAY_GRID_CLASS,
    OVERLAY_SECTION_CLASS,
    readonly_fields_component,
)
from heo.display.field_presentation import (
    FieldPresentation,
    overlay_section,
)
from ui.components.topology_scene import build_topology_render_plan, render_topology_scene

from dg_adapter.output.pfc_results import PfcFrame


DashboardView = Literal["pfc", "sankey", "system"]


def _duration_polyline(
    values: list[float], x: float, y: float, width: float, height: float,
) -> str:
    """Skaliert Dauerlinienwerte auf die SVG-Zeichenfläche."""
    if not values:
        return ""

    maximum = max(values) or 1.0
    count = len(values)
    points = []
    for index, value in enumerate(values):
        point_x = x + width * index / max(1, count - 1)
        point_y = y + height - height * value / maximum
        points.append(f"{point_x:.1f},{point_y:.1f}")
    return " ".join(points)


# Erzeugt das eingebettete Bild einer Jahresdauerlinie.
def _duration_chart_data_uri(curve_values: list[float]) -> str:
    width, height = 382, 92
    points = _duration_polyline(curve_values, 0, 0, width, height)
    markup = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="4" '
        'fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)"/>'
        f'<polyline points="{points}" fill="none" stroke="#f2b43c" '
        'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(markup, safe="")


# Rendert die Ergebnisdetails einer ausgewählten Komponente.
def energy_result_card_component(
    node: TopologyNode,
    lines: list[str],
    curve_values: list[float],
    *,
    title_override: str | None = None,
) -> html.Div:
    main_fields: list[FieldPresentation] = []
    more_fields: list[FieldPresentation] = []
    for line in lines:
        field = overlay_field_from_line(line, parameter_scope=f"result:node:{node.id}")
        (main_fields if result_dialog_view(field.label) == "main" else more_fields).append(field)
    sampled_curve = duration_curve_sample(curve_values)
    more_details = None
    if more_fields:
        more_details = html.Details(
            className=f"{OVERLAY_SECTION_CLASS} energy-result-section",
            children=[
                html.Summary(overlay_section("Weitere Größen").title),
                readonly_fields_component(
                    more_fields,
                    class_name=f"{OVERLAY_GRID_CLASS} energy-result-grid",
                ),
            ],
        )
    curve_details = None
    if sampled_curve:
        curve_details = html.Details(
            className=f"{OVERLAY_SECTION_CLASS} energy-result-section",
            children=[
                html.Summary(overlay_section("Jahresdauerlinie").title),
                html.Img(
                    src=_duration_chart_data_uri(sampled_curve),
                    className="energy-result-chart",
                    alt="",
                    **{"aria-hidden": "true"},
                ),
            ],
        )
    return html.Div(
        className="topology-overlay-shell energy-result-overlay",
        **{
            "data-topology-anchor": node.id,
            "data-topology-color": node.color,
        },
        children=html.Section(
            className="topology-overlay-card energy-result-card",
            **{"data-form-layout-owner": "external"},
            children=[
                html.Header(
                    className="topology-overlay-header",
                    children=[
                        html.H2(
                            title_override or (
                                decentral_device_name("EH_DHW" if node.device_code == "DL" else node.device_code)
                                if node.shape == "badge" and node.device_code
                                else node_label_variants(node).full.replace("\n", " ")
                            ),
                            className="topology-overlay-title",
                        ),
                        html.Button(
                            "×", type="button",
                            className="energy-result-close topology-overlay-close",
                            **{
                                "aria-label": "Einblendung schließen",
                                "data-topology-action": "close-result",
                            },
                        ),
                    ],
                ),
                readonly_fields_component(
                    main_fields,
                    class_name=f"{OVERLAY_GRID_CLASS} energy-result-grid",
                ) if main_fields else None,
                more_details,
                curve_details,
            ],
        ),
    )


# Rendert die Ergebnisdetails einer ausgewählten Verbindung.
def energy_edge_card_component(
    topology: Topology,
    edge: TopologyEdge,
    optimization_data: dict | None = None,
) -> html.Div:
    storage_code = central_storage_code_on_edge(topology, edge)
    storage_values = (
        central_storage_annual_mwh(optimization_data, storage_code)
        if storage_code else None
    )
    fields = (
        [overlay_field_from_line(line, parameter_scope=f"result:storage:{storage_code}")
         for line in central_storage_annual_lines(storage_values)]
        if storage_values is not None else [FieldPresentation(
            label=("Eingespeicherte Energie" if storage_code else "Übertragene Energie"),
            value=format_result_number(abs(edge.value), 3 if storage_code else 1),
            unit="MWh/a",
            kind="number",
            parameter_key=f"result:edge:{edge.id}:energy",
            numeric_value=abs(edge.value),
        )]
    )
    return html.Div(
        className=(
            "topology-overlay-shell energy-result-overlay "
            "energy-edge-result-overlay"
        ),
        **{
            "data-topology-anchor": f"EDGE:{edge.id}",
            "data-topology-color": COLORS.get(edge.carrier, COLORS["neutral"]),
        },
        children=html.Section(
            className="topology-overlay-card energy-result-card",
            **{"data-form-layout-owner": "external"},
            children=[
                html.Header(
                    className="topology-overlay-header",
                    children=[
                        html.H2(
                            edge_display_title(topology, edge),
                            className="topology-overlay-title",
                        ),
                        html.Button(
                            "×", type="button",
                            className="energy-result-close topology-overlay-close",
                            **{
                                "aria-label": "Einblendung schließen",
                                "data-topology-action": "close-result",
                            },
                        ),
                    ],
                ),
                readonly_fields_component(
                    fields,
                    class_name=f"{OVERLAY_GRID_CLASS} energy-result-grid",
                ),
            ],
        ),
    )


# Rendert eine Ergebnisprojektion ohne eigene Layoutentscheidung.
def energy_topology_component(
    *,
    view: DashboardView,
    topology: Topology,
    scene_geometry: PixelSceneGeometry,
    instance_id: str,
    config_state: dict | None = None,
    optimization_data: dict | None = None,
    pfc_frame: PfcFrame | None = None,
) -> html.Div:
    if view not in {"system", "sankey", "pfc"}:
        raise ValueError(f"Nicht unterstützte Topologieansicht: {view}")
    scene = TopologyScene(
        topology=topology,
        geometry=scene_geometry,
        placeholders={},
        elements=(),
    )
    storage_energy_mwh: dict[str, tuple[float, float, float]] = {}
    if view == "sankey":
        for edge in topology.edges:
            code = central_storage_code_on_edge(topology, edge)
            if code:
                values = central_storage_annual_mwh(optimization_data, code)
                if values is not None:
                    storage_energy_mwh[edge.id] = values
    plan = build_topology_render_plan(
        scene,
        presentation=view,
        instance_id=instance_id,
        animation_scale=(pfc_frame.animation_scale if pfc_frame else None),
        storage_energy_mwh=storage_energy_mwh,
    )
    overlays: list[Any] = []
    if view == "system":
        for node in plan.nodes:
            lines, curve = system_component_details(
                node, config_state, optimization_data
            )
            overlays.append(energy_result_card_component(node, lines, curve))
    elif view == "sankey":
        overlays.extend(
            energy_edge_card_component(topology, edge, optimization_data)
            for edge in topology.edges
            if abs(edge.value) > 1e-9
        )
    return render_topology_scene(
        plan,
        interactive_nodes=view == "system",
        node_values=(pfc_frame.node_values if pfc_frame else None),
        overlays=overlays,
        decorations=(),
        root_classes=("energy-topology-renderer",),
    )
