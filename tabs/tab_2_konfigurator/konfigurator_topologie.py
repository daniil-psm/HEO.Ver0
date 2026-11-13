# Rendert die HEO-Topologieszene als interaktive Dash-Ansicht des Konfigurators.
from __future__ import annotations

import math
from typing import Any

from dash import html

from heo.display.device_labels import (
    SLOT_ADD_LABELS, TOPOLOGY_AREA_TITLES, decentral_device_abbreviation,
)
from heo.topology.building import (
    BuildingRingPlacement,
    building_available_candidates,
    building_ring_placements,
)
from heo.topology.core import build_topology_scene
from heo.topology.definitions import (
    CARRIER_LABELS, CENTRAL_DEVICES, COLORS, INDIVIDUAL_COMPONENT_CONTROLS, RESOURCE_FOR_DEVICE, unused_candidates,
)
from heo.topology.geometry import (
    CANVAS_HEIGHT, CANVAS_WIDTH, candidate_z_indices as _candidate_z_indices,
    place_candidate_group, topology_html_node_style,
    topology_responsive_square_size,
)
from heo.topology.labels import candidate_label_variants, node_label_variants
from heo.topology.layout import SlotPlaceholder
from heo.topology.model import TopologyNode
from heo.topology.nodes import power_pill_label_ys as _power_pill_label_ys
from heo.topology.sizing import (
    BUILDING_BADGE_RADIUS, BUILDING_NODE_RADIUS, CANDIDATE_RADIUS,
    topology_node_radius,
)
from ui.components.action_buttons import action_button
from ui.components.topology_scene import (
    build_topology_render_plan, topology_edge_host, topology_grid_component,
    topology_scene_frame, render_topology_scene,
)

# Darstellung und Öffnungszustand der großen +-Bereiche werden an einer Stelle
# gepflegt. Ihre konkrete Geometrie stammt weiterhin aus der kanonischen Szene.
AREA_SLOT_SPECS = {
    "dc_area": {
        "title": TOPOLOGY_AREA_TITLES["dc_area"],
        "class_name": "konfig-dc-area-slot",
        "trigger_slots": ("dc_source", "dc_storage"),
    },
    "cool_area": {
        "title": TOPOLOGY_AREA_TITLES["cool_area"],
        "class_name": "konfig-cool-area-slot",
        "trigger_slots": ("cool_source", "cool_storage"),
    },
    "other_area": {
        "title": TOPOLOGY_AREA_TITLES["other_area"],
        "class_name": "konfig-other-area-slot",
        "trigger_slots": tuple(INDIVIDUAL_COMPONENT_CONTROLS),
    },
}


# Liefert den fachlich konkreten Hover-Text eines Plus-Buttons.
def _slot_add_label(slot: str) -> str:
    code = INDIVIDUAL_COMPONENT_CONTROLS.get(slot)
    if code:
        return f"{_candidate_label(code)} hinzufügen"
    return SLOT_ADD_LABELS.get(slot, "Komponente hinzufügen")


# Convert a slot or candidate key into a stable CSS class token.
def _css_token(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in str(value)
    )


# Definiert die Größe einer quadratischen Topologiekachel.
def _responsive_square_style(
    width: float, height: float, *, canvas_height: float,
) -> dict[str, str]:
    size = topology_responsive_square_size(width, height, canvas_height=canvas_height)
    return {"width": size, "height": size}


# Leitet eine physisch runde Rundung aus dem logischen Radius ab.
def _rounded_radius_style(
    width: float, height: float, radius: float, *, canvas_height: float = CANVAS_HEIGHT,
) -> dict[str, str]:
    effective_radius = min(radius, width / 2, height / 2)
    # ``border-radius`` erwartet den Radius, nicht den Durchmesser der Node.
    # Die gemeinsame Größenfunktion hält ihn trotzdem auf beiden
    # Viewport-Achsen physisch gleich groß.
    return {"borderRadius": topology_responsive_square_size(
        effective_radius, effective_radius,
        canvas_height=canvas_height,
    )}


# Positioniert eine global berechnete Node innerhalb eines Gruppenrahmens.
def _style_for_node_in_frame(
    node: TopologyNode,
    *,
    frame_left: float,
    frame_top: float,
    frame_width: float,
    frame_height: float,
    canvas_height: float,
) -> dict[str, str]:
    style = topology_html_node_style(node, canvas_height=canvas_height)
    width = node.width or node.radius * 2
    height = node.height or node.radius * 2
    style.update({
        "left": f"{(node.x * CANVAS_WIDTH - frame_left) / frame_width * 100:.3f}%",
        "top": f"{(node.y * canvas_height - frame_top) / frame_height * 100:.3f}%",
    })
    if node.shape == "pill":
        style.update({
            "width": f"{width / frame_width * 100:.3f}%",
            "height": f"{height / frame_height * 100:.3f}%",
        })
    return style


# Rendert eine auswählbare Komponente der Topologie.
def _node_button(
    node: TopologyNode, *, canvas_height: float = CANVAS_HEIGHT,
) -> html.Button:
    kind, code = "central", node.id
    if node.id == "GRID":
        kind, code = "grid", "GRID"
    elif node.id in {"AC_BUS", "DC_BUS"}:
        kind, code = "grid", node.id
    elif node.id in {"COOL_GRID", "HEAT_GRID"}:
        kind, code = "network", node.id
    elif node.id == "LOAD":
        kind, code = "load", "LOAD"
    elif node.id.startswith("BUILDING:"):
        kind, code = "building", node.id.split(":", 1)[1]
    elif (
        node.id in {resource[0] for resource in RESOURCE_FOR_DEVICE.values()}
        or node.id.split(":", 1)[0] in {
            "WASTE_IMPORT", "BIOMASS_IMPORT",
        }
    ):
        kind, code = "resource", node.id
    elif node.id in {"INVERTER"}:
        kind, code = "grid", node.id
    class_name, style = _node_presentation(
        node, canvas_height=canvas_height,
    )
    labels = node_label_variants(node)
    building_drag_attributes = (
        {
            "draggable": "true",
            "data-building-uid": str(code),
            "data-konfig-building-drop-target": "true",
        }
        if kind == "building" else {}
    )
    return html.Button(
        html.Span(labels.wrapped, className="topology-node-label"),
        id={"type": "konfig-node", "kind": kind, "code": str(code)},
        n_clicks=0,
        className=class_name,
        style=style,
        title=labels.full.replace("\n", " "),
        **{"data-konfig-anchor": f"{kind}:{code}"},
        **{
            "data-topology-label-full": labels.full,
            "data-topology-label-wrapped": labels.wrapped,
            "data-topology-label-short": labels.short,
        },
        **building_drag_attributes,
    )


