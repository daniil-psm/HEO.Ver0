"""Fachliche Node-Definitionen, Energieträger, Geräteslots und Auswahlregeln der HEO-Topologie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from heo.display.device_labels import central_device_abbreviation
from heo.model.devices import HEO_CENTRAL_DEVICE_CATALOG

EnergyCarrier = Literal[
    "ac", "power", "dc", "heat", "dhw", "cool", "cooling",
    "gas", "hydrogen", "biomass", "waste", "oil", "neutral",
]
NodeGroup = Literal["ac", "dc", "thermal", "cooling", "load"]
NodeRole = Literal["source", "bus", "converter", "storage", "consumer", "sink"]
NodeShape = Literal["circle", "pill", "building", "badge"]
NodeSizeProfile = Literal["standard", "building", "badge"]
PortSide = Literal["left", "right", "top", "bottom"]
EdgeRouting = Literal["bezier", "horizontal", "horizontal_tangent"]


@dataclass(frozen=True)
class NodeDefinition:
    """Kanonische, positionsunabhängige Definition einer Topologie-Node."""

    carrier: str
    shape: NodeShape = "circle"
    role: NodeRole = "source"
    label_kind: Literal["central", "auxiliary", "dynamic"] = "dynamic"
    size_profile: NodeSizeProfile = "standard"


COLORS: dict[str, str] = {
    "ac": "#f4b632",
    "dc": "#178859",
    "heat": "#f15342",
    "dhw": "#f15342",
    "cooling": "#2270e6",
    "neutral": "#43564d",
    # Kanonische Alias-Namen der Konfigurator- und Ergebnisansichten.
    "power": "#f4b632",
    "cool": "#2270e6",
    # Brenn- und Rohstoffe: getrennte Farbfamilien statt ähnlicher Brauntöne.
    # Gas bleibt warm, Abfall wird violett und Öl erhält einen kühlen Stahlton.
    "gas": "#d97706",
    "hydrogen": "#71c4e8",
    "biomass": "#75c66a",
    "waste": "#b05cc6",
    "oil": "#607d8b",
}

CARRIER_LABELS: dict[str, str] = {
    "ac": "AC",
    "power": "AC",
    "dc": "DC",
    "heat": "Raumwärme",
    "dhw": "Trinkwarmwasser",
    "cool": "Raumkälte",
    "cooling": "Raumkälte",
    "gas": "Erdgas",
    "hydrogen": "Wasserstoff",
    "biomass": "Biomasse",
    "waste": "Abfall",
    "oil": "Heizöl",
    "neutral": "Umgebungsenergie",
}


def canonical_energy_carrier(carrier: str) -> str:
    """Vereinheitlicht die Aliasnamen aller Topology-Ansichten."""

    return {"power": "ac", "cool": "cooling"}.get(carrier, carrier)


def energy_carrier_label(carrier: str) -> str:
    """Liefert die zentrale, deutschsprachige Energieträgerbezeichnung."""

    canonical = canonical_energy_carrier(carrier)
    return CARRIER_LABELS.get(canonical, str(carrier))


def energy_carrier_color(carrier: str) -> str:
    """Liefert dieselbe Farbe für Topologien, Legenden und Dokumentation."""

    canonical = canonical_energy_carrier(carrier)
    return COLORS.get(canonical, COLORS["neutral"])


# Gemeinsame fachliche Topologie-Metadaten. Tabs dürfen diese Daten verwenden,
# aber nicht durch eigene Kopien oder abweichende Reihenfolgen überschreiben.
CENTRAL_DEVICES: dict[str, dict[str, Any]] = {
    code: {
        **metadata,
        "label": central_device_abbreviation(code),
        **(
            {"primary_carrier": "heat"}
            if metadata.get("slot") == "coupled_source" else {}
        ),
    }
    for code, metadata in HEO_CENTRAL_DEVICE_CATALOG.items()
}
SLOT_CANDIDATES = {
    # Der AC-Einstieg ist ein gemeinsamer, verschachtelter Stack. CHP kann
    # darüber oder über den Wärmeerzeuger-+-Slot gewählt werden, wird aber
    # immer im ``coupled_source``-Stack abgelegt.
    "electric_source": ("GRID", "CHP", "BCHP", "WCHP"),
    "coupled_source": ("CHP", "BCHP", "WCHP"),
    "dc_source": ("PV", "WT", "WAT"),
    "dc_storage": ("BAT",),
    "heat_source": (
        "HP", "GROUNDHP", "EB", "STC", "GHP", "BOI", "WBOI", "BBOI",
        "CHP", "BCHP", "WCHP",
    ),
    "heat_storage": ("TES",),
    "cool_source": ("CC", "AC"),
    "cool_storage": ("CTES",),
    "hydrogen_converter": ("SAB", "FC", "ELYZ"),
    "hydrogen_storage": ("H2S",),
    "gas_storage": ("GS",),
}

# Der linke H₂-/Gasblock zeigt bewusst fünf getrennte Ein-Kandidaten-
# Bedienplätze. Die Schlüssel identifizieren nur den freien Platz im Layout;
# nach der Auswahl wird jedes Gerät über seinen regulären fachlichen Slot
# aus ``CENTRAL_DEVICES`` in den Konfiguratorzustand aufgenommen.
INDIVIDUAL_COMPONENT_CONTROLS: dict[str, str] = {
    f"{CENTRAL_DEVICES[code]['slot']}:{code}": code
    for code in ("SAB", "FC", "ELYZ", "H2S", "GS")
}

CENTRAL_SLOT_KEYS = tuple(
    slot for slot in SLOT_CANDIDATES if slot != "electric_source"
)

# Nur zentrale HEO-Geräte werden als eigenständige Kandidaten angeboten.
# Gebäudegeräte wie H2BOI bleiben auf ihre Gebäude-Slots beschränkt.
CONFIGURABLE_CENTRAL_CODES = tuple(CENTRAL_DEVICES)
RESOURCE_FOR_DEVICE = {
    "CHP": ("GAS_IMPORT", "gas"),
    "BOI": ("GAS_IMPORT", "gas"),
    "GHP": ("GAS_IMPORT", "gas"),
    "BCHP": ("BIOMASS_IMPORT", "biomass"),
    "BBOI": ("BIOMASS_IMPORT", "biomass"),
    "WCHP": ("WASTE_IMPORT", "waste"),
    "WBOI": ("WASTE_IMPORT", "waste"),
}


def add_device_to_slot_order(state: dict[str, Any], code: str) -> None:
    """Ergänzt Geräteauswahl und Slot-Reihenfolge in-place; unbekannte Geräte bleiben unberücksichtigt."""

    if code not in CONFIGURABLE_CENTRAL_CODES:
        return
    selected = list(state.get("central_devices") or [])
    if code not in selected:
        selected.append(code)
    order = normalize_slot_order(selected, state.get("slot_order"))
    slot = CENTRAL_DEVICES[code]["slot"]
    if code not in order[slot]:
        order[slot].append(code)
    state["central_devices"] = selected
    state["slot_order"] = order


def remove_device_from_slot_order(state: dict[str, Any], code: str) -> list[str]:
    """Entfernt ein Gerät in-place aus Auswahl und Slot-Reihenfolge."""

    selected = [item for item in state.get("central_devices", []) if item != code]
    state["central_devices"] = selected
    state["slot_order"] = normalize_slot_order(selected, state.get("slot_order"))
    return [code]


def remove_resource_from_slot_order(
    state: dict[str, Any], resource_id: str,
) -> list[str]:
    """Entfernt ressourcenabhängige Geräte in-place und liefert ihre Codes."""

    removed = [
        code for code in state.get("central_devices", [])
        if RESOURCE_FOR_DEVICE.get(code, (None,))[0] == resource_id
    ]
    if not removed:
        return []
    selected = [
        code for code in state.get("central_devices", []) if code not in removed
    ]
    state["central_devices"] = selected
    state["slot_order"] = normalize_slot_order(selected, state.get("slot_order"))
    return removed

# eQ-Quellen werden sichtbar am linken Rand in die Topologie geführt. Das
# Stromnetz folgt derselben Regel wie die Brennstoff- und Abfallquellen.
EXTERNAL_SOURCE_CARRIERS = {
    "GRID": "power",
    # Der H₂-Bezug ist eine eigenständige externe Quelle und erhält – wie
    # Strom-, Gas-, Biomasse- und Abfallbezug – eine sichtbare Eintrittskante
    # vom linken Viewport-Rand.
    "H2_IMPORT": "hydrogen",
    # Heizöl wird im DG ausschließlich von dezentralen Ölkesseln
    # verbraucht. Es bleibt trotzdem eine reguläre eQ der gemeinsamen
    # Topologiesemantik und steht im Quellenstack zwischen Abfall und Erdgas.
    "OIL_IMPORT": "oil",
    **{
        resource_id: carrier
        for resource_id, carrier in RESOURCE_FOR_DEVICE.values()
    },
}

# Sämtliche festen Nodes leiten Erscheinung und Beschriftung aus dieser
# Definition ab. Layoutfunktionen geben nur noch ihre Koordinaten, Größe und
# gegebenenfalls dynamische Gebäudebeschriftung an.
NODE_DEFINITIONS: dict[str, NodeDefinition] = {
    **{
        code: NodeDefinition(
            metadata.get("primary_carrier")
            or (metadata.get("outputs") or metadata.get("inputs") or ("neutral",))[0],
            label_kind="central",
        )
        for code, metadata in CENTRAL_DEVICES.items()
    },
    "GRID": NodeDefinition("power", label_kind="auxiliary"),
    "AC_BUS": NodeDefinition("power", "pill", "bus", "auxiliary"),
    "DC_BUS": NodeDefinition("dc", "pill", "bus", "auxiliary"),
    "INVERTER": NodeDefinition("neutral", "pill", "converter", "auxiliary"),
    "HEAT_GRID": NodeDefinition("heat", "pill", "bus", "auxiliary"),
    "COOL_GRID": NodeDefinition("cool", "pill", "bus", "auxiliary"),
    "LOAD": NodeDefinition("neutral", "pill", "sink", "auxiliary"),
    "GAS_IMPORT": NodeDefinition("gas", label_kind="auxiliary"),
    "GAS_BUS": NodeDefinition("gas", "pill", "bus", "auxiliary"),
    "H2_IMPORT": NodeDefinition("hydrogen", label_kind="auxiliary"),
    "H2_BUS": NodeDefinition("hydrogen", "pill", "bus", "auxiliary"),
    "BIOMASS_IMPORT": NodeDefinition("biomass", label_kind="auxiliary"),
    "WASTE_IMPORT": NodeDefinition("waste", label_kind="auxiliary"),
    "OIL_IMPORT": NodeDefinition("oil", label_kind="auxiliary"),
    "BUILDING": NodeDefinition(
        "neutral", "building", "consumer", size_profile="building"
    ),
    "BUILDING_GROUP": NodeDefinition(
        "neutral", "building", "consumer", size_profile="building"
    ),
}

# Pillen sind keine Sonderfälle der einzelnen Layoutbereiche: Ihre semantische
# Definition ist eine Teilmenge der kanonischen Node-Definitionen.  Dadurch
# können Lage und Ausdehnung im Raster variieren, während Label, Farbe und
# Rolle an einer einzigen Stelle festgelegt bleiben.
PILL_NODE_DEFINITIONS: dict[str, NodeDefinition] = {
    node_id: definition
    for node_id, definition in NODE_DEFINITIONS.items()
    if definition.shape == "pill"
}

COUPLED_SOURCE_CODES = frozenset(SLOT_CANDIDATES["coupled_source"])

# Feste visuelle Reihenfolge der brennstoffgebundenen Wärmeerzeuger. Biomasse
# liegt bewusst vor Abfall; Erdgas bleibt wegen des gemeinsamen Gasbusses am
# unteren Ende des eQ-Blocks.
HEAT_RESOURCE_STACK_ORDER = (
    "BIOMASS_IMPORT", "WASTE_IMPORT", "OIL_IMPORT", "GAS_IMPORT",
)


def normalize_slot_order(
    selected: Sequence[str],
    slot_order: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[str]]:
    """Kanonische Reihenfolge zentraler Komponenten in ihren Topologie-Slots."""

    selected_codes = [code for code in selected if code in CENTRAL_DEVICES]
    selected_set = set(selected_codes)
    source = slot_order or {}
    result: dict[str, list[str]] = {slot: [] for slot in CENTRAL_SLOT_KEYS}
    for slot in CENTRAL_SLOT_KEYS:
        for code in source.get(slot, ()):
            if (
                code in selected_set
                and CENTRAL_DEVICES[code]["slot"] == slot
                and code not in result[slot]
            ):
                result[slot].append(code)
    for code in selected_codes:
        slot = CENTRAL_DEVICES[code]["slot"]
        if code not in result[slot]:
            result[slot].append(code)
    heat_group = {
        "HP": 0, "GROUNDHP": 0, "EB": 0, "STC": 1,
        "GHP": 2, "BOI": 2, "WBOI": 2, "BBOI": 2,
    }
    dc_heat_order = {"HP": 0, "GROUNDHP": 1, "EB": 2}
    resource_group = {"BOI": 0, "GHP": 1, "BBOI": 2, "WBOI": 3}
    result["heat_source"].sort(
        key=lambda code: (
            heat_group.get(code, 99),
            dc_heat_order.get(code, resource_group.get(code, 0)),
        )
    )
    result["coupled_source"].sort(
        # Dieselbe Reihenfolge gilt im Wärme-Stack, an beiden vertikalen
        # Routingkorridoren und an den AC-Ports: Biomasse, Abfall, Erdgas.
        key=lambda code: {"BCHP": 0, "WCHP": 1, "CHP": 2}.get(code, 99)
    )
    result["cool_source"].sort(
        key=lambda code: {"AC": 0, "CC": 1}.get(code, 2)
    )
    return result


def ordered_slot_devices(state: Mapping[str, Any], slot: str) -> list[str]:
    """Liefert die normalisierte Reihenfolge ausgewählter Geräte eines Slots."""

    selected = list(state.get("central_devices") or [])
    return normalize_slot_order(selected, state.get("slot_order")).get(slot, [])


def unused_candidates(
    slot: str, selected: Sequence[str], grid_enabled: bool
) -> list[str]:
    """Liefert noch wählbare Geräte oder Netzbezug eines Slots."""

    used = set(selected)
    if grid_enabled:
        used.add("GRID")
    candidates = (
        (INDIVIDUAL_COMPONENT_CONTROLS[slot],)
        if slot in INDIVIDUAL_COMPONENT_CONTROLS
        else SLOT_CANDIDATES.get(slot, ())
    )
    return [
        code for code in candidates
        if code not in used
    ]


def has_gas_input_component(selected: Sequence[str]) -> bool:
    """Prüft auf ein Gerät, das über den externen Gasbezug versorgt wird."""

    return any(
        RESOURCE_FOR_DEVICE.get(code, (None,))[0] == "GAS_IMPORT"
        for code in selected
    )


def has_hydrogen_generator(selected: Sequence[str]) -> bool:
    """Prüft auf ein Gerät, das Wasserstoff erzeugt (aktuell ELYZ)."""

    return any(
        code in CENTRAL_DEVICES
        and CENTRAL_DEVICES[code].get("slot") != "hydrogen_storage"
        and "hydrogen" in CENTRAL_DEVICES[code].get("outputs", ())
        for code in selected
    )


def has_dc_system(selected: Sequence[str]) -> bool:
    """Prüft, ob ein ausgewähltes Gerät DC aufnimmt oder abgibt."""

    return any(
        "dc" in CENTRAL_DEVICES[code].get("inputs", ())
        or "dc" in CENTRAL_DEVICES[code].get("outputs", ())
        for code in selected if code in CENTRAL_DEVICES
    )


def has_cooling_system(selected: Sequence[str]) -> bool:
    """Prüft, ob ein ausgewähltes Gerät Kälte erzeugt oder speichert."""

    return any(
        "cool" in CENTRAL_DEVICES[code].get("outputs", ())
        for code in selected if code in CENTRAL_DEVICES
    )


def has_heat_generator(selected: Sequence[str]) -> bool:
    """Prüft auf einen ausgewählten Wärmeerzeuger; der Wärmespeicher allein genügt nicht."""

    return any(
        code != "TES" and "heat" in CENTRAL_DEVICES[code].get("outputs", ())
        for code in selected if code in CENTRAL_DEVICES
    )


def has_electric_source(selected: Sequence[str], grid_enabled: bool) -> bool:
    """Prüft auf Stromnetzbezug oder eine ausgewählte elektrische Quelle."""

    return bool(grid_enabled) or any(
        code in {"PV", "WT", "WAT", "FC", *COUPLED_SOURCE_CODES}
        for code in selected
    )


