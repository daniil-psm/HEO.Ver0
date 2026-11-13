"""Darstellungsunabhängige Geometrie und Pfadführung der HEO-Topologie."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, Mapping, Sequence

from heo.topology.definitions import COLORS, EdgeRouting, EnergyCarrier, PortSide
from heo.topology.model import (
    Topology, TopologyBounds, TopologyCell, TopologyEdge, TopologyNode, TopologyPort,
)

def node_dimensions(node: TopologyNode) -> tuple[float, float]:
    """Liefert Breite und Höhe einer Node in Ausgabepixeln."""

    diameter = float(node.radius * 2)
    return float(node.width or diameter), float(node.height or diameter)


def node_content_radius(node: TopologyNode, *, stroke_width: float = 0.0) -> float:
    """Radius der sichtbaren Kreisfläche innerhalb der zentralen Node-Grenze.

    Der Konfigurator verwendet ``box-sizing: border-box``: Der Rand liegt
    vollständig innerhalb des von der Szene reservierten Durchmessers. SVG
    zeichnet Konturen dagegen um die Geometrie herum. Dieser Wert stellt beide
    Renderer gleich und hält Nodes innerhalb ihrer Rasterzellen.
    """

    width, height = node_dimensions(node)
    return max(1.0, (min(width, height) - max(0.0, stroke_width)) / 2)


def topology_responsive_square_size(
    width: float, height: float, *, canvas_height: float | None = None,
) -> str:
    """CSS-Größe eines Kreises aus der kleineren sichtbaren Viewport-Achse."""

    resolved_height = CANVAS_HEIGHT if canvas_height is None else canvas_height
    return (
        f"min({width / CANVAS_WIDTH * 100:.4f}cqw, "
        f"{height / resolved_height * 100:.4f}cqh)"
    )


def topology_html_node_style(
    node: TopologyNode, *, canvas_height: float | None = None,
) -> dict[str, str]:
    """Gemeinsame HTML/CSS-Geometrie für interaktive Topologie-Nodes."""

    resolved_height = CANVAS_HEIGHT if canvas_height is None else canvas_height
    width, height = node_dimensions(node)
    style = {
        "left": f"{node.x * 100:.3f}%",
        "top": f"{node.y * 100:.3f}%",
        "width": f"{width / CANVAS_WIDTH * 100:.3f}%",
        "height": f"{height / resolved_height * 100:.3f}%",
        "--node-color": node.color,
        "zIndex": str(node.z_index or 4),
    }
    if node.shape == "pill":
        radius = min(node.radius, width / 2, height / 2)
        cell_width = node.cell_width or width
        cell_height = node.cell_height or height
        # Die Pillenbreite folgt der Spalte, ihre Endrundung aber weiterhin
        # dem aktuellen Komponenten-Node-Radius. Die responsive Umrechnung
        # entspricht deshalb exakt dem Radius einer Kreis-Node im selben Feld.
        radius_scale = radius / max(1.0, min(cell_width, cell_height))
        style["borderRadius"] = topology_responsive_square_size(
            cell_width * radius_scale,
            cell_height * radius_scale,
            canvas_height=resolved_height,
        )
    else:
        cell_width = node.cell_width or width
        cell_height = node.cell_height or height
        # Der logische Durchmesser ist ein Anteil der kleineren Rasterachse.
        # Diese Relation muss für cqw und cqh getrennt erhalten bleiben;
        # andernfalls schrumpft eine Node bei einer gestreckten Canvas doppelt
        # mit der kleineren Viewport-Achse.
        scale = min(width, height) / max(1.0, min(cell_width, cell_height))
        size = topology_responsive_square_size(
            cell_width * scale, cell_height * scale,
            canvas_height=resolved_height,
        )
        style.update({"width": size, "height": size})
    return style


def vertical_stack_position(
    anchor_x: float,
    anchor_y: float,
    step_y: float,
    index: int,
) -> tuple[float, float]:
    """Positioniert das Element ``index`` in einem vertikalen Stack.

    Die Funktion ist absichtlich frei von Konfigurator-Semantik. Dadurch
    verwenden Konfigurator, Ergebnisdarstellung und spätere PFC/Sankey-Ansichten
    dieselbe grundlegende Stack-Geometrie.
    """

    return anchor_x, anchor_y + index * step_y


def merge_vertical_bounds(
    bounds: Iterable[tuple[float, float] | None],
) -> tuple[float, float] | None:
    """Vereinigt vorhandene vertikale Pixelgrenzen zu einem Bereich."""

    available = [item for item in bounds if item is not None]
    if not available:
        return None
    return min(item[0] for item in available), max(
        item[1] for item in available
    )


def track_block_shift_after(
    previous_last_track: int,
    next_first_track: int,
) -> int:
    """Verschiebung für zwei vertikal aneinandergrenzende Rasterblöcke.

    Ein Trackschritt entspricht einer halben Zellenhöhe. ``row_bounds``
    erweitert den ersten und letzten belegten Track jeweils um eine halbe
    Zellenhöhe. Deshalb berühren sich zwei Pillen genau dann, wenn der erste
    Track des unteren Blocks zwei Tracks auf den letzten Track des oberen
    folgt. Bereits getrennte Blöcke behalten ihre natürliche Position.
    """

    return max(0, previous_last_track + 2 - next_first_track)


def node_bounds(
    node: TopologyNode,
    canvas_width: float,
    canvas_height: float,
) -> TopologyBounds:
    """Liefert die äußeren Node-Grenzen in normierten Canvas-Koordinaten."""

    width, height = node_dimensions(node)
    return TopologyBounds(
        x=node.x - width / canvas_width / 2,
        y=node.y - height / canvas_height / 2,
        width=width / canvas_width,
        height=height / canvas_height,
    )


def node_content_bounds(
    node: TopologyNode,
    canvas_width: float,
    canvas_height: float,
) -> TopologyBounds:
    """Liefert die geschützten Text- und Bildgrenzen einer Node in normierten Koordinaten."""

    return TopologyBounds(
        x=node.x - node.content_width / canvas_width / 2,
        y=node.y - node.content_height / canvas_height / 2,
        width=node.content_width / canvas_width,
        height=node.content_height / canvas_height,
    )


def _bounds_overlap(first: TopologyBounds, second: TopologyBounds) -> bool:
    """Prüft die Überlappung zweier rechteckiger Node-Grenzen."""

    return not (
        first.x + first.width <= second.x
        or second.x + second.width <= first.x
        or first.y + first.height <= second.y
        or second.y + second.height <= first.y
    )


def validate_content_visibility(
    nodes: Mapping[str, TopologyNode],
    canvas_width: float,
    canvas_height: float,
) -> list[str]:
    """Liefert Hinweise zu überlappenden oder verdeckten Inhalten innerhalb derselben Zelle."""

    issues: list[str] = []
    grouped: dict[str, list[TopologyNode]] = {}
    for node in nodes.values():
        if node.cell_id:
            grouped.setdefault(node.cell_id, []).append(node)

    for cell_id, cell_nodes in grouped.items():
        for index, first in enumerate(cell_nodes):
            first_bounds = node_content_bounds(first, canvas_width, canvas_height)
            for second in cell_nodes[index + 1 :]:
                second_content = node_content_bounds(
                    second, canvas_width, canvas_height
                )
                first_outer = node_bounds(first, canvas_width, canvas_height)
                second_outer = node_bounds(second, canvas_width, canvas_height)
                content_overlap = _bounds_overlap(first_bounds, second_content)
                content_covered = (
                    first.z_index < second.z_index
                    and _bounds_overlap(first_bounds, second_outer)
                ) or (
                    second.z_index < first.z_index
                    and _bounds_overlap(second_content, first_outer)
                )
                if content_overlap or content_covered:
                    issues.append(
                        f"Zelle {cell_id}: Inhalte von {first.id} und {second.id} überlappen."
                    )
    return issues


def position_overlapping_nodes(
    nodes: list[TopologyNode],
    *,
    cell_id: str,
    cell_title: str,
    center_x: float,
    center_y: float,
    canvas_width: float,
    canvas_height: float,
    overlap_ratio: float = 0.28,
) -> tuple[list[TopologyNode], TopologyCell | None]:
    """Liefert vertikal überlappende Node-Kopien und ihre gemeinsame Zellfläche.

    overlap_ratio begrenzt die gewünschte Überlappung; geschützte Inhalte bestimmen den Mindestabstand.
    """

    if not nodes:
        return [], None

    ordered = list(nodes)
    max_diameter = max(node_dimensions(node)[1] for node in ordered)
    # Die gewünschte Überlappung darf weder Beschriftungen noch die davorliegende Kreisfläche verdecken.
    content_step = max(node.content_height for node in ordered) + 8.0
    overlap_step = max_diameter * (1.0 - max(0.0, min(0.45, overlap_ratio)))
    radius_to_content = max(
        node_dimensions(node)[1] / 2 + node.content_height / 2 + 4.0
        for node in ordered
    )
    step = max(content_step, overlap_step, radius_to_content)
    total_height = max_diameter + step * (len(ordered) - 1)
    start_y = center_y * canvas_height - total_height / 2 + max_diameter / 2

    positioned = [
        replace(
            node,
            x=center_x,
            y=(start_y + index * step) / canvas_height,
            cell_id=cell_id,
            z_index=node.z_index + index,
        )
        for index, node in enumerate(ordered)
    ]
    # Die gemeinsame Zellfläche umschließt die vollständig positionierte Gruppe.
    cell_width = max(node_dimensions(node)[0] for node in positioned) + 18.0
    cell = TopologyCell(
        id=cell_id,
        title=cell_title,
        carrier={
            "ac": "ac",
            "dc": "dc",
            "thermal": "heat",
            "cooling": "cooling",
            "load": "ac",
        }[positioned[0].group],
        role=positioned[0].role,
        node_ids=tuple(node.id for node in positioned),
        bounds=TopologyBounds(
            x=center_x - cell_width / canvas_width / 2,
            y=(start_y - max_diameter / 2) / canvas_height,
            width=cell_width / canvas_width,
            height=total_height / canvas_height,
        ),
    )
    return positioned, cell


def size_pill_to_nodes(
    pill: TopologyNode,
    connected_nodes: list[TopologyNode],
    *,
    canvas_width: float,
    canvas_height: float,
    minimum_height: float = 92.0,
) -> TopologyNode:
    """Passt eine Bus-Pille oben und unten an die Grenzen ihrer Komponenten an."""

    if not connected_nodes:
        return replace(pill, height=max(minimum_height, node_dimensions(pill)[1]))

    bounds = [node_bounds(node, canvas_width, canvas_height) for node in connected_nodes]
    top = min(item.y for item in bounds)
    bottom = max(item.y + item.height for item in bounds)
    height = max(minimum_height, (bottom - top) * canvas_height)
    center_y = (top + bottom) / 2
    return replace(pill, y=center_y, height=height)


# Die Node verdeckt das letzte Kantenstück; dadurch bleiben Anschlüsse bei Skalierung lückenlos.
def node_port(
    node: TopologyNode,
    *,
    port_id: str,
    carrier: EnergyCarrier,
    side: PortSide,
    canvas_width: float,
    canvas_height: float,
    position_y: float | None = None,
) -> TopologyPort:
    """Erzeugt einen normierten Node-Port mit optionaler Anschlusshöhe position_y."""

    _width, height = node_dimensions(node)
    x = node.x
    y = node.y if position_y is None else position_y
    if node.shape == "pill" and position_y is not None:
        half_height = height / canvas_height / 2
        y = max(node.y - half_height, min(node.y + half_height, position_y))
    return TopologyPort(port_id, carrier, side, x, y)


def node_center(
    node: TopologyNode,
    canvas_width: float,
    canvas_height: float,
) -> tuple[float, float]:
    """Rechnet den normierten Node-Mittelpunkt in Pixelkoordinaten der Ausgabefläche um."""

    return node.x * canvas_width, node.y * canvas_height


def edge_offsets(
    edges: list[TopologyEdge],
    active_threshold: float = 0.05,
    spacing: float = 36.0,
) -> dict[str, float]:
    """Liefert Pixelversätze für parallele aktive Kanten anhand von active_threshold und spacing."""

    groups: dict[tuple[str, str], list[TopologyEdge]] = {}
    for edge in edges:
        # die sortierte Kombination gruppiert beide Flussrichtungen gemeinsam
        key = tuple(sorted((edge.source, edge.target)))
        groups.setdefault(key, []).append(edge)

    offsets: dict[str, float] = {}
    for group in groups.values():
        active = [edge for edge in group if abs(edge.value) >= active_threshold]
        if len(active) <= 1:
            for edge in group:
                offsets[edge.id] = 0.0
            continue

        start = -spacing * (len(active) - 1) / 2
        for index, edge in enumerate(active):
            offsets[edge.id] = start + index * spacing
        for edge in group:
            offsets.setdefault(edge.id, 0.0)
    return offsets


def bezier_points(
    source: TopologyNode,
    target: TopologyNode,
    curvature: float,
    offset: float,
    canvas_width: float,
    canvas_height: float,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Liefert Start, zwei Kontrollpunkte und Ende einer Bézierkurve in Pixelkoordinaten.

    curvature steuert die Krümmung; offset versetzt parallele Verbindungen seitlich.
    """

    x0, y0 = node_center(source, canvas_width, canvas_height)
    x1, y1 = node_center(target, canvas_width, canvas_height)
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)

    if length < 1e-9:
        return (x0, y0), (x0, y0), (x1, y1), (x1, y1)

    # Normalenvektor verschiebt beide Kontrollpunkte auf dieselbe Pfadseite
    normal_x = -dy / length
    normal_y = dx / length
    bend = curvature * length
    offset_x = normal_x * (bend + offset)
    offset_y = normal_y * (bend + offset)
    control_1 = (x0 + dx * 0.34 + offset_x, y0 + dy * 0.34 + offset_y)
    control_2 = (x0 + dx * 0.66 + offset_x, y0 + dy * 0.66 + offset_y)
    return (x0, y0), control_1, control_2, (x1, y1)


