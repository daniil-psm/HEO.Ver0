"""Reine Pfadgeometrie für die bereits im Layoutplan festgelegten Routen."""
from __future__ import annotations

import math

from heo.topology.definitions import PortSide
from heo.topology.geometry import (
    CANVAS_HEIGHT, CANVAS_WIDTH, node_port, path_between_ports,
    rounded_orthogonal_path, rounded_polyline_path,
)
from heo.topology.model import TopologyNode


def _ports_path(
    source: TopologyNode,
    target: TopologyNode,
    carrier: str,
    *,
    y: float | None = None,
    source_y: float | None = None,
    target_y: float | None = None,
    canvas_height: float = CANVAS_HEIGHT,
) -> str:
    """Liefert den direkten SVG-Pfad zwischen den einander zugewandten Ports zweier Nodes."""

    topology_carrier = {
        "power": "ac",
        "ac": "ac",
        "dc": "dc",
        "heat": "heat",
        "cool": "cooling",
        "hydrogen": "hydrogen",
    }.get(carrier, "ac")
    # Der Port liegt immer auf der Seite, die zur Gegen-Node zeigt. Dadurch
    # enden auch rückwärts gerichtete Kanten (z. B. Netz → links liegender
    # Erzeuger) am sichtbaren Node-Rand statt an einer Feldgrenze.
    source_side: PortSide = "right" if target.x >= source.x else "left"
    target_side: PortSide = "left" if target.x >= source.x else "right"
    source_port = node_port(
        source,
        port_id=f"{source.id}:out",
        carrier=topology_carrier,
        side=source_side,
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=source_y if source_y is not None else y,
    )
    target_port = node_port(
        target,
        port_id=f"{target.id}:in",
        carrier=topology_carrier,
        side=target_side,
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=target_y if target_y is not None else y,
    )
    return path_between_ports(
        source_port,
        target_port,
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
    )


def _akm_heat_path(
    source: TopologyNode,
    target: TopologyNode,
    *,
    source_y: float,
    target_y: float,
    lane_x: float,
    canvas_height: float,
) -> str:
    """Verbindet Wärmenetz und AKM als abgerundeten H-V-H-Pfad.

    Beide Ports liegen auf der linken Node-Seite. Der vertikale Abschnitt
    läuft in ``lane_x``; so bleiben ausschließlich horizontale und vertikale
    Geraden, während nur die beiden 90-Grad-Ecken abgerundet werden.
    """

    source_port = node_port(
        source,
        port_id=f"{source.id}:akm-heat-out",
        carrier="heat",
        side="left",
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=source_y,
    )
    target_port = node_port(
        target,
        port_id=f"{target.id}:akm-heat-in",
        carrier="heat",
        side="left",
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=target_y,
    )
    return rounded_orthogonal_path(
        source_port,
        target_port,
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        lane_x=lane_x,
        corner_radius=16.0,
    )


def _chp_ac_path(
    source: TopologyNode,
    target: TopologyNode,
    *,
    source_y: float,
    target_y: float,
    horizontal_lane_y: float,
    local_lane_x: float,
    left_lane_x: float,
    canvas_height: float,
) -> str:
    """Faltet BHKW→AC als H-V-H-V-H-Pfad.

    Der Strom verlässt das BHKW rechts, steigt in die reservierte Halbzeile,
    quert nach links zum ehemaligen BHKW-Wärmekorridor und trifft die
    Strompille abschließend von links.
    """

    source_port = node_port(
        source, port_id=f"{source.id}:power-out", carrier="ac", side="right",
        canvas_width=CANVAS_WIDTH, canvas_height=canvas_height,
        position_y=source_y,
    )
    target_port = node_port(
        target, port_id=f"{source.id}:ac-in", carrier="ac", side="left",
        canvas_width=CANVAS_WIDTH, canvas_height=canvas_height,
        position_y=target_y,
    )
    start = source_port.x * CANVAS_WIDTH, source_port.y * canvas_height
    end = target_port.x * CANVAS_WIDTH, target_port.y * canvas_height
    return rounded_polyline_path((
        start,
        (local_lane_x, start[1]),
        (local_lane_x, horizontal_lane_y),
        (left_lane_x, horizontal_lane_y),
        (left_lane_x, end[1]),
        end,
    ), corner_radius=12.0)


