"""Responsive Größenregeln für HEO-Topologieknoten."""

from __future__ import annotations
from dataclasses import dataclass
from heo.topology.definitions import NodeSizeProfile

# Referenzmaße für Gebäude und Badges; das responsive Raster löst die
# tatsächlich verwendeten Abstände je Topologieszene auf.
CENTRAL_STACK_STEP = 66.0
STACK_VERTICAL_OVERLAP_RATIO = 0.8
MAX_BUILDING_COLUMNS = 2
BUILDING_NODE_RADIUS = 48.0
BUILDING_BADGE_RADIUS = 17.0
CANDIDATE_RADIUS = 42.0
# Freier Abstand zwischen zwei Gebäudeumrissen: drei kleine Kreisradien.
BUILDING_STACK_STEP = 2 * BUILDING_NODE_RADIUS + 3 * BUILDING_BADGE_RADIUS


@dataclass(frozen=True)
class NodeSizeDefinition:
    """Responsive Größenregel einer Node-Kategorie.

    Der Rasterlöser liefert nur den Standarddurchmesser. Diese Definition
    übersetzt ihn zentral in Radien für Komponenten, Pillenenden, Gebäude und
    Badges. Dadurch bleiben besondere Gebäudegrößen bewusst erhalten.
    """

    content_ratio: float = 0.98
    radius_ratio: float = 0.5
    minimum_radius_ratio: float = 0.0
    badge_clearance: float = 0.0
    fixed_radius: float | None = None


NODE_SIZE_DEFINITIONS: dict[NodeSizeProfile, NodeSizeDefinition] = {
    # Komponenten und Pillenenden haben stets denselben Radius.
    "standard": NodeSizeDefinition(),
    # Gebäude lassen Platz für ihre dezentralen Badges und dürfen daher
    # kleiner als eine Standard-Node werden.
    "building": NodeSizeDefinition(
        minimum_radius_ratio=0.30,
        badge_clearance=BUILDING_BADGE_RADIUS,
    ),
    "badge": NodeSizeDefinition(fixed_radius=BUILDING_BADGE_RADIUS),
}


def topology_node_radius(
    profile: NodeSizeProfile, standard_diameter: float = 0.0,
) -> float:
    """Löst einen kanonischen Node-Radius aus dem responsiven Raster auf."""

    definition = NODE_SIZE_DEFINITIONS[profile]
    if definition.fixed_radius is not None:
        if profile == "badge" and standard_diameter > 0:
            standard_radius = standard_diameter / 2
            return min(definition.fixed_radius, standard_radius * 0.32)
        return definition.fixed_radius
    radius = standard_diameter * definition.radius_ratio
    if profile == "building":
        badge_radius = topology_node_radius("badge", standard_diameter)
        radius = max(
            standard_diameter * definition.minimum_radius_ratio,
            radius - badge_radius,
        )
    return radius


def topology_node_content_ratio(profile: NodeSizeProfile = "standard") -> float:
    """Anteil der kleineren Rasterachse, den eine Node-Kategorie belegt."""

    return NODE_SIZE_DEFINITIONS[profile].content_ratio