def curved_path_between(
    source: TopologyNode,
    target: TopologyNode,
    curvature: float,
    offset: float,
    canvas_width: float,
    canvas_height: float,
) -> str:
    """Liefert den SVG-Pfad einer geschwungenen Verbindung zwischen zwei Node-Mittelpunkten."""

    start, control_1, control_2, end = bezier_points(
        source,
        target,
        curvature,
        offset,
        canvas_width,
        canvas_height,
    )
    return (
        f"M {start[0]:.1f} {start[1]:.1f} "
        f"C {control_1[0]:.1f} {control_1[1]:.1f} "
        f"{control_2[0]:.1f} {control_2[1]:.1f} {end[0]:.1f} {end[1]:.1f}"
    )


def path_between_ports(
    source: TopologyPort,
    target: TopologyPort,
    *,
    canvas_width: float,
    canvas_height: float,
    routing: EdgeRouting = "horizontal_tangent",
) -> str:
    """Liefert einen SVG-Pfad zwischen expliziten Ports mit horizontalen Tangenten an beiden Enden."""

    start_x = source.x * canvas_width
    start_y = source.y * canvas_height
    end_x = target.x * canvas_width
    end_y = target.y * canvas_height

    if routing == "horizontal" or abs(start_y - end_y) < 0.5:
        return f"M {start_x:.1f} {start_y:.1f} L {end_x:.1f} {end_y:.1f}"

    delta_x = end_x - start_x
    direction = 1.0 if delta_x >= 0 else -1.0
    # Der Griff bleibt unter der halben horizontalen Distanz und erzeugt dadurch
    # auch bei kleinen Abständen eine ruhige, eindeutige S-Kurve.
    handle = min(max(abs(delta_x) * 0.38, 24.0), max(24.0, abs(delta_x) * 0.48))
    control_1_x = start_x + direction * handle
    control_2_x = end_x - direction * handle
    return (
        f"M {start_x:.1f} {start_y:.1f} "
        f"C {control_1_x:.1f} {start_y:.1f} "
        f"{control_2_x:.1f} {end_y:.1f} {end_x:.1f} {end_y:.1f}"
    )