def _rounded_dc_path(
    source: TopologyNode,
    target: TopologyNode,
    *,
    source_y: float,
    target_y: float,
    lane_x: float,
    canvas_height: float,
) -> str:
    """Verbindet DC-Ports direkt oder über die vorgegebene vertikale Umlenkspur."""

    if math.isclose(source_y, target_y, abs_tol=1e-9):
        return _ports_path(
            source, target, "dc", y=source_y,
            canvas_height=canvas_height,
        )

    return _rounded_hvh_path(
        source, target, "dc", source_y=source_y, target_y=target_y,
        lane_x=lane_x, canvas_height=canvas_height,
    )


def _rounded_hvh_path(
    source: TopologyNode,
    target: TopologyNode,
    carrier: str,
    *,
    source_y: float,
    target_y: float,
    lane_x: float,
    canvas_height: float,
) -> str:
    """Erzeugt eine erzwungene Rechts→Links-H-V-H-Verbindung."""

    source_port = node_port(
        source, port_id=f"{source.id}:{carrier}-out", carrier=carrier,
        side="right", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height, position_y=source_y,
    )
    target_port = node_port(
        target, port_id=f"{target.id}:{carrier}-in", carrier=carrier,
        side="left", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height, position_y=target_y,
    )
    return rounded_orthogonal_path(
        source_port, target_port,
        canvas_width=CANVAS_WIDTH, canvas_height=canvas_height,
        lane_x=lane_x, corner_radius=16.0,
    )


def _dc_elyz_path(
    source: TopologyNode,
    target: TopologyNode,
    *,
    source_y: float,
    target_y: float,
    right_lane_x: float,
    left_lane_x: float,
    bridge_y: float,
    canvas_height: float,
) -> str:
    """Führt DC rechts aus der Pille und von links in den Elektrolyseur."""

    source_port = node_port(
        source, port_id=f"{source.id}:elyz-dc-out", carrier="dc",
        side="right", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height, position_y=source_y,
    )
    target_port = node_port(
        target, port_id=f"{target.id}:dc-in", carrier="dc",
        side="left", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height, position_y=target_y,
    )
    start = source_port.x * CANVAS_WIDTH, source_port.y * canvas_height
    end = target_port.x * CANVAS_WIDTH, target_port.y * canvas_height
    return rounded_polyline_path((
        start,
        (right_lane_x, start[1]),
        (right_lane_x, bridge_y),
        (left_lane_x, bridge_y),
        (left_lane_x, end[1]),
        end,
    ), corner_radius=12.0)


def _rounded_resource_path(
    source: TopologyNode,
    target: TopologyNode,
    carrier: str,
    *,
    canvas_height: float,
    target_y: float | None = None,
    lane_x: float,
) -> str:
    """Verbindet eine gemeinsame externe Quelle über eine H-V-H-Leitung."""

    source_port = node_port(
        source, port_id=f"{source.id}:{target.id}:out", carrier=carrier,
        side="right", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height, position_y=source.y,
    )
    target_port = node_port(
        target, port_id=f"{source.id}:{target.id}:in", carrier=carrier,
        side="left", canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=target.y if target_y is None else target_y,
    )
    return rounded_orthogonal_path(
        source_port, target_port,
        canvas_width=CANVAS_WIDTH, canvas_height=canvas_height,
        lane_x=lane_x,
        corner_radius=12.0,
    )


def _external_source_viewport_path(
    source: TopologyNode,
    carrier: str,
    *,
    canvas_height: float,
    source_y: float | None = None,
) -> str:
    """Horizontale Eintrittskante einer eQ-Quelle vom linken Viewportrand."""

    topology_carrier = {
        "power": "ac", "ac": "ac", "dc": "dc", "heat": "heat",
        "cool": "cooling", "cooling": "cooling", "hydrogen": "hydrogen",
    }.get(carrier, "ac")
    port = node_port(
        source,
        port_id=f"viewport:{source.id}:in",
        carrier=topology_carrier,
        side="left",
        canvas_width=CANVAS_WIDTH,
        canvas_height=canvas_height,
        position_y=source.y if source_y is None else source_y,
    )
    y = port.y * canvas_height
    return f"M 0.000 {y:.3f} L {port.x * CANVAS_WIDTH:.3f} {y:.3f}"