# Gruppiert AC-Pille, DC-Pille und Inverter für ein gemeinsames Hover.
def _power_pill_group(
    nodes: dict[str, TopologyNode], *, canvas_height: float,
) -> html.Div:
    part_ids = [item for item in ("AC_BUS", "DC_BUS", "INVERTER") if item in nodes]
    parts = [nodes[item] for item in part_ids]
    left = min(
        node.x * CANVAS_WIDTH - (node.width or node.radius * 2) / 2
        for node in parts
    )
    right = max(
        node.x * CANVAS_WIDTH + (node.width or node.radius * 2) / 2
        for node in parts
    )
    top = min(
        node.y * canvas_height - (node.height or node.radius * 2) / 2
        for node in parts
    )
    bottom = max(
        node.y * canvas_height + (node.height or node.radius * 2) / 2
        for node in parts
    )
    width, height = right - left, bottom - top
    children = []
    label_ys = _power_pill_label_ys(
        nodes, canvas_height=canvas_height,
    )
    for node in parts:
        button = _node_button(node, canvas_height=canvas_height)
        button.style = {
            **button.style,
            **_style_for_node_in_frame(
                node,
                frame_left=left,
                frame_top=top,
                frame_width=width,
                frame_height=height,
                canvas_height=canvas_height,
            ),
        }
        if node.id in label_ys:


            node_height = node.height or node.radius * 2
            node_top = node.y * canvas_height - node_height / 2
            button.style["--konfig-label-y"] = (
                f"{(label_ys[node.id] * canvas_height - node_top) / node_height * 100:.3f}%"
            )
        children.append(button)
    return html.Div(
        id="konfig-current-power-pill",
        className="konfig-power-pill-group konfig-current-power-pill",
        style={
            "left": f"{left / CANVAS_WIDTH * 100:.3f}%",
            "top": f"{top / canvas_height * 100:.3f}%",
            "width": f"{width / CANVAS_WIDTH * 100:.3f}%",
            "height": f"{height / canvas_height * 100:.3f}%",
        },
        children=children,
    )


# Gruppiert jede zentrale Komponente mit ihrem Hover-Löschkreis.
def _component_groups(
    state: dict[str, Any],
    nodes: dict[str, TopologyNode],
    *,
    canvas_height: float,
    covered_area_classes: dict[str, list[str]] | None = None,
) -> list[html.Div]:
    result = []
    removable = [
        (str(code), "central") for code in state.get("central_devices") or []
    ]
    if state.get("grid_enabled") and "GRID" in nodes:
        removable.insert(0, ("GRID", "grid"))

    resource_ids = {
        RESOURCE_FOR_DEVICE[code][0]
        for code in state.get("central_devices") or []
        if code in RESOURCE_FOR_DEVICE
    }
    removable.extend(
        (resource_id, "resource")
        for resource_id in sorted(resource_ids)
        if resource_id in nodes
    )
    for code, kind in removable:
        node = nodes.get(code)
        if node is None or node.shape != "circle":
            continue
        component = _node_button(node, canvas_height=canvas_height)
        node_size = component.style["width"]
        component.style = {
            **component.style,
            "left": "50%",
            "top": "50%",


            "width": "100%",
            "height": "100%",
        }
        trash = action_button(
            "trash",
            {
                "type": "konfig-remove-node",
                "kind": kind,
                "code": code,
            },
            class_name="konfig-node-trash konfig-component-trash",
            style={
                "left": "85.355%",
                "top": "14.645%",
            },
            title=f"{node.title} entfernen",
        )
        result.append(html.Div(
            [component, trash],
            className=" ".join((
                "konfig-component-group",
                f"konfig-component-{code.lower()}",
                *(("konfig-component-resource",) if kind == "resource" else ()),
                *(covered_area_classes or {}).get(code, ()),
            )),
            style={
                "left": f"{node.x * 100:.3f}%",
                "top": f"{node.y * 100:.3f}%",
                "width": node_size,
                "height": node_size,


                "zIndex": str(node.z_index),
            },
        ))
    return result


# CSS-Markierungen für Nodes, die unter einem Glas-+-Bereich liegen.
def _covered_area_classes(
    node: TopologyNode,
    placeholders: dict[str, SlotPlaceholder],
    *,
    canvas_height: float,
) -> list[str]:
    if node.id in {"AC_BUS", "HEAT_GRID"}:
        return []

    node_width = node.width or 2 * node.radius
    node_height = node.height or 2 * node.radius
    node_left = node.x * CANVAS_WIDTH - node_width / 2
    node_right = node_left + node_width
    node_top = node.y * canvas_height - node_height / 2
    node_bottom = node_top + node_height
    classes = []
    for area_id in ("dc_area", "cool_area"):
        area = placeholders.get(area_id)
        if area is None:
            continue
        area_width = area.width or 2 * area.radius
        area_height = area.height or 2 * area.radius
        area_left = area.x - area_width / 2
        area_right = area_left + area_width
        area_top = area.y - area_height / 2
        area_bottom = area_top + area_height
        if not (
            node_right <= area_left or area_right <= node_left
            or node_bottom <= area_top or area_bottom <= node_top
        ):
            classes.append(f"konfig-covered-by-{area_id.replace('_', '-')}")
    return classes


# Rendert einen Platzhalter zum Hinzufügen einer Komponente.
def _slot_button(slot: str, point: tuple[float, float], *, compact: bool = False) -> html.Button:
    x, y = point
    return html.Button(
        "+",
        id={"type": "konfig-add-slot", "slot": slot},
        n_clicks=0,
        className=(
            "konfig-add-slot konfig-add-slot-small"
            if compact else "konfig-add-slot"
        ),
        style={"left": f"{x / CANVAS_WIDTH * 100:.3f}%", "top": f"{y / CANVAS_HEIGHT * 100:.3f}%"},
        title=_slot_add_label(slot),
        **{"data-konfig-add-label": _slot_add_label(slot)},
    )


# Liefert die kontextgerechte, umgebrochene Kandidatenbeschriftung.
def _candidate_label(code: str, *, decentral: bool = False) -> str:
    return candidate_label_variants(
        code, decentral=decentral,
    ).wrapped


# Baut den Beschriftungsinhalt einer angebotenen Komponente.
def _candidate_label_content(
    code: str, *, decentral: bool = False,
) -> html.Span:
    return html.Span(
        _candidate_label(code, decentral=decentral),
        className="topology-node-label",
    )