def same_side_loop_path(
    source: TopologyPort,
    target: TopologyPort,
    *,
    canvas_width: float,
    canvas_height: float,
    loop_depth: float = 72.0,
) -> str:
    """Erzeugt eine ruhige U-Kurve mit horizontalen Tangenten an beiden Ports."""

    start_x = source.x * canvas_width
    start_y = source.y * canvas_height
    end_x = target.x * canvas_width
    end_y = target.y * canvas_height
    direction = -1.0 if source.side == "left" else 1.0
    outside_x = (
        min(start_x, end_x) - loop_depth
        if direction < 0
        else max(start_x, end_x) + loop_depth
    )
    return (
        f"M {start_x:.1f} {start_y:.1f} "
        f"C {outside_x:.1f} {start_y:.1f} "
        f"{outside_x:.1f} {end_y:.1f} {end_x:.1f} {end_y:.1f}"
    )


def horizontal_semicircle_path(
    source: TopologyPort,
    target: TopologyPort,
    *,
    canvas_width: float,
    canvas_height: float,
    diameter: float,
) -> str:
    """Horizontale Zuleitung mit einem Halbkreis am Ziel.

    Quelle und Ziel besitzen horizontale Tangenten. Der Halbkreis hat exakt
    ``diameter`` Pixel Höhe und eignet sich damit für einen Anschluss, dessen
    reservierter Pillenabschnitt genau einer Node-Höhe entspricht.
    """

    start_x = source.x * canvas_width
    start_y = source.y * canvas_height
    end_x = target.x * canvas_width
    end_y = target.y * canvas_height
    radius = max(1.0, diameter / 2)
    expected_delta = 2 * radius
    # Der vorgelagerte Pillenabschnitt liefert normalerweise exakt diese
    # Höhendifferenz. Bei Rundungsabweichungen bleibt der Radius geometrisch
    # stabil und die kurze vertikale Differenz wird in der Linie aufgenommen.
    arc_start_y = end_y - expected_delta if end_y >= start_y else end_y + expected_delta
    sweep = 0 if end_y >= arc_start_y else 1
    return (
        f"M {start_x:.1f} {start_y:.1f} "
        f"L {end_x:.1f} {arc_start_y:.1f} "
        f"A {radius:.1f} {radius:.1f} 0 0 {sweep} "
        f"{end_x:.1f} {end_y:.1f}"
    )


