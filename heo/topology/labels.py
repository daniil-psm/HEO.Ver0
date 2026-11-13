"""Zentrale Beschriftungsstufen für Knoten und Komponentenauswahl der HEO-Topologie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from heo.model.devices import HEO_DECENTRAL_DEVICE_CATALOG, TOPOLOGY_AUXILIARY_LABELS
from heo.display.device_labels import decentral_device_abbreviation
from heo.topology.definitions import CENTRAL_DEVICES
from heo.topology.model import TopologyNode

@dataclass(frozen=True)
class NodeLabelVariants:
    """Die drei zentralen Beschriftungsstufen einer Topologie-Node."""

    full: str
    wrapped: str
    short: str


def _node_label_variants(
    full_label: str, wrapped_label: str, abbreviation: str,
) -> NodeLabelVariants:
    """Normalisiert die drei Stufen und vermeidet leere Varianten."""

    full = str(full_label or abbreviation)
    wrapped = str(wrapped_label or full)
    short = str(abbreviation or wrapped)
    return NodeLabelVariants(full=full, wrapped=wrapped, short=short)


def central_node_label_variants(code: str) -> NodeLabelVariants:
    """Vollname, definierter Umbruch und Kürzel einer zentralen Komponente."""

    metadata = CENTRAL_DEVICES[code]
    labels = metadata.get("topology_labels") or {}
    full = str(labels.get("full") or metadata.get("full_name") or metadata["label"])
    return _node_label_variants(
        full,
        str(labels.get("wrapped") or full),
        str(labels.get("short") or metadata.get("abbreviation") or metadata["label"]),
    )


def auxiliary_node_label_variants(node_id: str) -> NodeLabelVariants:
    """Entsprechende Beschriftungsstufen für Netz- und Bezugs-Nodes."""

    labels = TOPOLOGY_AUXILIARY_LABELS[node_id]
    return _node_label_variants(
        labels["full"], labels["wrapped"], labels["short"],
    )


def candidate_label_variants(
    code: str, *, decentral: bool = False,
) -> NodeLabelVariants:
    """Liefert kontextgerechte Labelstufen vor dem Hinzufügen einer Node."""

    if decentral:
        metadata = HEO_DECENTRAL_DEVICE_CATALOG.get(code, {})
        labels = metadata.get("candidate_labels") or metadata.get("topology_labels") or {}
        full = str(labels.get("full") or metadata.get("full_name") or decentral_device_abbreviation(code))
        abbreviation = str(labels.get("short") or metadata.get("abbreviation") or code)
        return _node_label_variants(
            full,
            str(labels.get("wrapped") or full),
            abbreviation,
        )

    if code in CENTRAL_DEVICES:
        metadata = CENTRAL_DEVICES[code]
        labels = metadata.get("candidate_labels") or metadata.get("topology_labels") or {}
        return _node_label_variants(
            str(labels.get("full") or metadata.get("full_name") or metadata["label"]),
            str(labels.get("wrapped") or labels.get("full") or metadata["label"]),
            str(labels.get("short") or metadata.get("abbreviation") or metadata["label"]),
        )
    if code in TOPOLOGY_AUXILIARY_LABELS:
        return auxiliary_node_label_variants(code)
    if code == "BUILDING":
        return _node_label_variants("Gebäude", "Gebäude", "Gebäude")
    metadata = HEO_DECENTRAL_DEVICE_CATALOG.get(code, {})
    labels = metadata.get("candidate_labels") or metadata.get("topology_labels") or {}
    full = str(labels.get("full") or metadata.get("full_name") or decentral_device_abbreviation(code))
    abbreviation = str(labels.get("short") or metadata.get("abbreviation") or code)
    return _node_label_variants(
        full,
        str(labels.get("wrapped") or full),
        abbreviation,
    )


def node_label_variants(node: TopologyNode) -> NodeLabelVariants:
    """Liefert die an Renderer zu übergebenden Beschriftungsstufen einer Node."""

    return _node_label_variants(
        node.label_full or node.title,
        node.label_wrapped or node.title,
        node.label_short or node.title,
    )


def _fitted_node_label(
    full_label: str, abbreviation: str, diameter: float
) -> str:
    """Zeigt den umgebrochenen Namen oder bei Platzmangel das Kürzel."""

    lines = full_label.split("\n")
    estimated_characters = max(3, int(diameter / 8.0))
    if len(lines) <= 3 and max(map(len, lines), default=0) <= estimated_characters:
        return full_label
    return abbreviation


def _central_node_label(code: str, diameter: float) -> str:
    """Nutzt den vollen Namen, solange er in den Rasterkreis passt."""

    variants = central_node_label_variants(code)
    return _fitted_node_label(
        variants.wrapped,
        variants.short,
        diameter,
    )


def _auxiliary_node_label(node_id: str, diameter: float) -> str:
    """Wendet dieselbe Platzlogik auf Netz- und Bezugs-Nodes an."""

    variants = auxiliary_node_label_variants(node_id)
    return _fitted_node_label(variants.wrapped, variants.short, diameter)


def _building_node_label(
    building_name: str, building_id: Any, diameter: float
) -> str:
    """Zeigt ausschließlich einen passenden Namen, sonst nur die Gebäude-ID."""

    fallback = str(building_id)
    name = str(building_name or "").strip()
    if not name:
        return fallback
    wrapped_name = _wrapped_building_name(name, diameter)
    return wrapped_name if wrapped_name is not None else fallback


def _wrapped_building_name(
    building_name: str,
    diameter: float,
    *,
    maximum_lines: int = 3,
) -> str | None:
    """Bricht einen Gebäudenamen um, solange er vollständig in die Node passt."""

    characters_per_line = max(3, int(diameter / 8.0))
    line_break = "__HEO_LINE_BREAK__"
    words = str(building_name or "").replace("\n", f" {line_break} ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        if word == line_break:
            if current:
                lines.append(current)
                current = ""
            continue
        if len(word) > characters_per_line:
            return None
        candidate = f"{current} {word}".strip()
        if len(candidate) <= characters_per_line:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) >= maximum_lines:
            return None
    if current:
        lines.append(current)
    if not lines or len(lines) > maximum_lines:
        return None
    return "\n".join(lines)
