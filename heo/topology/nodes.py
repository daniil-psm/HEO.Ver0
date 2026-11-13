"""Baut die sichtbaren Knoten und Pillen aus der aufgelösten HEO-Rastergeometrie."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from heo.model.devices import TOPOLOGY_AUXILIARY_LABELS
from heo.topology.definitions import (
    CENTRAL_DEVICES, COLORS, NODE_DEFINITIONS,
    PILL_NODE_DEFINITIONS,
    RESOURCE_FOR_DEVICE, has_cooling_system, has_dc_system, ordered_slot_devices,
)
from heo.topology.geometry import CANVAS_HEIGHT, CANVAS_WIDTH
from heo.topology.labels import (
    NodeLabelVariants, _auxiliary_node_label, _building_node_label,
    _central_node_label, _node_label_variants, _wrapped_building_name,
    auxiliary_node_label_variants, central_node_label_variants,
)
from heo.topology.layout import PixelSceneGeometry, SlotPlaceholder, _pixel_scene_geometry
from heo.topology.model import TopologyNode
from heo.topology.sizing import topology_node_radius

def _node(
    node_id: str,
    label: str,
    x: float,
    y: float,
    carrier: str,
    *,
    shape: str = "circle",
    width: float | None = None,
    height: float | None = None,
    radius: float = 55.0,
    canvas_height: float = CANVAS_HEIGHT,
    z_index: int = 0,
    label_variants: NodeLabelVariants | None = None,
) -> TopologyNode:
    """Erzeugt eine Graph-Node aus Pixelposition und kanonischen Form-, Träger- und Labeldefinitionen."""

    # Kanonische Definitionen halten Form, Rolle und Beschriftung in allen Renderern gleich.
    definition = NODE_DEFINITIONS.get(node_id)
    if definition is None and node_id.startswith("BUILDING_GROUP:"):
        definition = NODE_DEFINITIONS["BUILDING_GROUP"]
    elif definition is None and node_id.startswith("BUILDING:"):
        definition = NODE_DEFINITIONS["BUILDING"]
    if definition is not None:
        carrier = definition.carrier
        shape = definition.shape
        if label_variants is None:
            if definition.label_kind == "central" and node_id in CENTRAL_DEVICES:
                label_variants = central_node_label_variants(node_id)
            elif (
                definition.label_kind == "auxiliary"
                and node_id in TOPOLOGY_AUXILIARY_LABELS
            ):
                label_variants = auxiliary_node_label_variants(node_id)
        if label_variants is not None:
            label = label_variants.wrapped
    group = {
        "power": "ac",
        "ac": "ac",
        "dc": "dc",
        "heat": "thermal",
        "cool": "cooling",
    }.get(carrier, "load")
    role = (
        definition.role if definition is not None else
        "bus" if shape == "pill" else "consumer" if shape == "building" else "source"
    )
    # Positionen werden normiert gespeichert; Radien und Ausdehnungen bleiben in Pixeln.
    return TopologyNode(
        id=node_id,
        title=label,
        icon="",
        x=x / CANVAS_WIDTH,
        y=y / canvas_height,
        radius=radius,
        group=group,
        role=role,
        color=COLORS.get(carrier, COLORS["neutral"]),
        shape=shape,
        width=width,
        height=height,
        z_index=z_index,
        label_full=label_variants.full if label_variants else label,
        label_wrapped=label_variants.wrapped if label_variants else label,
        label_short=label_variants.short if label_variants else label,
    )


def _pill(
    node_id: str,
    x: float,
    y: float,
    *,
    width: float,
    height: float,
    node_diameter: float,
    canvas_height: float = CANVAS_HEIGHT,
    z_index: int = 0,
) -> TopologyNode:
    """Erzeugt eine Raster-Pille aus ihrer zentralen semantischen Definition.

    Aufrufstellen geben ausschließlich Position und Ausdehnung an. Träger,
    Form, Rolle, Beschriftung und Endradius stammen aus den zentralen
    Definitionen.
    """

    if node_id not in PILL_NODE_DEFINITIONS:
        raise ValueError(f"{node_id!r} ist keine zentral definierte Pille")
    size_profile = PILL_NODE_DEFINITIONS[node_id].size_profile
    return _node(
        node_id,
        "",
        x,
        y,
        "neutral",
        width=width,
        height=height,
        radius=topology_node_radius(size_profile, node_diameter),
        canvas_height=canvas_height,
        z_index=z_index,
    )
def _scene_geometry(
    state: dict[str, Any],
    buildings: list[dict[str, Any]],
    *,
    canvas_height: float = CANVAS_HEIGHT,
    force_dc: bool = False,
    force_cooling: bool = False,
    include_editing_placeholders: bool = True,
    pixel: PixelSceneGeometry | None = None,
) -> tuple[dict[str, TopologyNode], dict[str, SlotPlaceholder]]:
    """Berechnet Nodes und nächste +-Positionen aus derselben Stack-Geometrie."""

    selected = list(state.get("central_devices") or [])
    dc_active = has_dc_system(selected) or force_dc
    cold_active = has_cooling_system(selected) or force_cooling
    pixel = pixel or _pixel_scene_geometry(
        state,
        buildings,
        canvas_height=canvas_height,
        force_dc=force_dc,
        force_cooling=force_cooling,
        include_editing_placeholders=include_editing_placeholders,
    )
    layouts = pixel.layouts
    nodes: dict[str, TopologyNode] = {}
    placeholders = dict(pixel.placeholders)
    # Alle Kreis-Nodes und Pillenenden teilen die zentrale Standardgröße.
    standard_radius = topology_node_radius("standard", pixel.node_diameter)

    ac_top, ac_bottom = pixel.bounds["ac"]
    if pixel.ac_visible:
        nodes["AC_BUS"] = _pill(
            "AC_BUS", pixel.column_x["power_bus"], (ac_top + ac_bottom) / 2,
            width=pixel.pill_width, height=ac_bottom - ac_top,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=2,
        )
    if dc_active:
        dc_top, dc_bottom = pixel.bounds["dc"]
        nodes["INVERTER"] = _pill(
            "INVERTER", pixel.column_x["power_bus"],
            # Der Inverter folgt dem untersten ausgewählten AC-Erzeuger
            # statt einer festen ersten Zwischenzeile.
            (pixel.bounds["ac"][1] - pixel.cell_height / 2),
            width=pixel.pill_width, height=pixel.cell_height,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=5,
        )
        nodes["DC_BUS"] = _pill(
            "DC_BUS", pixel.column_x["power_bus"], (dc_top + dc_bottom) / 2,
            width=pixel.pill_width, height=dc_bottom - dc_top,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=4,
        )

    heat_top, heat_bottom = pixel.bounds["heat"]
    nodes["HEAT_GRID"] = _pill(
        "HEAT_GRID", pixel.column_x["network"], (heat_top + heat_bottom) / 2,
        width=pixel.pill_width, height=heat_bottom - heat_top,
        node_diameter=pixel.node_diameter,
        canvas_height=canvas_height, z_index=3,
    )
    if cold_active:
        cool_top, cool_bottom = pixel.bounds["cool"]
        nodes["COOL_GRID"] = _pill(
            "COOL_GRID", pixel.column_x["network"],
            (cool_top + cool_bottom) / 2,
            width=pixel.pill_width, height=cool_bottom - cool_top,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=3,
        )

    load_top, load_bottom = pixel.bounds["load"]
    nodes["LOAD"] = _pill(
        "LOAD", pixel.column_x["load"], (load_top + load_bottom) / 2,
        width=pixel.pill_width, height=load_bottom - load_top,
        node_diameter=pixel.node_diameter,
        canvas_height=canvas_height, z_index=3,
    )

    grid_layout = layouts["electric_source"]
    if state.get("grid_enabled"):
        grid_labels = auxiliary_node_label_variants("GRID")
        nodes["GRID"] = _node(
            "GRID", _auxiliary_node_label("GRID", 2 * grid_layout.radius),
            grid_layout.anchor_x, grid_layout.anchor_y,
            "power", radius=grid_layout.radius,
            canvas_height=canvas_height, z_index=6,
            label_variants=grid_labels,
        )

    for slot in (
        "coupled_source",
        "dc_source",
        "dc_storage",
        "heat_source",
        "heat_storage",
        "cool_source",
        "cool_storage",
    ):
        codes = ordered_slot_devices(state, slot)
        for index, code in enumerate(codes):
            x, y = pixel.device_positions[code]
            layout = layouts[slot]
            carrier = CENTRAL_DEVICES[code].get("primary_carrier") or (
                CENTRAL_DEVICES[code].get("outputs", (layout.carrier,))[0]
            )
            labels = central_node_label_variants(code)
            nodes[code] = replace(
                _node(
                    code, _central_node_label(code, 2 * layout.radius), x, y,
                    carrier,
                    radius=layout.radius, canvas_height=canvas_height,
                    z_index=6 + index, label_variants=labels,
                ),
                device_code=code,
            )
    # Geräte mit demselben externen Input teilen sich genau eine Quellen-Node.
    # Die Quelle übernimmt die Zeile des obersten Verbrauchers. Ein Mittelwert
    # würde sie zwischen Haupt- und Zwischenzeilen aus dem Raster herauslösen.
    resource_groups: dict[str, list[str]] = {}
    resource_meta: dict[str, str] = {}
    for code in selected:
        resource = RESOURCE_FOR_DEVICE.get(code)
        if resource and code in nodes:
            resource_id, carrier_name = resource
            resource_groups.setdefault(resource_id, []).append(code)
            resource_meta[resource_id] = carrier_name
    ordered_resource_groups = sorted(
        resource_groups.items(),
        key=lambda item: pixel.external_source_track_by_id.get(
            item[0], pixel.external_source_start_track,
        ),
    )
    for group_index, (resource_id, codes) in enumerate(ordered_resource_groups):
        carrier_name = resource_meta[resource_id]
        # e-Qs verwenden den zentral geplanten Quellenstack unter dem
        # DC-Bereich. Ein CHP erzwingt damit seine Quelle auch ohne externen
        # Wärmeerzeuger; mehrere Quellen erhalten getrennte Halbreihen, bleiben
        # horizontal aber mit Stromnetz, H₂-Bezug und ELY ausgerichtet.
        y = pixel.layouts["electric_source"].anchor_y + (
            pixel.external_source_track_by_id.get(
                resource_id, pixel.external_source_start_track + group_index,
            )
        ) * pixel.cell_height / 2
        x = pixel.column_x["resource"]
        resource_labels = auxiliary_node_label_variants(resource_id)
        nodes[resource_id] = _node(
            resource_id,
            _auxiliary_node_label(
                resource_id, 2 * pixel.layouts["heat_source"].radius
            ),
            x,
            y, carrier_name, radius=pixel.layouts["heat_source"].radius,
            canvas_height=canvas_height, z_index=6 + group_index,
            label_variants=resource_labels,
        )

    if "gas_bus" in layouts:
        gas_layout = layouts["gas_bus"]
        gas_top, gas_bottom = pixel.bounds.get(
            "gas_bus", (
                gas_layout.anchor_y - gas_layout.radius,
                gas_layout.anchor_y + gas_layout.radius,
            ),
        )
        # Die Bounds liegen in der Pixelgeometrie; bei einer alten
        # Ergebnisansicht ohne Gasverbraucher bleibt die Pille kompakt.
        nodes["GAS_BUS"] = _pill(
            "GAS_BUS", gas_layout.anchor_x, gas_layout.anchor_y,
            width=pixel.pill_width, height=gas_bottom - gas_top,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=3,
        )
        gas_x, gas_y = pixel.device_positions["GAS_IMPORT"]
        nodes["GAS_IMPORT"] = _node(
            "GAS_IMPORT", _auxiliary_node_label("GAS_IMPORT", 2 * standard_radius),
            gas_x, gas_y, "gas", radius=standard_radius,
            canvas_height=canvas_height, z_index=7,
            label_variants=auxiliary_node_label_variants("GAS_IMPORT"),
        )
        if "GS" in pixel.device_positions:
            gs_x, gs_y = pixel.device_positions["GS"]
            nodes["GS"] = replace(
                _node(
                    "GS", _central_node_label("GS", 2 * standard_radius),
                    gs_x, gs_y, "gas", radius=standard_radius,
                    canvas_height=canvas_height, z_index=7,
                    label_variants=central_node_label_variants("GS"),
                ),
                device_code="GS",
            )

    if "hydrogen_bus" in layouts:
        h2_layout = layouts["hydrogen_bus"]
        h2_top, h2_bottom = pixel.bounds.get(
            "hydrogen_bus", (
                h2_layout.anchor_y - h2_layout.radius,
                h2_layout.anchor_y + h2_layout.radius,
            ),
        )
        nodes["H2_BUS"] = _pill(
            "H2_BUS", h2_layout.anchor_x, h2_layout.anchor_y,
            width=pixel.pill_width, height=h2_bottom - h2_top,
            node_diameter=pixel.node_diameter,
            canvas_height=canvas_height, z_index=3,
        )
        import_x, import_y = pixel.device_positions["H2_IMPORT"]
        nodes["H2_IMPORT"] = _node(
            "H2_IMPORT", _auxiliary_node_label("H2_IMPORT", 2 * standard_radius),
            import_x, import_y, "hydrogen", radius=standard_radius,
            # Der Bezug bleibt als externe Quelle vor den H₂-Komponenten;
            # die Trackplanung verhindert auch beim kompakten Bus ein
            # geometrisches Zusammenfallen mit ELY.
            canvas_height=canvas_height, z_index=15,
            label_variants=auxiliary_node_label_variants("H2_IMPORT"),
        )
        for index, code in enumerate(
            ("SAB", "FC", "ELYZ", "H2S")
        ):
            if code not in pixel.device_positions:
                continue
            x, y = pixel.device_positions[code]
            nodes[code] = replace(
                _node(
                    code, _central_node_label(code, 2 * standard_radius), x, y,
                    CENTRAL_DEVICES[code].get("outputs", ("hydrogen",))[0],
                    radius=standard_radius, canvas_height=canvas_height,
                    z_index=7 + index,
                    label_variants=central_node_label_variants(code),
                ),
                device_code=code,
            )

    building_layout = layouts["building"]
    for index, row in enumerate(buildings):
        uid = int(row.get("uid", index))
        position = pixel.device_positions.get(f"BUILDING:{uid}")
        if position is None:
            continue
        x, y = position
        building_id = row.get("id") or index + 1
        building_name = str(row.get("name") or "").strip()
        label = _building_node_label(
            building_name, building_id, 2 * building_layout.radius
        )
        wrapped_building_name = _wrapped_building_name(
            building_name, 2 * building_layout.radius
        )
        building_labels = _node_label_variants(
            building_name or str(building_id),
            wrapped_building_name or str(building_id),
            str(building_id),
        )
        nodes[f"BUILDING:{uid}"] = _node(
            f"BUILDING:{uid}", label, x, y, "neutral",
            shape="building", radius=building_layout.radius,
            canvas_height=canvas_height, z_index=6 + index,
            label_variants=building_labels,
        )
    group_labels = {
        "central": ("Weitere zentral versorgte Gebäude", "Zentrale\nGebäude"),
        "decentral": ("Weitere dezentral versorgte Gebäude", "Dezentrale\nGebäude"),
    }
    for index, group_name in enumerate(("central", "decentral")):
        members = pixel.building_groups.get(group_name)
        position = pixel.device_positions.get(
            f"BUILDING_GROUP:{group_name.upper()}"
        )
        if members is None or position is None:
            continue
        x, y = position
        full_label, wrapped_label = group_labels[group_name]
        count = len(members)
        count_suffix = f"\n{count}" if count else ""
        label_variants = _node_label_variants(
            f"{full_label} ({count})" if count else full_label,
            f"{wrapped_label}{count_suffix}",
            f"{wrapped_label.splitlines()[0]}\n{count}" if count else wrapped_label,
        )
        nodes[f"BUILDING_GROUP:{group_name.upper()}"] = _node(
            f"BUILDING_GROUP:{group_name.upper()}",
            label_variants.wrapped,
            x, y, "neutral", shape="building",
            radius=building_layout.radius,
            canvas_height=canvas_height, z_index=20 + index,
            label_variants=label_variants,
        )
    nodes = {
        node_id: replace(
            node,
            cell_width=pixel.cell_width,
            cell_height=pixel.cell_height,
        )
        for node_id, node in nodes.items()
    }
    return nodes, placeholders


def _ac_top_row_center_y(
    nodes: Mapping[str, TopologyNode], *, canvas_height: float,
) -> float:
    """Kanonischer Ausgangstrack der AC-Pille.

    Der Port folgt der obersten reservierten Anschlusszeile der Pille und
    niemals der inzwischen tiefer liegenden BHKW-Node. Damit bleiben Eintritt
    und Austritt des Busses auf derselben Rasterzeile.
    """

    if "GRID" in nodes:
        return nodes["GRID"].y
    ac_bus = nodes["AC_BUS"]
    bus_height = ac_bus.height or 2 * ac_bus.radius
    return (
        ac_bus.y * canvas_height - bus_height / 2 + ac_bus.radius
    ) / canvas_height


def power_pill_label_ys(
    nodes: Mapping[str, TopologyNode], *, canvas_height: float,
) -> dict[str, float]:
    """Zentriert AC-/DC-Texte in den sichtbaren Flächen der Strompille.

    Ohne DC liegt AC in der gesamten AC-Pille. Mit Inverter teilt dessen
    Oberkante die AC-Fläche und dessen Unterkante die DC-Fläche.
    """

    inverter = nodes.get("INVERTER")
    result: dict[str, float] = {}
    ac_bus = nodes.get("AC_BUS")
    dc_bus = nodes.get("DC_BUS")
    if ac_bus is not None:
        ac_height = ac_bus.height or 2 * ac_bus.radius
        ac_top = ac_bus.y * canvas_height - ac_height / 2
        if inverter is None:
            result["AC_BUS"] = ac_bus.y
        else:
            inverter_height = inverter.height or 2 * inverter.radius
            inverter_top = inverter.y * canvas_height - inverter_height / 2
            result["AC_BUS"] = (ac_top + inverter_top) / 2 / canvas_height
    if dc_bus is not None:
        dc_height = dc_bus.height or 2 * dc_bus.radius
        dc_bottom = dc_bus.y * canvas_height + dc_height / 2
        if inverter is None:
            result["DC_BUS"] = dc_bus.y
        else:
            inverter_height = inverter.height or 2 * inverter.radius
            inverter_bottom = inverter.y * canvas_height + inverter_height / 2
            result["DC_BUS"] = (
                inverter_bottom + dc_bottom
            ) / 2 / canvas_height
    return result