def rounded_orthogonal_path(
    source: TopologyPort,
    target: TopologyPort,
    *,
    canvas_width: float,
    canvas_height: float,
    lane_x: float,
    corner_radius: float = 16.0,
) -> str:
    """Verbindet horizontale Ports als H-V-H-Pfad mit runden Ecken.

    ``lane_x`` ist die x-Position des vertikalen Abschnitts in Pixeln. Der
    Radius wird auf die vorhandenen Abschnittslängen begrenzt, damit auch eng
    benachbarte DC-Verbraucherpfade geometrisch gültig bleiben.
    """

    start_x = source.x * canvas_width
    start_y = source.y * canvas_height
    end_x = target.x * canvas_width
    end_y = target.y * canvas_height
    # Kurze Teilstücke begrenzen den Radius, damit Rundungen nicht über ihre Stützpunkte hinausragen.
    radius = max(0.0, min(
        corner_radius,
        abs(lane_x - start_x) / 2,
        abs(end_x - lane_x) / 2,
        abs(end_y - start_y) / 2,
    ))
    if radius <= 0.01 or abs(end_y - start_y) <= 0.01:
        return (
            f"M {start_x:.1f} {start_y:.1f} "
            f"L {lane_x:.1f} {start_y:.1f} "
            f"L {lane_x:.1f} {end_y:.1f} "
            f"L {end_x:.1f} {end_y:.1f}"
        )
    sx = 1.0 if lane_x >= start_x else -1.0
    ex = 1.0 if end_x >= lane_x else -1.0
    sy = 1.0 if end_y >= start_y else -1.0
    return (
        f"M {start_x:.1f} {start_y:.1f} "
        f"L {lane_x - sx * radius:.1f} {start_y:.1f} "
        f"Q {lane_x:.1f} {start_y:.1f} "
        f"{lane_x:.1f} {start_y + sy * radius:.1f} "
        f"L {lane_x:.1f} {end_y - sy * radius:.1f} "
        f"Q {lane_x:.1f} {end_y:.1f} "
        f"{lane_x + ex * radius:.1f} {end_y:.1f} "
        f"L {end_x:.1f} {end_y:.1f}"
    )


