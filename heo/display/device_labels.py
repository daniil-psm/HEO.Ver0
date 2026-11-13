"""Zentrale HEO-Geräte- und Gebäude-Bezeichnungen für alle Ansichten."""

from __future__ import annotations

from heo.model.devices import (
    TOPOLOGY_AUXILIARY_LABELS, central_device_metadata,
    decentral_device_metadata,
)

# Bezeichnungen der Hinzufügen-Schaltflächen in der HEO-Topologie.
SLOT_ADD_LABELS = {
    "electric_source": "Stromerzeuger hinzufügen",
    "dc_source": "DC-Erzeuger hinzufügen",
    "dc_storage": "DC-Speicher hinzufügen",
    "heat_source": "Wärmeerzeuger hinzufügen",
    "heat_storage": "Wärmespeicher hinzufügen",
    "cool_source": "Kälteerzeuger hinzufügen",
    "cool_storage": "Kältespeicher hinzufügen",
    "building": "Gebäude hinzufügen",
    "dc_area": "Gleichstrom hinzufügen",
    "cool_area": "Kälte hinzufügen",
    "other_area": "Weitere Komponenten hinzufügen",
    "hydrogen_converter": "Wasserstoffwandler hinzufügen",
    "hydrogen_storage": "Wasserstoffspeicher hinzufügen",
    "gas_storage": "Gasspeicher hinzufügen",
}

TOPOLOGY_AREA_TITLES = {
    "dc_area": "Gleichstrom",
    "cool_area": "Kälte",
    "other_area": "weitere",
}

def catalog_display_name(code: str) -> str:
    """Liefert den kanonischen Vollnamen eines Topologie-Codes.

    Zentrale HEO-Geräte haben Vorrang, weil einige Codes auch im dezentralen
    Katalog vorkommen. Netz-, Bus- und Bezugs-Knoten werden anschließend über
    den Hilfskatalog aufgelöst.
    """

    metadata = central_device_metadata(code) or decentral_device_metadata(code)
    if metadata:
        return str(
            metadata.get("full_name")
            or metadata.get("topology_labels", {}).get("full")
            or code
        )
    auxiliary_labels = TOPOLOGY_AUXILIARY_LABELS.get(code, {})
    return str(auxiliary_labels.get("full") or code)


def central_device_name(code: str) -> str:
    """Liefert die zentrale Vollbezeichnung oder ersatzweise den Code."""

    metadata = central_device_metadata(code) or {}
    return str(metadata.get("full_name") or code)


def central_device_abbreviation(code: str) -> str:
    """Liefert das zentrale Kürzel oder ersatzweise den Code."""

    metadata = central_device_metadata(code) or {}
    return str(metadata.get("abbreviation") or code)


def decentral_device_name(code: str) -> str:
    """Liefert die dezentrale Vollbezeichnung oder ersatzweise den Code."""

    metadata = decentral_device_metadata(code) or {}
    return str(metadata.get("full_name") or code)


def decentral_device_abbreviation(code: str) -> str:
    """Liefert das dezentrale Kürzel oder ersatzweise den Code."""

    metadata = decentral_device_metadata(code) or {}
    return str(metadata.get("abbreviation") or code)


# Deutsche Bezeichnungen für Gebäudetypen, Kategorien und Ladearten.
BUILDING_TYPE_LABELS = {
    "SFH": "Einfamilienhaus",
    "MFH": "Mehrfamilienhaus",
    "TH": "Reihenhaus",
    "AB": "Wohnblock",
    "OB": "Büro",
    "SC": "Schule",
    "GS": "Lebensmittelmarkt",
    "RE": "Restaurant",
    "MFH+GR": "Mehrfamilienhaus + Markt",
    "AB+GR": "Wohnblock + Markt",
    "MFH+RE": "Mehrfamilienhaus + Restaurant",
    "AB+RE": "Wohnblock + Restaurant",
}

BUILDING_CATEGORY_LABELS = {
    "residential": "Wohngebäude",
    "non_residential": "Nichtwohngebäude",
    "mixed": "Gemischt genutztes Gebäude",
}

EV_CHARGING_LABELS = {
    "on_demand": "Direktladen",
    "optimized": "Optimiert",
    "bi_directional": "Bidirektional",
}

def building_type_label(code: str) -> str:
    """Übersetzt einen DG-Gebäudetyp für die Oberfläche."""

    return BUILDING_TYPE_LABELS.get(code, code)


def building_category_label(category: str) -> str:
    """Übersetzt eine Gebäudekategorie für die Oberfläche."""

    return BUILDING_CATEGORY_LABELS.get(category, category)


def ev_charging_label(mode: str) -> str:
    """Übersetzt das Ladeverhalten für die Oberfläche."""

    return EV_CHARGING_LABELS.get(mode, mode)


def building_heater_label(code: str) -> str:
    """Liefert die Gebäudedialog-Bezeichnung eines Heizsystems."""

    if code == "heat_grid":
        return TOPOLOGY_AUXILIARY_LABELS["HEAT_GRID"]["full"]
    return decentral_device_name(code)