# Bestimmt die Darstellungsattribute einer Kandidatenbeschriftung.
def _candidate_label_attributes(
    code: str, *, decentral: bool = False,
) -> dict[str, str]:
    labels = candidate_label_variants(
        code, decentral=decentral,
    )
    return {
        "data-topology-label-full": labels.full,
        "data-topology-label-wrapped": labels.wrapped,
        "data-topology-label-short": labels.short,
    }


# Baut Darstellungs- und Abhängigkeitsklassen eines Kandidaten.
def _candidate_classes(slot: str, code: str, *, single: bool = False) -> str:
    classes = [
        "topology-node-surface",
        "topology-scene-node",
        "konfig-candidate",
    ]
    if single:
        classes.append("konfig-single-candidate")
    if "dc" in CENTRAL_DEVICES.get(code, {}).get("inputs", ()):
        classes.append("konfig-candidate-requires-dc")
    if "cool" in CENTRAL_DEVICES.get(code, {}).get("outputs", ()):
        classes.append("konfig-candidate-enables-cooling")
    if code == "AC":
        classes.append("konfig-candidate-extends-heat")
    return " ".join(classes)


# Leitet die HTML-Darstellung aus der kanonischen Node-Geometrie ab.
def _node_presentation(
    node: TopologyNode, *, canvas_height: float,
) -> tuple[str, dict[str, str]]:
    classes = [
        "topology-node-surface",
        "topology-scene-node",
        "konfig-node",
        f"konfig-node-{node.shape}",
    ]
    if node.id in {"LOAD", "AC_BUS", "DC_BUS", "COOL_GRID", "HEAT_GRID"}:
        classes.append("konfig-node-pill")
    if node.id == "LOAD":
        classes.append("konfig-load-pill")
    elif node.id == "HEAT_GRID":
        classes.append("konfig-heat-pill")
    if node.id in {"AC_BUS", "DC_BUS", "INVERTER"}:
        classes.append("konfig-power-pill-part")
    if node.id == "AC_BUS":
        classes.append("konfig-ac-pill")
    elif node.id == "DC_BUS":
        classes.append("konfig-dc-pill")
    elif node.id == "INVERTER":
        classes.append("konfig-inverter-node")
    style = topology_html_node_style(node, canvas_height=canvas_height)
    if node.id == "AC_BUS":
        full_height = node.height or node.radius * 2
        visible_height = min(full_height, node.radius * 2)
        style["--konfig-label-y"] = f"{visible_height / 2 / full_height * 100:.3f}%"
    elif node.id == "DC_BUS":
        full_height = node.height or node.radius * 2
        style["--konfig-label-y"] = (
            f"{(node.radius * 2 + (full_height - node.radius * 2) / 2) / full_height * 100:.3f}%"
        )
    return " ".join(classes), style


# Rendert die nächste freie Position, optional mit Einzelvorschau.
def _slot_placeholder(
    placeholder: SlotPlaceholder,
    *,
    canvas_height: float = CANVAS_HEIGHT,
    single_candidate: str | None = None,
    expanded: bool = False,
    hide_origin_when_expanded: bool = False,
    label: str = "+",
) -> Any:
    diameter = placeholder.radius * 2
    color = COLORS.get(placeholder.carrier, COLORS["neutral"])
    classes = ["konfig-slot-placeholder"]
    if expanded and hide_origin_when_expanded:
        classes.append("is-candidate-menu-open")
    if placeholder.shape == "building":
        classes.append("konfig-building-placeholder")
    if label != "+":
        classes.append("konfig-slot-placeholder-hint")
    base_style = {
        "left": f"{placeholder.x / CANVAS_WIDTH * 100:.3f}%",
        "top": f"{placeholder.y / canvas_height * 100:.3f}%",
        **_responsive_square_style(diameter, diameter, canvas_height=canvas_height),
        "--node-color": color,
        "zIndex": "4",
    }
    button = html.Button(
        label,
        id={"type": "konfig-add-slot", "slot": placeholder.slot},
        n_clicks=0,
        className=" ".join(classes),
        style=base_style,
        title=_slot_add_label(placeholder.slot),
        **(
            {"data-konfig-add-label": _slot_add_label(placeholder.slot)}
            if label == "+" else {}
        ),
    )
    if not single_candidate:
        return button

    wrapper_style = {
        key: base_style[key]
        for key in ("left", "top", "width", "height", "--node-color")
    }
    child_style = {
        "left": "50%", "top": "50%", "width": "100%", "height": "100%",
        "--node-color": color,
    }
    button.style = {**child_style, "zIndex": "4"}
    candidate_slot = str(
        CENTRAL_DEVICES.get(single_candidate, {}).get(
            "slot", placeholder.slot
        )
    )
    candidate = html.Button(
        _candidate_label_content(single_candidate),
        id={
            "type": "konfig-candidate",
            "slot": candidate_slot,
            "code": single_candidate,
        },
        n_clicks=0,
        className=_candidate_classes(
            candidate_slot, single_candidate, single=True
        ),
        style={**child_style, "zIndex": "30"},
        title=f"{_candidate_label(single_candidate)} mit Klick übernehmen",
        **_candidate_label_attributes(single_candidate),
    )
    return html.Div(
        [button, candidate],
        className=(
            "konfig-single-candidate-slot is-menu-open"
            if expanded else "konfig-single-candidate-slot"
        ),
        style=wrapper_style,
    )


# Ersetzt auch innerhalb einer grossen Bereichsvorschau den Plus-Node.
def _embedded_single_candidate_slot(
    slot: str,
    code: str,
    color: str,
    wrapper_style: dict[str, str],
    *,
    extra_class: str,
    trigger_slot: str | None = None,
    expanded: bool = False,
) -> html.Div:
    wrapper_style = dict(wrapper_style)
    add_slot = trigger_slot or slot
    child_style = {
        "left": "50%", "top": "50%", "width": "100%", "height": "100%",
        "--node-color": color,
    }
    plus = html.Button(
        "+",
        id={"type": "konfig-add-slot", "slot": add_slot},
        n_clicks=0,
        className=f"konfig-slot-placeholder {extra_class}",
        style={**child_style, "zIndex": "4"},
        title=_slot_add_label(add_slot),
        **{"data-konfig-add-label": _slot_add_label(add_slot)},
    )
    candidate = html.Button(
        _candidate_label_content(code),
        id={"type": "konfig-candidate", "slot": slot, "code": code},
        n_clicks=0,
        className=_candidate_classes(slot, code, single=True),
        style={**child_style, "zIndex": "30"},
        title=f"{_candidate_label(code)} mit Klick übernehmen",
        **_candidate_label_attributes(code),
    )
    return html.Div(
        [plus, candidate],
        className=(
            "konfig-single-candidate-slot konfig-embedded-single-slot is-menu-open"
            if expanded
            else "konfig-single-candidate-slot konfig-embedded-single-slot"
        ),
        style=wrapper_style,
    )