def rounded_polyline_path(
    points: Sequence[tuple[float, float]], *, corner_radius: float = 12.0,
) -> str:
    """Erzeugt einen abgerundeten Pfad durch beliebig viele Stützpunkte."""

    # Doppelte aufeinanderfolgende Punkte würden Teilstücke ohne Richtung erzeugen.
    filtered: list[tuple[float, float]] = []
    for x, y in points:
        point = (float(x), float(y))
        if not filtered or math.hypot(
            point[0] - filtered[-1][0], point[1] - filtered[-1][1],
        ) > 1e-6:
            filtered.append(point)
    if not filtered:
        return ""
    if len(filtered) == 1:
        return f"M {filtered[0][0]:.1f} {filtered[0][1]:.1f}"

    # Jede innere Ecke abrunden; die benachbarten Teilstücklängen begrenzen den Radius.
    commands = [f"M {filtered[0][0]:.1f} {filtered[0][1]:.1f}"]
    for index in range(1, len(filtered) - 1):
        previous = filtered[index - 1]
        current = filtered[index]
        following = filtered[index + 1]
        incoming = (current[0] - previous[0], current[1] - previous[1])
        outgoing = (following[0] - current[0], following[1] - current[1])
        incoming_length = math.hypot(*incoming)
        outgoing_length = math.hypot(*outgoing)
        radius = min(
            max(0.0, corner_radius), incoming_length / 2, outgoing_length / 2,
        )
        if radius <= 0.01:
            commands.append(f"L {current[0]:.1f} {current[1]:.1f}")
            continue
        before = (
            current[0] - incoming[0] / incoming_length * radius,
            current[1] - incoming[1] / incoming_length * radius,
        )
        after = (
            current[0] + outgoing[0] / outgoing_length * radius,
            current[1] + outgoing[1] / outgoing_length * radius,
        )
        commands.extend((
            f"L {before[0]:.1f} {before[1]:.1f}",
            f"Q {current[0]:.1f} {current[1]:.1f} "
            f"{after[0]:.1f} {after[1]:.1f}",
        ))
    commands.append(f"L {filtered[-1][0]:.1f} {filtered[-1][1]:.1f}")
    return " ".join(commands)


def distribute_routing_lanes(
    keys: Sequence[str],
    *,
    start: float,
    end: float,
) -> dict[str, float]:
    """Verteilt Spuren mit gleichen Zwischen- und Randabständen im Korridor.

    ``start`` und ``end`` können eine vollständige oder halbe Rasterzeile bzw.
    -spalte beschreiben; dieselbe Regel gilt für X- und Y-Spuren.

    N eindeutige Schlüssel teilen den Bereich in N + 1 gleiche Abstände.
    Ihre Reihenfolge bleibt erhalten; eine einzelne Spur liegt in der Mitte.
    """

    ordered = list(dict.fromkeys(keys))
    if not ordered:
        return {}
    corridor_left, corridor_right = sorted((float(start), float(end)))
    step = (corridor_right - corridor_left) / (len(ordered) + 1)
    return {
        key: corridor_left + index * step
        for index, key in enumerate(ordered, start=1)
    }


def distribute_vertical_lanes(
    keys: Sequence[str],
    *,
    left: float,
    right: float,
) -> dict[str, float]:
    """Verteilt vertikale Spuren mit gleichen Zwischen- und Randabständen im X-Korridor."""

    return distribute_routing_lanes(keys, start=left, end=right)


def distribute_horizontal_lanes(
    keys: Sequence[str],
    *,
    top: float,
    bottom: float,
) -> dict[str, float]:
    """Verteilt horizontale Spuren mit gleichen Zwischen- und Randabständen im Y-Korridor."""

    return distribute_routing_lanes(keys, start=top, end=bottom)


