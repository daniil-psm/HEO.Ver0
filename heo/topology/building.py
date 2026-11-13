"""Gebäudekomponenten, Anschlussregeln und dezentrale Ringelemente der HEO-Topologie."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from heo.model.building_supply import central_connections, cooling_supply
from heo.model.devices import (
    HEO_DECENTRAL_DEVICE_CATALOG, building_has_automatic_dhw_storage,
    decentral_device_codes, normalize_building_heater,
)
from heo.display.device_labels import decentral_device_abbreviation
from heo.topology.definitions import COLORS
from heo.topology.geometry import CANVAS_WIDTH
from heo.topology.model import TopologyNode
from heo.topology.sizing import topology_node_radius

BUILDING_SLOT_CHOICES = {
    "pv": ("PV",),
    "stc": ("STC",),
    "heater": decentral_device_codes("heater"),
    "dhw": ("EH_DHW",),
    "dhw_storage": ("TES_DHW",),
    "battery": ("BAT",),
    "ev": ("EV",),
    "heat_storage": ("TES",),
    "cooling": ("CC",),
}

# Energieträgerfarbe der kleinen Anschlusspunkte eines Gebäudes. Die
# Zuordnung beschreibt den Hauptenergieträger der dezentralen Komponente am
# Gebäude: PV, Batterie und Fahrzeugbatterie liegen auf DC; thermische
# Komponenten liegen am jeweiligen Wärme- oder Kälteträger.
BUILDING_SLOT_CARRIERS = {
    "pv": "dc",
    "stc": "heat",
    "heater": "heat",
    # Der Durchlauferhitzer erhält einen eigenen Trinkwarmwasser-Badge. Sein
    # elektrischer Bedarf bleibt Teil der internen Gebäudebilanz.
    "dhw": "dhw",
    "dhw_storage": "dhw",
    "battery": "dc",
    "ev": "dc",
    "heat_storage": "heat",
    "cooling": "cool",
}

# Fachliche Kandidatengruppen der Gebäude-UI.  Die technischen CSV-Slots
# bleiben absichtlich erhalten; diese Gruppierung beschreibt dagegen, welche
# Auswahl ein Mensch an einem Energieanschluss des Gebäudes erhält.
BUILDING_CARRIER_CANDIDATES = {
    "dc": ("PV", "BAT", "EV"),
    "heat": (
        "STC", "TES", "HP", "GHP", "BHP", "H2HP", "OHP", "BOI",
        "BBOI", "OBOI", "H2BOI", "CHP", "FC", "DH", "EH",
    ),
    "dhw": ("EH_DHW",),
    "cooling": ("CC",),
}

BUILDING_CARRIER_SLOTS = {
    "dc": ("pv", "battery", "ev"),
    "heat": ("stc", "heater", "heat_storage"),
    "dhw": ("dhw",),
    "cooling": ("cooling",),
}

def building_available_candidates(
    row: Mapping[str, Any], carrier: str,
) -> tuple[str, ...]:
    """Liefert ausschließlich fachlich zulässige Gebäudekandidaten.

    Ein Heizsystem ist ein exklusives Systemslot. PV, Batterie, EV,
    Solarthermie, Warmwasserdurchlauferhitzer und Speicher können dagegen
    jeweils zusätzlich gewählt werden. Eine lokale KKM wird im Referenz-DG
    nur für Gebäude ohne Wärmenetzanschluss ausgelegt.
    """

    candidates = BUILDING_CARRIER_CANDIDATES.get(carrier, ())
    heater = normalize_building_heater(row.get("heater"))
    selected_by_slot = {
        slot: _building_badge_value(dict(row), slot)
        for slot in BUILDING_SLOT_CHOICES
    }
    available: list[str] = []
    for code in candidates:
        metadata = HEO_DECENTRAL_DEVICE_CATALOG.get(code, {})
        slot = str(metadata.get("slot") or "")
        if slot == "cooling" and heater in {None, "", "heat_grid"}:
            continue
        if not slot:
            continue
        if selected_by_slot.get(slot):
            continue
        available.append(code)
    return tuple(available)


def building_slot_for_candidate(code: str) -> str | None:
    """Liefert den CSV-Slot eines dezentralen Kandidaten."""

    slot = HEO_DECENTRAL_DEVICE_CATALOG.get(code, {}).get("slot")
    return str(slot) if slot in BUILDING_SLOT_CHOICES else None


def building_ring_items(
    row: Mapping[str, Any], *, include_available: bool = True,
) -> tuple[tuple[str, str, str], ...]:
    """Erzeugt die zentrale Reihenfolge der sichtbaren Gebäude-Ringelemente.

    Ein Eintrag ist ``(Schlüssel, Gerätecode, Energieträger)``. Leere Codes
    kennzeichnen freie Auswahlkreise; belegte Einträge sind anklickbare lokale
    Komponenten. ``heat_grid`` und zentrale Anschlüsse erscheinen bewusst
    nicht als Ringelemente, sondern ausschließlich als Quartierskante.
    """

    normalized_row = dict(row)
    result: list[tuple[str, str, str]] = []
    cooling_item: tuple[str, str, str] | None = None
    for slot in BUILDING_SLOT_CHOICES:
        code = _building_badge_value(normalized_row, slot)
        if code:
            item = (slot, code, BUILDING_SLOT_CARRIERS[slot])
            # Der freie Kälte-Kreis liegt am Ende des Rings. Eine gewählte
            # KKM ersetzt ihn an genau dieser Stelle, statt anschließend
            # anhand ihres technischen CSV-Slots in die Liste einzusortieren.
            if slot == "cooling":
                cooling_item = item
            else:
                result.append(item)
    if include_available:
        for carrier in ("dc", "heat", "dhw", "cooling"):
            if building_available_candidates(normalized_row, carrier):
                result.append((carrier, "", carrier))
    if cooling_item is not None:
        result.append(cooling_item)
    return tuple(result)


@dataclass(frozen=True)
class BuildingRingPlacement:
    """Renderer-unabhängiger Platz auf dem Ring eines Gebäudes.

    ``x`` und ``y`` sind lokale Pixelversätze vom Mittelpunkt des Gebäudes.
    Renderer müssen diese Werte innerhalb eines gleichmäßig skalierten
    Gebäudegruppen-Rahmens verwenden. Eine globale Prozentposition würde bei
    nicht proportionalen Viewports aus dem Kreis einen Ellipsenversatz machen
    und Badges sichtbar vom Gebäude lösen.
    """

    key: str
    code: str
    carrier: str
    slot_index: int
    angle: float
    x: float
    y: float


def building_ring_placements(
    row: Mapping[str, Any], *, radius: float,
    include_available: bool = True,
) -> tuple[BuildingRingPlacement, ...]:
    """Ordnet alle sichtbaren Ringelemente in gleichen Winkelabständen an.

    Die semantische Slot-Reihenfolge bleibt stabil. Unbelegte, unsichtbare
    Slots reservieren jedoch keinen Winkel mehr, damit im Ring keine optischen
    Lücken entstehen.
    """

    normalized_row = dict(row)
    slots = tuple(BUILDING_SLOT_CHOICES)
    by_index: dict[int, tuple[str, str, str]] = {}
    assigned_codes: set[str] = set()
    for slot_index, slot in enumerate(slots):
        code = _building_badge_value(normalized_row, slot)
        if not code:
            continue
        by_index[slot_index] = (slot, code, BUILDING_SLOT_CARRIERS[slot])
        assigned_codes.add(code)

    # Normalisierte Optimierungsergebnisse dürfen zusätzliche dezentrale
    # Codes liefern, auch wenn deren ursprüngliches CSV-Feld nicht vorliegt.
    extra_codes = [
        str(item.get("code") or "")
        for item in (normalized_row.get("decentral_devices") or [])
        if isinstance(item, Mapping) and item.get("code")
        and str(item.get("code")) not in assigned_codes
    ]
    for code in extra_codes:
        preferred_slot = building_slot_for_candidate(code)
        candidate_indices = [
            index for index, slot in enumerate(slots)
            if index not in by_index and slot == preferred_slot
        ] or [index for index in range(len(slots)) if index not in by_index]
        if not candidate_indices:
            break
        slot_index = candidate_indices[0]
        slot = slots[slot_index]
        by_index[slot_index] = (slot, code, BUILDING_SLOT_CARRIERS[slot])

    if include_available:
        for carrier in ("dc", "heat", "dhw", "cooling"):
            if not building_available_candidates(normalized_row, carrier):
                continue
            candidate_indices = [
                index for index, slot in enumerate(slots)
                if index not in by_index
                and slot in BUILDING_CARRIER_SLOTS[carrier]
            ]
            if candidate_indices:
                by_index[candidate_indices[0]] = (carrier, "", carrier)

    result: list[BuildingRingPlacement] = []
    ordered = sorted(by_index.items())
    count = len(ordered)
    for display_index, (slot_index, (key, code, carrier)) in enumerate(ordered):
        angle = -90.0 + 360.0 * display_index / count
        radians = math.radians(angle)
        result.append(BuildingRingPlacement(
            key=key,
            code=code,
            carrier=carrier,
            slot_index=slot_index,
            angle=angle,
            x=math.cos(radians) * radius,
            y=math.sin(radians) * radius,
        ))
    return tuple(result)


def apply_building_candidate(
    row: dict[str, Any], slot: str, code: str | None,
) -> bool:
    """Überträgt eine Kandidatenwahl konsistent in einen Gebäude-CSV-Datensatz.

    Der Rückgabewert zeigt an, ob die Wahl fachlich zulässig war. Die Funktion
    ist absichtlich UI-frei und wird sowohl von Callbacks als auch späteren
    Import-/Vorschaupfaden verwendet.
    """

    # TES_DHW wird aus Heizsystem und DLE-Zustand abgeleitet und darf nicht
    # unabhängig davon hinzugefügt oder entfernt werden.
    if slot == "dhw_storage":
        return False
    choices = BUILDING_SLOT_CHOICES.get(slot)
    if choices is None:
        return False
    if code is not None and code not in choices:
        return False

    if slot == "pv":
        row["f_PV1"], row["f_PV2"] = ((0.2, 0.2) if code else (0.0, 0.0))
    elif slot == "stc":
        row["f_STC"] = 0.2 if code else 0.0
    elif slot == "heater":
        row["heater"] = normalize_building_heater(code) if code else "heat_grid"
    elif slot == "dhw":
        row["dhw"], row["dhw_heater"] = bool(code), "EH_DHW" if code else ""
    elif slot == "battery":
        row["f_BAT"] = 1.0 if code else 0.0
    elif slot == "ev":
        row["EV"] = (float(row.get("EV") or 1.0) if code else 0.0)
    elif slot == "heat_storage":
        row["f_TES"] = 35.0 if code else 0.0
    elif slot == "cooling":
        if row.get("heater") in {None, "", "heat_grid"}:
            return False
        row["cooling"] = bool(code)
    if slot in {"heater", "cooling"}:
        for key in ("cooling_supply", "_cooling_decentral", "_central_cooling_opt_out"):
            row.pop(key, None)
    return True


def synchronize_central_cooling(
    building_state: dict[str, Any] | None, *, enabled: bool,
) -> dict[str, Any]:
    """Die Erzeugerauswahl verändert den DG-Gebäudekühlbedarf nicht."""
    state = dict(building_state or {})
    state["rows"] = [dict(row) for row in state.get("rows") or []]
    return state
def _building_has_heat(row: dict[str, Any]) -> bool:
    """Prüft den zentralen Raumwärmeanschluss anhand expliziter Träger oder der Gebäuderegeln."""

    if "central_carriers" in row:
        return "heat" in set(row.get("central_carriers") or [])
    return central_connections(row)["heat"]


def _building_has_central_cooling(row: dict[str, Any]) -> bool:
    """Prüft den zentralen Kälteanschluss anhand expliziter Träger oder der Gebäuderegeln."""

    if "central_carriers" in row:
        return "cooling" in set(row.get("central_carriers") or [])
    return central_connections(row)["cooling"]


def _building_has_central_dhw(row: Mapping[str, Any]) -> bool:
    """Prüft die eigenständige zentrale Trinkwarmwasserversorgung."""

    if "central_carriers" in row:
        return "dhw" in set(row.get("central_carriers") or [])
    return central_connections(row)["dhw"]


def _building_badge_value(row: dict[str, Any], slot: str) -> str | None:
    """Liefert den ausgewählten dezentralen Gerätecode eines Gebäudeslots oder einen leeren Text."""

    normalized_codes = [
        str(item.get("code") or "")
        for item in (row.get("decentral_devices") or [])
        if isinstance(item, dict)
    ]
    slot_codes = BUILDING_SLOT_CHOICES.get(slot, ())
    normalized_match = next(
        (
            "EH_DHW" if code == "DL" and slot == "dhw" else code
            for code in normalized_codes if code in slot_codes or (
                code == "DL" and slot == "dhw"
            )
        ),
        None,
    )
    if normalized_match:
        return normalized_match
    if slot == "pv" and float(row.get("f_PV1") or 0) + float(row.get("f_PV2") or 0) > 0:
        return "PV"
    if slot == "stc" and float(row.get("f_STC") or 0) > 0:
        return "STC"
    if slot == "heater" and row.get("heater") not in {None, "", "heat_grid"}:
        return normalize_building_heater(row.get("heater"))
    if slot == "dhw" and bool(row.get("dhw")):
        return "EH_DHW"
    if slot == "battery" and float(row.get("f_BAT") or 0) > 0:
        return "BAT"
    if slot == "ev" and bool(row.get("EV")):
        return "EV"
    if slot == "heat_storage" and float(row.get("f_TES") or 0) > 0:
        return "TES"
    if slot == "dhw_storage" and building_has_automatic_dhw_storage(row):
        return "TES_DHW"
    if slot == "cooling" and cooling_supply(row) == "decentral":
        return "CC"
    return None


def _building_is_decentral(row: dict[str, Any]) -> bool:
    """Teilt Gebäude für die beiden kompakten Sammel-Nodes ein."""

    return any(
        _building_badge_value(row, slot)
        for slot in BUILDING_SLOT_CHOICES
    )


def _visible_building_plan(
    buildings: Sequence[Mapping[str, Any]],
    *,
    capacity: int,
    include_editing_placeholder: bool,
) -> tuple[list[dict[str, Any]], dict[str, tuple[int, ...]]]:
    """Plant sichtbare Gebäude, Sammel-Nodes und optionalen Plus-Platz.

    Nur tatsächlich benötigte Sammel-Nodes belegen Plätze. Der editierbare
    Plus-Platz zählt ausschließlich im Konfigurator zur Kapazität.
    """

    rows = [dict(row) for row in buildings]
    available = max(0, int(capacity) - int(include_editing_placeholder))
    if len(rows) <= available:
        return rows, {}

    for visible_count in range(min(len(rows), available), -1, -1):
        overflow = rows[visible_count:]
        groups: dict[str, tuple[int, ...]] = {}
        for group_name, is_decentral in (("central", False), ("decentral", True)):
            members = tuple(
                int(row.get("uid", index + visible_count))
                for index, row in enumerate(overflow)
                if _building_is_decentral(row) is is_decentral
            )
            if members:
                groups[group_name] = members
        if visible_count + len(groups) <= available:
            return rows[:visible_count], groups

    return [], {}
def _building_badge_nodes(
    buildings: Sequence[Mapping[str, Any]],
    nodes: Mapping[str, TopologyNode],
    *,
    canvas_height: float,
    ring_placements: Mapping[int, Sequence[BuildingRingPlacement]],
    standard_diameter: float,
) -> dict[str, TopologyNode]:
    """Erzeugt dezentrale Gebäude-Nodes aus derselben Gebäude-Semantik."""

    result: dict[str, TopologyNode] = {}
    for index, source_row in enumerate(buildings):
        row = dict(source_row)
        uid = int(row.get("uid", index))
        parent_id = f"BUILDING:{uid}"
        parent = nodes.get(parent_id)
        if parent is None:
            continue
        placements = ring_placements.get(uid, ())
        for placement in placements:
            slot, code = placement.key, placement.code
            if not code:
                continue
            slot_index = placement.slot_index
            carrier = next(
                (
                    BUILDING_SLOT_CARRIERS[candidate_slot]
                    for candidate_slot, choices in BUILDING_SLOT_CHOICES.items()
                    if code in choices
                ),
                {
                    # DL exportiert Wärme. Die Badge-Farbe folgt dem Export-
                    # Energieträger und nicht dem elektrischen Hilfsbedarf.
                    "DL": "heat", "EH_DHW": "heat", "EV": "dc",
                    "PV": "dc", "BAT": "dc", "CC": "cool",
                }.get(code, BUILDING_SLOT_CARRIERS[slot]),
            )
            node_id = f"{parent_id}:{code}:{slot_index}"
            result[node_id] = TopologyNode(
                id=node_id,
                title=decentral_device_abbreviation(code),
                icon="",
                group={
                    "power": "ac", "dc": "dc", "heat": "thermal",
                    "cool": "cooling",
                }.get(carrier, "load"),
                role="source",
                color=COLORS.get(carrier, COLORS["neutral"]),
                radius=topology_node_radius("badge", standard_diameter),
                x=parent.x + placement.x / CANVAS_WIDTH,
                y=parent.y + placement.y / canvas_height,
                device_code=code,
                shape="badge",
                parent_id=parent_id,
                z_index=30 + slot_index,
            )
    return result