# Gemeinsamer Rahmen für DC-, Kälte- und weitere-Bereichsfelder.
def _carrier_area_slot(
    area_key: str,
    area: SlotPlaceholder,
    actions: html.Div,
    *,
    canvas_height: float,
    expanded: bool = False,
) -> html.Div:
    spec = AREA_SLOT_SPECS[area_key]
    width = area.width or 2 * area.radius
    height = area.height or 2 * area.radius
    classes = [
        "konfig-area-slot",
        "konfig-carrier-area-slot",
        str(spec["class_name"]),
    ]
    if expanded:
        classes.append("is-menu-open")
    return html.Div(
        className=" ".join(classes),
        style={
            "left": f"{area.x / CANVAS_WIDTH * 100:.3f}%",
            "top": f"{area.y / canvas_height * 100:.3f}%",
            "width": f"{width / CANVAS_WIDTH * 100:.3f}%",
            "height": f"{height / canvas_height * 100:.3f}%",
            **_rounded_radius_style(
                width, height, area.radius, canvas_height=canvas_height,
            ),
        },
        title=_slot_add_label(area_key),
        children=[
            html.Button(
                "",
                id={"type": "konfig-menu-dismiss", "scope": area_key},
                n_clicks=0,
                className="konfig-menu-dismiss",
                tabIndex=-1,
            ),
            html.Span("+", className="konfig-area-plus"),
            html.Span(str(spec["title"]), className="konfig-area-title"),
            actions,
        ],
    )


# Positioniert einen regulären Slot relativ zu seinem UI-Overlay.
def _area_control_style(
    area: SlotPlaceholder,
    control: SlotPlaceholder,
    *,
    canvas_height: float,
) -> dict[str, str]:
    area_width = area.width or 2 * area.radius
    area_height = area.height or 2 * area.radius
    left = area.x - area_width / 2
    top = area.y - area_height / 2
    diameter = 2 * control.radius
    return {
        "left": f"{(control.x - left) / area_width * 100:.3f}%",
        "top": f"{(control.y - top) / area_height * 100:.3f}%",
        "width": f"{diameter / area_width * 100:.3f}%",
        "height": f"{diameter / area_height * 100:.3f}%",
        "zIndex": "4",
        **_responsive_square_style(
            diameter, diameter, canvas_height=canvas_height,
        ),
    }


# Rendert ein reines Konfigurator-Overlay über zwei regulären Slots.
def _inactive_carrier_area_slot(
    area_key: str,
    area: SlotPlaceholder,
    source: SlotPlaceholder,
    storage: SlotPlaceholder,
    *,
    storage_code: str,
    canvas_height: float,
    menu_slot: str = "",
) -> html.Div:
    source_style = _area_control_style(
        area, source, canvas_height=canvas_height,
    )
    storage_style = _area_control_style(
        area, storage, canvas_height=canvas_height,
    )
    color = COLORS.get(source.carrier, COLORS["neutral"])
    actions = html.Div(
        className="konfig-area-actions konfig-carrier-controls",
        children=[
            html.Button(
                "+",
                id={"type": "konfig-add-slot", "slot": source.slot},
                n_clicks=0,
                className="konfig-slot-placeholder konfig-area-control-slot",
                style={**source_style, "--node-color": color},
                title=_slot_add_label(source.slot),
                **{"data-konfig-add-label": _slot_add_label(source.slot)},
            ),
            _embedded_single_candidate_slot(
                storage.slot,
                storage_code,
                COLORS.get(storage.carrier, COLORS["neutral"]),
                storage_style,
                extra_class="konfig-area-control-slot",
                expanded=menu_slot == storage.slot,
            ),
        ],
    )
    return _carrier_area_slot(
        area_key,
        area,
        actions,
        canvas_height=canvas_height,
        expanded=menu_slot in AREA_SLOT_SPECS[area_key]["trigger_slots"],
    )


# Rendert den kanonisch geplanten Bereich der H₂-/Gas-Bedienplätze.
def _other_area_slot(
    area: SlotPlaceholder,
    component_placeholders: dict[str, SlotPlaceholder],
    *,
    canvas_height: float,
    menu_slot: str = "",
) -> html.Div | None:
    placeholders = list(component_placeholders.values())
    if not placeholders:
        return None

    diameter_by_slot = {
        placeholder.slot: 2 * placeholder.radius
        for placeholder in placeholders
    }
    width = area.width or 2 * area.radius
    height = area.height or 2 * area.radius
    left = area.x - width / 2
    top = area.y - height / 2

    def local_style(placeholder: SlotPlaceholder) -> dict[str, str]:
        diameter = diameter_by_slot[placeholder.slot]
        return {
            "left": f"{(placeholder.x - left) / width * 100:.3f}%",
            "top": f"{(placeholder.y - top) / height * 100:.3f}%",
            "width": f"{diameter / width * 100:.3f}%",
            "height": f"{diameter / height * 100:.3f}%",
            "zIndex": "4",
            **_responsive_square_style(
                diameter, diameter, canvas_height=canvas_height,
            ),
        }

    actions = html.Div(
        className="konfig-area-actions konfig-carrier-controls konfig-other-controls",
        children=[
            _embedded_single_candidate_slot(
                str(CENTRAL_DEVICES[code]["slot"]),
                code,
                COLORS.get(placeholder.carrier, COLORS["neutral"]),
                local_style(placeholder),
                extra_class="konfig-other-control-slot",
                trigger_slot=control_id,
                expanded=menu_slot == control_id,
            )
            for control_id, placeholder in component_placeholders.items()
            for code in [INDIVIDUAL_COMPONENT_CONTROLS[control_id]]
        ],
    )
    spec = AREA_SLOT_SPECS["other_area"]
    return _carrier_area_slot(
        "other_area",
        area,
        actions,
        canvas_height=canvas_height,
        expanded=menu_slot in spec["trigger_slots"],
    )