def candidate_z_indices(
    points: Sequence[tuple[float, float]], *, base: int = 30,
) -> tuple[int, ...]:
    """Liefert die zentrale Stapelreihenfolge einer Kandidatengruppe.

    Kandidaten in der oberen Hälfte liegen vor Kandidaten darunter. Bei
    gleicher Höhe bleibt die Reihenfolge von links nach rechts stabil. Der
    zurückgegebene Index entspricht stets dem Punkt an derselben Listenstelle.
    """

    z_indices = [int(base)] * len(points)
    ordered_indices = sorted(
        range(len(points)), key=lambda index: (
            points[index][1], points[index][0], index,
        ),
    )
    for rank, index in enumerate(ordered_indices):
        z_indices[index] = int(base) + len(points) - rank
    return tuple(z_indices)


def place_candidate_group(
    anchor: tuple[float, float],
    *,
    anchor_radius: float,
    group_origin_radius: float,
    candidate_offsets: Sequence[tuple[float, float]],
    candidate_radius: float,
    canvas_width: float,
    canvas_height: float,
    margin: float = 8.0,
) -> tuple[float, float]:
    """Positioniert eine Kandidatengruppe innerhalb der Topologiefläche.

    Die Gruppe besteht immer aus einem eigenen +-Ursprung und radial um ihn
    angeordneten Kandidaten. Solange der gesamte Verbund sichtbar bleibt,
    stimmt sein Mittelpunkt mit dem auslösenden +-Button überein. Bei einem
    Randüberlauf wird der *Gruppenursprung* tangential zum ursprünglichen
    +-Button verschoben; die radiale Kandidatenanordnung bleibt unverändert.
    Die Funktion ist unabhängig von Kandidatenart und kann damit für zentrale
    wie dezentrale Slots dienen.
    """

    offsets = tuple(candidate_offsets)
    if not offsets:
        return anchor
    width = float(canvas_width)
    height = float(canvas_height)
    safe_margin = max(0.0, float(margin))
    candidate_size = max(0.0, float(candidate_radius))
    origin_size = max(0.0, float(group_origin_radius))

    def fits(center: tuple[float, float]) -> bool:
        """Prüft, ob Gruppenursprung und alle Kandidaten samt Randabstand in den Viewport passen."""

        origin_fits = (
            safe_margin + origin_size <= center[0] <= width - safe_margin - origin_size
            and safe_margin + origin_size <= center[1] <= height - safe_margin - origin_size
        )
        return origin_fits and all(
            safe_margin + candidate_size <= center[0] + offset_x <= width - safe_margin - candidate_size
            and safe_margin + candidate_size <= center[1] + offset_y <= height - safe_margin - candidate_size
            for offset_x, offset_y in offsets
        )

    if fits(anchor):
        return anchor

    # Der neue zentrale +-Ursprung berührt den ursprünglichen +-Kreis. Mehrere
    # Winkel werden geprüft, damit etwa an einer linken oberen Ecke die freie
    # Richtung nach rechts unten gewählt werden kann.
    tangent_distance = max(0.0, float(anchor_radius)) + origin_size
    candidates: list[tuple[float, float]] = []
    for step in range(32):
        angle = 2 * math.pi * step / 32
        group_center = (
            anchor[0] + math.cos(angle) * tangent_distance,
            anchor[1] + math.sin(angle) * tangent_distance,
        )
        if fits(group_center):
            candidates.append(group_center)
    if candidates:
        viewport_center = width / 2, height / 2
        return min(
            candidates,
            key=lambda center: (
                (center[0] - anchor[0]) ** 2 + (center[1] - anchor[1]) ** 2,
                (center[0] - viewport_center[0]) ** 2
                + (center[1] - viewport_center[1]) ** 2,
            ),
        )

    # Extrem kleine Ansichten können keine Tangentenposition aufnehmen. Dann
    # wird der gesamte Gruppenrahmen geklemmt, statt einzelne Kandidaten
    # außerhalb des Viewports zu belassen.
    min_x = max(
        safe_margin + origin_size,
        *(safe_margin + candidate_size - offset_x for offset_x, _ in offsets),
    )
    max_x = min(
        width - safe_margin - origin_size,
        *(width - safe_margin - candidate_size - offset_x for offset_x, _ in offsets),
    )
    min_y = max(
        safe_margin + origin_size,
        *(safe_margin + candidate_size - offset_y for _, offset_y in offsets),
    )
    max_y = min(
        height - safe_margin - origin_size,
        *(height - safe_margin - candidate_size - offset_y for _, offset_y in offsets),
    )
    return (
        min(max(anchor[0], min_x), max(min_x, max_x)),
        min(max(anchor[1], min_y), max(min_y, max_y)),
    )


def translate_nodes(
    nodes: Mapping[str, TopologyNode],
    *,
    dx: float,
    dy: float,
    canvas_width: float,
    canvas_height: float,
) -> dict[str, TopologyNode]:
    """Verschiebt einen vollständigen Szenenzustand in Pixelkoordinaten.

    Die Funktion verändert weder Topologie noch Größen. Sie wird unter anderem
    benutzt, um eine Konfigurator-Vorschau am auslösenden Slot zu verankern.
    """

    return {
        node_id: replace(
            node,
            x=node.x + dx / canvas_width,
            y=node.y + dy / canvas_height,
        )
        for node_id, node in nodes.items()
    }