# Ordnet die angebotenen Komponenten um den gewählten Platzhalter an.
def _candidate_ring(
    menu: dict[str, Any] | None,
    state: dict[str, Any],
    buildings: list[dict[str, Any]],
    placeholders: dict[str, SlotPlaceholder],
    *,
    canvas_height: float = CANVAS_HEIGHT,
) -> list[html.Button]:
    if not menu:
        return []
    slot = str(menu.get("slot") or "")
    building_carrier = (
        slot.rsplit(":", 1)[-1] if slot.startswith("building:") else ""
    )
    is_building_candidate = bool(building_carrier)
    origin = menu.get("origin")
    placeholder = placeholders.get(slot)
    if origin and isinstance(origin, (list, tuple)) and len(origin) == 2:
        center = (float(origin[0]), float(origin[1]))

        origin_radius = BUILDING_NODE_RADIUS if is_building_candidate else 14.0
        carrier = building_carrier or "neutral"
    else:
        center = (placeholder.x, placeholder.y) if placeholder else None
        origin_radius = placeholder.radius if placeholder else 55.0
        carrier = placeholder.carrier if placeholder else "neutral"
    if not center:
        return []

    if slot == "building":
        candidates = ["BUILDING"]
    elif slot.startswith("building:"):
        try:
            uid = int(slot.split(":", 2)[1])
        except (IndexError, ValueError):
            return []
        row = next(
            (item for item in buildings if int(item.get("uid", -1)) == uid),
            None,
        )
        candidates = list(building_available_candidates(
            row or {}, building_carrier,
        ))
    else:
        candidates = unused_candidates(
            slot,
            list(state.get("central_devices") or []),
            bool(state.get("grid_enabled")),
        )
    if not candidates:
        return []

    count = len(candidates)


    candidate_radius = (
        BUILDING_BADGE_RADIUS
        if is_building_candidate and count == 1
        else CANDIDATE_RADIUS
    )
    if count == 1:
        angles = (0.0,)

        radius_x = radius_y = 0.0
    elif count == 2:
        angles = (math.pi, 0.0)
        radius_x = radius_y = origin_radius + candidate_radius
    elif count == 3:
        angles = (-math.pi / 2, 5 * math.pi / 6, math.pi / 6)
        radius_x = radius_y = origin_radius + candidate_radius
    else:
        angles = tuple(-math.pi / 2 + 2 * math.pi * index / count for index in range(count))
        radius_x = radius_y = origin_radius + candidate_radius
    offsets = tuple(
        (math.cos(angle) * radius_x, math.sin(angle) * radius_y)
        for angle in angles
    )
    candidate_center = place_candidate_group(
        center,
        anchor_radius=origin_radius,
        group_origin_radius=origin_radius,
        candidate_offsets=offsets,
        candidate_radius=candidate_radius,
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
    )
    candidate_positions = tuple(
        (candidate_center[0] + offset_x, candidate_center[1] + offset_y)
        for offset_x, offset_y in offsets
    )
    candidate_z_indices = _candidate_z_indices(
        candidate_positions
    )


    result = []
    for index, code in enumerate(candidates):
        angle = angles[index]
        x, y = candidate_positions[index]
        label = _candidate_label(code, decentral=is_building_candidate)
        candidate_carrier = str(
            CENTRAL_DEVICES.get(code, {}).get("primary_carrier") or carrier
        )
        candidate_display_radius = (
            candidate_radius
            if is_building_candidate else origin_radius
        )
        result.append(
            html.Button(
                _candidate_label_content(
                    code, decentral=is_building_candidate,
                ),
                id={"type": "konfig-candidate", "slot": slot, "code": code},
                n_clicks=0,
                className=(
                    _candidate_classes(slot, code, single=count == 1)
                    + (
                        " konfig-building-candidate"
                        + (
                            " konfig-building-ring-candidate"
                            if count > 1 else ""
                        )
                        if is_building_candidate else ""
                    )
                ),
                style={
                    "left": f"{x / CANVAS_WIDTH * 100:.3f}%",
                    "top": f"{y / canvas_height * 100:.3f}%",
                    **_responsive_square_style(
                        2 * (candidate_display_radius if count == 1 else candidate_radius),
                        2 * (candidate_display_radius if count == 1 else candidate_radius),
                        canvas_height=canvas_height,
                    ),
                    "--node-color": COLORS.get(
                        candidate_carrier, COLORS["neutral"]
                    ),
                    "zIndex": str(candidate_z_indices[index]),
                },
                title=f"{label} mit Klick übernehmen",
                **_candidate_label_attributes(
                    code, decentral=is_building_candidate,
                ),
            )
        )
    if count > 1:
        result.append(html.Span(
            "+",
            className="konfig-candidate-menu-origin",
            style={
                "left": f"{candidate_center[0] / CANVAS_WIDTH * 100:.3f}%",
                "top": f"{candidate_center[1] / canvas_height * 100:.3f}%",
                **_responsive_square_style(
                    2 * origin_radius,
                    2 * origin_radius,
                    canvas_height=canvas_height,
                ),
                "--node-color": COLORS.get(carrier, COLORS["neutral"]),
                "zIndex": "30",
            },
        ))
    return result