def _distance_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Berechnet den kleinsten euklidischen Abstand eines Punktes zu einem Liniensegment."""

    point_x, point_y = point
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    denominator = dx * dx + dy * dy
    if denominator <= 1e-9:
        return math.hypot(point_x - x0, point_y - y0)
    factor = max(
        0.0,
        min(1.0, ((point_x - x0) * dx + (point_y - y0) * dy) / denominator),
    )
    nearest = (x0 + factor * dx, y0 + factor * dy)
    return math.hypot(point_x - nearest[0], point_y - nearest[1])


def collision_avoiding_path(
    source: TopologyNode,
    target: TopologyNode,
    all_nodes: dict[str, TopologyNode],
    curvature: float,
    offset: float,
    canvas_width: float,
    canvas_height: float,
    obstacle_clearance: float = 16.0,
    route_clearance: float = 14.0,
    boundary_padding: float = 24.0,
    corner_radius: float = 18.0,
) -> str:
    """Liefert eine direkte Kurve oder einen gerundeten SVG-Pfad über einen bewerteten Korridor.

    obstacle_clearance steuert die Hinderniserkennung, route_clearance die Korridorprüfung.
    """

    start = node_center(source, canvas_width, canvas_height)
    end = node_center(target, canvas_width, canvas_height)
    obstacles = [
        node
        for node in all_nodes.values()
        if node.id not in {source.id, target.id}
        and _distance_to_segment(
            node_center(node, canvas_width, canvas_height),
            start,
            end,
        )
        < node.radius + obstacle_clearance
    ]
    if not obstacles:
        return curved_path_between(
            source,
            target,
            curvature,
            offset,
            canvas_width,
            canvas_height,
        )

    # Ausweichkorridore am Rand, in der Mitte und neben allen Nodes bieten alternative Wege.
    candidate_lanes = {
        boundary_padding,
        canvas_width - boundary_padding,
        (start[0] + end[0]) / 2 + offset,
    }
    for node in all_nodes.values():
        center_x, _ = node_center(node, canvas_width, canvas_height)
        candidate_lanes.add(
            max(boundary_padding, center_x - node.radius - boundary_padding + offset)
        )
        candidate_lanes.add(
            min(
                canvas_width - boundary_padding,
                center_x + node.radius + boundary_padding + offset,
            )
        )

    # Kollisionen werden deutlich stärker gewichtet als die resultierende Pfadlänge.
    def route_score(lane_x: float) -> float:
        """Bewertet einen vertikalen Korridor nach Kollisionen und Pfadlänge."""

        segments = [
            (start, (lane_x, start[1])),
            ((lane_x, start[1]), (lane_x, end[1])),
            ((lane_x, end[1]), end),
        ]
        collisions = 0
        for node in all_nodes.values():
            if node.id in {source.id, target.id}:
                continue
            center = node_center(node, canvas_width, canvas_height)
            if any(
                _distance_to_segment(center, segment_start, segment_end)
                < node.radius + route_clearance
                for segment_start, segment_end in segments
            ):
                collisions += 1
        length = (
            abs(start[0] - lane_x)
            + abs(start[1] - end[1])
            + abs(end[0] - lane_x)
        )
        return collisions * 100_000 + length

    # Erst den günstigsten Korridor wählen, anschließend den gerundeten SVG-Pfad daraus erzeugen.
    lane = min(candidate_lanes, key=route_score)
    direction_x0 = 1 if lane >= start[0] else -1
    direction_x1 = 1 if end[0] >= lane else -1
    direction_y = 1 if end[1] >= start[1] else -1
    return (
        f"M {start[0]:.1f} {start[1]:.1f} "
        f"L {lane - direction_x0 * corner_radius:.1f} {start[1]:.1f} "
        f"Q {lane:.1f} {start[1]:.1f} "
        f"{lane:.1f} {start[1] + direction_y * corner_radius:.1f} "
        f"L {lane:.1f} {end[1] - direction_y * corner_radius:.1f} "
        f"Q {lane:.1f} {end[1]:.1f} "
        f"{lane + direction_x1 * corner_radius:.1f} {end[1]:.1f} "
        f"L {end[0]:.1f} {end[1]:.1f}"
    )


def build_edge_paths(
    nodes: dict[str, TopologyNode],
    edges: list[TopologyEdge],
    canvas_width: float,
    canvas_height: float,
    avoid_nodes: bool = False,
) -> dict[str, str]:
    """Liefert SVG-Pfade je Kante; avoid_nodes aktiviert die Prüfung von Ausweichkorridoren."""

    offsets = edge_offsets(edges)
    paths: dict[str, str] = {}
    for edge in edges:
        if edge.path is not None:
            paths[edge.id] = edge.path
            continue
        source = nodes[edge.source]
        target = nodes[edge.target]
        if edge.source_port is not None and edge.target_port is not None:
            paths[edge.id] = path_between_ports(
                edge.source_port,
                edge.target_port,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                routing=edge.routing,
            )
        elif avoid_nodes:
            paths[edge.id] = collision_avoiding_path(
                source,
                target,
                nodes,
                edge.curvature,
                offsets[edge.id],
                canvas_width,
                canvas_height,
            )
        else:
            paths[edge.id] = curved_path_between(
                source,
                target,
                edge.curvature,
                offsets[edge.id],
                canvas_width,
                canvas_height,
            )
    return paths


# Energiesystem-Komponenten als Nodes
DEFAULT_NODES = (
    TopologyNode("grid", "Stromnetz", "grid", "ac", "source", COLORS["ac"], 64, 0.13, 0.16),
    TopologyNode("ac_bus", "AC-Bus", "bus", "ac", "bus", COLORS["ac"], 64, 0.13, 0.42),
    TopologyNode("converter", "Wandler", "converter", "dc", "converter", COLORS["ac"], 64, 0.30, 0.42),
    TopologyNode("pv", "PV", "pv", "dc", "source", COLORS["dc"], 64, 0.45, 0.16, "PV"),
    TopologyNode("dc_bus", "DC-Bus", "bus", "dc", "bus", COLORS["dc"], 64, 0.56, 0.42),
    TopologyNode("bess", "BESS", "battery", "dc", "storage", COLORS["dc"], 64, 0.69, 0.16, "BAT"),
    TopologyNode("heatpump", "Reversible\nWP", "heatpump", "thermal", "converter", COLORS["heat"], 66, 0.90, 0.42, "HP"),
    TopologyNode("thermal_storage", "Thermischer\nSpeicher", "storage", "thermal", "storage", COLORS["heat"], 64, 0.90, 0.64, "TES"),
    TopologyNode("load", "Last", "house", "load", "sink", COLORS["neutral"], 74, 0.56, 0.84),
)

# Verbindungen zwischen den Komponenten als Edges
DEFAULT_EDGES = (
    ("grid_to_ac", "grid", "ac_bus", "ac", 0.00),
    ("ac_to_grid", "ac_bus", "grid", "ac", 0.00),
    ("ac_to_converter", "ac_bus", "converter", "ac", 0.00),
    ("converter_to_dc", "converter", "dc_bus", "dc", 0.00),
    ("dc_to_converter", "dc_bus", "converter", "dc", 0.00),
    ("converter_to_ac", "converter", "ac_bus", "ac", 0.00),
    ("ac_to_load", "ac_bus", "load", "ac", 0.16),
    ("pv_to_dc", "pv", "dc_bus", "dc", 0.08),
    ("dc_to_bess", "dc_bus", "bess", "dc", 0.08),
    ("bess_to_dc", "bess", "dc_bus", "dc", 0.08),
    ("dc_to_heatpump", "dc_bus", "heatpump", "dc", 0.00),
    ("dc_to_load", "dc_bus", "load", "dc", 0.00),
    ("heatpump_to_heat_load", "heatpump", "load", "heat", 0.12),
    ("heatpump_to_storage", "heatpump", "thermal_storage", "heat", 0.00),
    ("storage_to_heat_load", "thermal_storage", "load", "heat", 0.10),
    ("heatpump_to_cooling_load", "heatpump", "load", "cooling", -0.12),
)


def build_default_topology(edge_values: Mapping[str, float] | None = None) -> Topology:
    """Erzeugt die Beispieltopologie mit optionalen Kantenwerten und Lastsegmenten."""

    values = edge_values or {}
    nodes = {node.id: node for node in DEFAULT_NODES}
    edges = [
        TopologyEdge(
            edge_id,
            source,
            target,
            carrier,
            float(values.get(edge_id, 0.0) or 0.0),
            curvature,
        )
        for edge_id, source, target, carrier, curvature in DEFAULT_EDGES
    ]
    return Topology(nodes=nodes, edges=edges)


CANVAS_WIDTH = 1600.0
CANVAS_HEIGHT = 820.0
TOPOLOGY_EDGE_STROKE_WIDTH = 3.0


def centered_edge_port_ys(
    center_y: float,
    connection_ids: Sequence[str],
    *,
    canvas_height: float,
    edge_width: float = TOPOLOGY_EDGE_STROKE_WIDTH,
) -> dict[str, float]:
    """Stapelt gleich breite Edge-Ports lückenlos und insgesamt zentriert.

    Die Rückgabewerte sind normierte Y-Koordinaten. Der Abstand benachbarter
    Mittellinien entspricht exakt der sichtbaren Linienbreite in Canvaspixeln;
    dadurch berühren sich die Edge-Bereiche, ohne einander zu überdecken.
    """

    ordered = list(dict.fromkeys(connection_ids))
    if not ordered:
        return {}
    spacing = max(0.0, float(edge_width)) / max(1.0, float(canvas_height))
    start_y = center_y - spacing * (len(ordered) - 1) / 2
    return {
        connection_id: start_y + index * spacing
        for index, connection_id in enumerate(ordered)
    }