# Liefert einen Kreisring-Versatz in Bildschirmkoordinaten.
def _ring_point(angle: float, radius: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return math.cos(radians) * radius, math.sin(radians) * radius


# Plant einen gemeinsamen gleichmäßigen Hoverring samt Aktionen.
#
# Trash und Copy belegen benachbarte Plätze, deren Mitte exakt rechts vom
# Gebäude liegt. Die übrigen Badges bleiben in ihrer zyklischen Reihenfolge
# und werden mit minimalem Gesamtweg auf die freien Plätze abgebildet.
def _building_hover_layout(
    item_count: int | tuple[float, ...],
) -> tuple[tuple[float, ...], float, float]:
    base_angles = (
        tuple(
            -90.0 + 360.0 * index / item_count
            for index in range(item_count)
        )
        if isinstance(item_count, int)
        else tuple(item_count)
    )
    count = len(base_angles)
    step = 360.0 / (count + 2)
    trash_angle = -step / 2.0
    duplicate_angle = step / 2.0
    if count == 0:
        return (), trash_angle, duplicate_angle
    available_angles = tuple(
        duplicate_angle + step * (index + 1)
        for index in range(count)
    )

    def circular_distance(first: float, second: float) -> float:
        return abs((first - second + 180.0) % 360.0 - 180.0)

    shift = min(
        range(count),
        key=lambda candidate_shift: sum(
            circular_distance(
                base_angles[index],
                available_angles[(index + candidate_shift) % count],
            )
            for index in range(count)
        ),
    )
    item_angles = tuple(
        available_angles[(index + shift) % count]
        for index in range(count)
    )
    return item_angles, trash_angle, duplicate_angle


# Rendert einen freien Gebäudeslot mit genau einer direkt auswählbaren Komponente.
def _single_building_candidate(candidates, common, carrier_color, uid, slot, carrier):
    code = candidates[0]
    badge_style = {
        **common["style"],
        "left": "50%", "top": "50%",
    }
    candidate_style = {
        "left": "50%", "top": "50%",
        "--node-color": carrier_color,
        "--building-carrier-color": carrier_color,
    }
    plus = html.Button(
        "+",
        id={
            "type": "konfig-building-slot",
            "uid": uid,
            "slot": slot,
            "value": "",
        },
        n_clicks=0,
        className=common["className"],
        style=badge_style,
        title=common["title"],
    )
    candidate = html.Button(
        _candidate_label_content(code, decentral=True),
        id={
            "type": "konfig-candidate",
            "slot": f"building:{uid}:{carrier}",
            "code": code,
        },
        n_clicks=0,
        className=(
            _candidate_classes(
                f"building:{uid}:{carrier}", code, single=True,
            )
            + " konfig-building-candidate"
        ),
        style=candidate_style,
        title=(
            f"{_candidate_label(code, decentral=True)} mit Klick übernehmen"
        ),
        **_candidate_label_attributes(code, decentral=True),
    )
    badge = html.Div(
        [plus, candidate],
        className=(
            "konfig-single-candidate-slot "
            "konfig-single-building-candidate"
        ),
        style={
            **common["style"],
            "width": "var(--topology-building-badge-size)",
            "height": "var(--topology-building-badge-size)",
        },
    )
    return badge


# Rendert ein Ringelement als Komponente, freien Slot oder statische Beschriftung.
def _building_ring_badge(
    placement: BuildingRingPlacement, hover_angle: float, *,
    building: TopologyNode, frame_radius: float, frame_size: float,
    interactive: bool, menu_slot: str, uid: int, row: dict[str, Any],
    badge_radius: float, canvas_height: float,
) -> Any:
    slot, value, carrier = (
        placement.key, placement.code, placement.carrier
    )
    base_x, base_y = placement.x, placement.y
    hover_x, hover_y = _ring_point(hover_angle, building.radius)
    carrier_color = COLORS.get(carrier, COLORS["neutral"])
    is_open_multi_candidate_slot = (
        interactive
        and not value
        and menu_slot == f"building:{uid}:{slot}"
        and len(building_available_candidates(row, carrier)) > 1
    )
    common = dict(
        className=(
            "konfig-building-badge is-set"
            if value else "konfig-building-badge"
        ) + (
            " is-candidate-menu-open"
            if is_open_multi_candidate_slot else ""
        ),
        style={
            "left": f"{(frame_radius + base_x) / frame_size * 100:.3f}%",
            "top": f"{(frame_radius + base_y) / frame_size * 100:.3f}%",
            "--konfig-hover-left": f"{(frame_radius + hover_x) / frame_size * 100:.3f}%",
            "--konfig-hover-top": f"{(frame_radius + hover_y) / frame_size * 100:.3f}%",
            "--building-carrier-color": carrier_color,
            "--topology-building-badge-size": topology_responsive_square_size(
                2 * badge_radius,
                2 * badge_radius,
                canvas_height=canvas_height,
            ),
        },
        title=(
            f"Dezentrale Komponente: {decentral_device_abbreviation(value)}"
            if value
            else f"{CARRIER_LABELS.get(carrier, carrier.capitalize())}-Komponente hinzufügen"
        ),
    )

    if interactive:
        candidates = (
            building_available_candidates(row, carrier)
            if not value else ()
        )
        if len(candidates) == 1:
            badge = _single_building_candidate(candidates, common, carrier_color, uid, slot, carrier)
        else:
            badge = html.Button(
                decentral_device_abbreviation(value) if value else "+",
                id={
                    "type": "konfig-building-slot",
                    "uid": uid,
                    "slot": slot,
                    "value": value or "",
                },
                n_clicks=0,
                **({"data-konfig-anchor": f"decentral:{uid}:{slot}:{value}"} if value else {}),
                **common,
            )
    else:
        badge = html.Div(
            decentral_device_abbreviation(value) if value else "+",
            **common,
        )
    return badge


# Rendert die Aktionen zum Duplizieren und Entfernen eines Gebäudes.
def _building_actions(
    uid, building, frame_radius, frame_size, action_size,
    duplicate_angle, trash_angle, interactive,
) -> list[Any]:
    actions = []
    if interactive:
        duplicate_x, duplicate_y = _ring_point(
            duplicate_angle, building.radius,
        )
        actions.append(action_button(
            "duplicate",
            {"type": "konfig-duplicate-building", "uid": uid},
            class_name="konfig-node-action konfig-building-duplicate",
            style={
                "left": f"{(frame_radius + duplicate_x) / frame_size * 100:.3f}%",
                "top": f"{(frame_radius + duplicate_y) / frame_size * 100:.3f}%",
                "--topology-building-badge-size": action_size,
            },
            title="Gebäude duplizieren",
        ))
        trash_x, trash_y = _ring_point(trash_angle, building.radius)
        actions.append(action_button(
            "trash",
            {"type": "konfig-remove-node", "kind": "building", "code": str(uid)},
            class_name="konfig-node-action konfig-node-trash konfig-building-trash",
            style={
                "left": f"{(frame_radius + trash_x) / frame_size * 100:.3f}%",
                "top": f"{(frame_radius + trash_y) / frame_size * 100:.3f}%",
                "--topology-building-badge-size": action_size,
            },
            title="Gebäude entfernen",
        ))
    return actions


# Baut die Hülle eines Gebäudes aus Mittelpunkt, Ringelementen und Aktionen.
def _building_group(
    row, uid, building, ring_placements, canvas_height,
    standard_diameter, interactive, menu_slot,
) -> html.Div:
    badge_radius = topology_node_radius(
        "badge",
        standard_diameter or min(
            building.cell_width or 2 * building.radius,
            building.cell_height or 2 * building.radius,
        ),
    )
    frame_radius = building.radius + badge_radius
    frame_size = 2 * frame_radius
    building_control = _node_button(
        building, canvas_height=canvas_height
    )
    building_control.style = {
        **building_control.style,
        "left": "50%", "top": "50%",
        "width": f"{2 * building.radius / frame_size * 100:.3f}%",
        "height": f"{2 * building.radius / frame_size * 100:.3f}%",
    }
    children: list[Any] = [building_control]
    placements = (ring_placements or {}).get(uid)
    if placements is None:
        placements = building_ring_placements(
            row,
            radius=building.radius,
            include_available=interactive,
        )

    hover_angles, trash_angle, duplicate_angle = _building_hover_layout(
        tuple(item.angle for item in placements),
    )
    action_size = topology_responsive_square_size(
        2 * badge_radius,
        2 * badge_radius,
        canvas_height=canvas_height,
    )
    for item_index, placement in enumerate(placements):
        badge = _building_ring_badge(
            placement, hover_angles[item_index],
            building=building, frame_radius=frame_radius, frame_size=frame_size,
            interactive=interactive, menu_slot=menu_slot, uid=uid, row=row,
            badge_radius=badge_radius, canvas_height=canvas_height,
        )
        children.append(badge)
    children.extend(_building_actions(
        uid, building, frame_radius, frame_size, action_size,
        duplicate_angle, trash_angle, interactive,
    ))
    return html.Div(
        children,
        className=(
            "konfig-building-group"
            + (" konfig-static-building-group" if not interactive else "")
            + (
                " is-menu-open"
                if menu_slot.startswith(f"building:{uid}:") else ""
            )
        ),
        style={
            "left": f"{building.x * 100:.3f}%",
            "top": f"{building.y * 100:.3f}%",
            **_responsive_square_style(
                frame_size, frame_size, canvas_height=canvas_height,
            ),
        },
    )


# Rendert Gebäudeanschlüsse und dezentrale Komponenten als einen Ring.
#
# Freie Energieträger und bereits gewählte Komponenten sind gleichwertige
# Ringelemente. Beim Hover kommen Copy und Papierkorb als weitere Elemente
# hinzu. Die neue Verteilung wird dabei so gedreht, dass die vorhandenen
# Kreise in Summe den kürzesten Weg zurücklegen.
def _building_groups(
    buildings: list[dict[str, Any]],
    nodes: dict[str, TopologyNode],
    *,
    ring_placements: dict[
        int, tuple[BuildingRingPlacement, ...]
    ] | None = None,
    canvas_height: float = CANVAS_HEIGHT,
    standard_diameter: float | None = None,
    interactive: bool = True,
    menu_slot: str = "",
) -> list[html.Div]:
    result: list[html.Div] = []
    for index, row in enumerate(buildings):
        uid = int(row.get("uid", index))
        building = nodes.get(f"BUILDING:{uid}")
        if building is None:
            continue
        result.append(_building_group(
            row, uid, building, ring_placements, canvas_height,
            standard_diameter, interactive, menu_slot,
        ))
    return result


# Rendert vorhandene Knoten, Gebäude und Komponentengruppen.
def _graph_controls(
    state, nodes, canvas_height, cover_if_needed, buildings, central_scene, pixel, menu_slot, covered_area_classes,
):
    power_ids = {"AC_BUS", "DC_BUS", "INVERTER"}
    central_ids = set(state.get("central_devices") or [])
    # Nur Quellen mit tatsächlich gewählten abhängigen Geräten werden weiter
    # unten als löschbare Komponentengruppe gerendert. Ein von einem anderen
    # Gasgerät erzeugter GAS_IMPORT-Knoten darf hier nicht pauschal
    # herausgefiltert werden, sonst bleibt seine Eintrittskante ohne Node.
    grouped_resource_ids = {
        RESOURCE_FOR_DEVICE[code][0]
        for code in central_ids
        if code in RESOURCE_FOR_DEVICE
    }
    graph_controls: list[Any] = []
    for node in nodes.values():
        if node.shape == "badge":
            # Aktive Badge-Geometrie wird innerhalb der interaktiven
            # Gebäudegruppe aus demselben kanonischen Ringplan ausgegeben.
            continue
        if node.id.startswith("BUILDING_GROUP:"):
            class_name, style = _node_presentation(
                node, canvas_height=canvas_height
            )
            labels = node_label_variants(node)
            graph_controls.append(cover_if_needed(
                html.Div(
                    html.Span(labels.wrapped, className="topology-node-label"),
                    className=f"{class_name} konfig-building-summary",
                    style=style,
                    title=labels.full,
                    **{
                        "data-topology-label-full": labels.full,
                        "data-topology-label-wrapped": labels.wrapped,
                        "data-topology-label-short": labels.short,
                    },
                ),
                node.id,
            ))
            continue
        if (
            node.id in power_ids
            or node.id in central_ids
            or node.id == "GRID"
            or node.id in grouped_resource_ids
            or node.id.startswith("BUILDING:")
        ):
            continue
        button = _node_button(node, canvas_height=canvas_height)
        graph_controls.append(cover_if_needed(button, node.id))
    graph_controls.append(cover_if_needed(
        _power_pill_group(nodes, canvas_height=canvas_height),
        *(node_id for node_id in power_ids if node_id in nodes),
    ))
    graph_controls.extend(_building_groups(
        buildings, nodes,
        ring_placements=central_scene.building_rings,
        canvas_height=canvas_height,
        standard_diameter=pixel.node_diameter,
        menu_slot=menu_slot,
    ))
    graph_controls.extend(_component_groups(
        state, nodes, canvas_height=canvas_height,
        covered_area_classes=covered_area_classes,
    ))

    return graph_controls


# Rendert freie Geräteslots und die zugehörigen Hoverbereiche.
def _placeholder_controls(state, placeholders, canvas_height, menu_slot):
    controls: list[Any] = []

    for slot, placeholder in placeholders.items():
        if slot == "dc_area":
            controls.append(
                _inactive_carrier_area_slot(
                    "dc_area",
                    placeholder,
                    placeholders["dc_source"],
                    placeholders["dc_storage"],
                    storage_code="BAT",
                    canvas_height=canvas_height,
                    menu_slot=menu_slot,
                )
            )
        elif "dc_area" in placeholders and slot in {"dc_source", "dc_storage"}:
            # Diese beiden Slots werden innerhalb der großen DC-Hoverfläche
            # gerendert, bleiben aber als globale Kandidaten-Ursprünge erhalten.
            continue
        elif "cool_area" in placeholders and slot in {
            "cool_source", "cool_storage"
        }:
            # Future cooling nodes are rendered inside the large area.
            continue
        elif slot == "cool_area":
            controls.append(
                _inactive_carrier_area_slot(
                    "cool_area",
                    placeholder,
                    placeholders["cool_source"],
                    placeholders["cool_storage"],
                    storage_code="CTES",
                    canvas_height=canvas_height,
                    menu_slot=menu_slot,
                )
            )
        elif slot == "other_area":
            other_area = _other_area_slot(
                placeholder,
                {
                    control_id: placeholders[control_id]
                    for control_id in INDIVIDUAL_COMPONENT_CONTROLS
                    if control_id in placeholders
                },
                canvas_height=canvas_height,
                menu_slot=menu_slot,
            )
            if other_area is not None:
                controls.append(other_area)
        elif (
            "other_area" in placeholders
            and slot in INDIVIDUAL_COMPONENT_CONTROLS
        ):
            # Die kanonischen Bedienplätze werden innerhalb ihres ebenfalls
            # kanonischen Bereichs gerendert.
            continue
        elif slot in INDIVIDUAL_COMPONENT_CONTROLS:
            controls.append(
                _slot_placeholder(
                    placeholder,
                    canvas_height=canvas_height,
                    single_candidate=INDIVIDUAL_COMPONENT_CONTROLS[slot],
                    expanded=menu_slot == slot,
                )
            )
        else:
            candidates = (
                ["BUILDING"] if slot == "building" else
                unused_candidates(
                    slot,
                    list(state.get("central_devices") or []),
                    bool(state.get("grid_enabled")),
                )
            )
            controls.append(
                _slot_placeholder(
                    placeholder,
                    canvas_height=canvas_height,
                    single_candidate=(
                        candidates[0] if len(candidates) == 1 else None
                    ),
                    expanded=menu_slot == slot,
                    hide_origin_when_expanded=(
                        menu_slot == slot and len(candidates) > 1
                    ),
                )
            )

    return controls


# Zeigt die aktuelle Auswahl mit der platzhalterfreien Geometrie der Ergebnisansicht.
# Die Vorschau enthält keine Ergebniswerte und keine Aktionen zum Bearbeiten.
def _static_topology_preview(state, buildings):
    scene = build_topology_scene(
        state, buildings, include_editing_placeholders=False,
        center_parallel_ports=True,
    )
    plan = build_topology_render_plan(
        scene, presentation="system", instance_id="configurator-static-preview",
    )
    return html.Div([
        html.H2("Statische Topologievorschau", className="dashboard-title dev-topology-preview-label"),
        render_topology_scene(plan, root_classes=("dev-topology-static-scene",)),
    ], className="konfig-topology-canvas dev-topology-static-preview")


# Rendert den aktuellen Graphen mit addierbaren und gesetzten Nodes.
def render_configurator_topology(
    state: dict[str, Any],
    building_state: dict[str, Any] | None,
    *,
    dimmed: bool = False,
    static_preview: bool = False,
) -> html.Div:
    buildings = list((building_state or {}).get("rows") or [])
    if static_preview:
        return _static_topology_preview(state, buildings)
    central_scene = build_topology_scene(
        state,
        buildings,
        center_parallel_ports=True,
    )
    pixel = central_scene.geometry
    canvas_height = pixel.canvas_height
    nodes = central_scene.topology.nodes
    render_plan = build_topology_render_plan(
        central_scene,
        presentation="configurator",
        instance_id="configurator-main",
    )
    placeholders = central_scene.placeholders
    covered_area_classes = {
        node_id: _covered_area_classes(
            node, placeholders, canvas_height=canvas_height,
        )
        for node_id, node in nodes.items()
    }

    def cover_if_needed(component: Any, *node_ids: str) -> Any:
        classes = list(dict.fromkeys(
            class_name
            for node_id in node_ids
            for class_name in covered_area_classes.get(node_id, [])
        ))
        if not classes:
            return component
        return html.Div(
            component,
            className=" ".join(classes),
            style={"display": "contents"},
        )
    menu = dict(state.get("add_menu") or {})
    menu_slot = str(menu.get("slot") or "")
    graph_controls = _graph_controls(
        state, nodes, canvas_height, cover_if_needed, buildings, central_scene, pixel, menu_slot, covered_area_classes,
    )

    controls = _placeholder_controls(state, placeholders, canvas_height, menu_slot)

    if menu_slot.startswith("building:"):
        _prefix, uid_text, local_carrier = menu_slot.split(":", 2)
        building = nodes.get(f"BUILDING:{uid_text}")
        if building is not None:
            row = next(
                (item for item in buildings if int(item.get("uid", -1)) == int(uid_text)),
                {},
            )
            ring_placements = central_scene.building_rings.get(
                int(uid_text), ()
            )
            placement = next(
                (item for item in ring_placements if item.key == local_carrier),
                None,
            )
            if placement is not None:
                menu["origin"] = (
                    building.x * CANVAS_WIDTH + placement.x,
                    building.y * canvas_height + placement.y,
                )
    candidate_controls = (
        []
        if menu_slot in INDIVIDUAL_COMPONENT_CONTROLS
        else _candidate_ring(
            menu, state, buildings, placeholders, canvas_height=canvas_height
        )
    )
    canvas_classes = [
        "konfig-topology-canvas", "topology-renderer", "topology-visual-root",
    ]
    if dimmed or menu_slot:
        canvas_classes.extend([
            "is-configuration-desaturated", "is-topology-desaturated",
        ])

    grid_layer = topology_grid_component(pixel)
    grid_layer.className += " konfig-grid-overlay"
    edge_layer = topology_edge_host(render_plan)
    edge_layer.className += " konfig-edge-layer"
    scene_frame = topology_scene_frame(
        render_plan,
        children=[
            grid_layer,
            edge_layer,
            html.Div(
                className="konfig-current-scene topology-visual-layer",
                children=graph_controls,
            ),
            html.Div(className="konfig-live-controls", children=controls),
        ],
    )
    scene_frame.className += " konfig-topology-scene-frame"

    # Der Szenenrahmen erzeugt durch seine Zentrierungs-Transformation einen
    # eigenen Stapelkontext. Kandidaten innerhalb dieses Rahmens könnten daher
    # nicht über den außerhalb liegenden, flächigen Dismiss-Button hinausragen.
    # Ein deckungsgleicher Rahmen hält ihre Koordinaten unverändert, liegt aber
    # als Geschwisterelement zuverlässig über dem Dismiss-Layer.
    candidate_frame = topology_scene_frame(
        render_plan,
        children=candidate_controls,
    )
    candidate_frame.className += " konfig-candidate-layer"

    return html.Div(
        className=" ".join(canvas_classes),
        **{"data-create-token": state.get("create_token") or ""},
        children=[
            scene_frame,
            html.Button(
                "", id="konfig-remove-selected", n_clicks=0,
                style={"display": "none"}, tabIndex=-1,
            ),
            html.Button(
                "",
                id={"type": "konfig-menu-dismiss", "scope": "canvas"},
                n_clicks=0,
                className=(
                    "konfig-menu-dismiss konfig-canvas-dismiss is-active"
                    if menu_slot
                    else "konfig-menu-dismiss konfig-canvas-dismiss"
                ),
                tabIndex=-1,
            ),
            candidate_frame,
        ],
    )
