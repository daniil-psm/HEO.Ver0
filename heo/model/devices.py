"""HEO-Gerätekatalog, Geräteidentitäten und Gebäude-Heizsystemregeln."""

# Zentraler Übersetzungskatalog zwischen DG und HEO für die Komponenten

from __future__ import annotations

from typing import Any, Mapping


def _label_variants(
    *,
    full_name: str, abbreviation: str, wrapped_name: str | None,
) -> dict[str, str]:
    """Erzeugt Vollname, umgebrochene Bezeichnung und Kürzel eines Katalogeintrags."""

    return {
        "full": full_name,
        "wrapped": wrapped_name or full_name,
        "short": abbreviation,
    }


def _device(
    *,
    full_name: str,
    abbreviation: str,
    slot: str,
    wrapped_name: str | None = None,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Erzeugt Metadaten einer zentralen Komponente einschließlich Slot und Energieträgern."""

    candidate_labels = _label_variants(
        full_name=full_name,
        abbreviation=abbreviation,
        wrapped_name=wrapped_name,
    )
    return {
        "full_name": full_name,
        "abbreviation": abbreviation,
        "label": full_name,
        "topology_labels": dict(candidate_labels),
        "candidate_labels": candidate_labels,
        "slot": slot,
        "inputs": inputs,
        "outputs": outputs,
    }

# Zentrale Komponenten der HEO-Auswahl; native DG-Codes bleiben im Adapter.
HEO_CENTRAL_DEVICE_CATALOG: dict[str, dict[str, Any]] = {
    "PV": _device(full_name="Photovoltaik", abbreviation="PV", slot="dc_source", wrapped_name="Photo-\nvoltaik", outputs=("dc",)),
    "WT": _device(full_name="Windkraftanlage", abbreviation="WKA", slot="dc_source", wrapped_name="Windkraft-\nanlage", outputs=("dc",)),
    "WAT": _device(full_name="Wasserkraftanlage", abbreviation="WAT", slot="dc_source", wrapped_name="Wasserkraft-\nanlage", outputs=("dc",)),
    "STC": _device(full_name="Solarthermie", abbreviation="ST", slot="heat_source", wrapped_name="Solar-\nthermie", outputs=("heat",)),
    "CHP": _device(full_name="Erdgas-BHKW", abbreviation="BHKW", slot="coupled_source", inputs=("gas",), outputs=("power", "heat")),
    "BOI": _device(full_name="Gaskessel", abbreviation="GK", slot="heat_source", wrapped_name="Gas-\nkessel", inputs=("gas",), outputs=("heat",)),
    "GHP": _device(full_name="Gas-Wärmepumpe", abbreviation="GWP", slot="heat_source", wrapped_name="Gas-Wärme-\npumpe", inputs=("gas",), outputs=("heat",)),
    "HP": _device(full_name="Wärmepumpe", abbreviation="WP", slot="heat_source", wrapped_name="Wärme-\npumpe", inputs=("dc",), outputs=("heat",)),
    "GROUNDHP": _device(full_name="Erdwärmepumpe", abbreviation="GEO", slot="heat_source", wrapped_name="Erdwärme-\npumpe", inputs=("dc",), outputs=("heat",)),
    "EB": _device(full_name="Elektroheizer", abbreviation="EH", slot="heat_source", wrapped_name="Elektro-\nheizer", inputs=("dc",), outputs=("heat",)),
    "CC": _device(full_name="Kompressionskältemaschine", abbreviation="KKM", slot="cool_source", wrapped_name="Kompressions-\nkältemaschine", inputs=("dc",), outputs=("cool",)),
    "AC": _device(full_name="Absorptionskältemaschine", abbreviation="AKM", slot="cool_source", wrapped_name="Absorptions-\nkältemaschine", inputs=("heat",), outputs=("cool",)),
    "BCHP": _device(full_name="Biomasse-BHKW", abbreviation="BBHKW", slot="coupled_source", wrapped_name="BIO-\nBHKW", inputs=("biomass",), outputs=("power", "heat")),
    "BBOI": _device(full_name="Biomassekessel", abbreviation="BK", slot="heat_source", wrapped_name="Biomasse-\nkessel", inputs=("biomass",), outputs=("heat",)),
    "WCHP": _device(full_name="Abfall-BHKW", abbreviation="ABHKW", slot="coupled_source", wrapped_name="AB-\nBHKW", inputs=("waste",), outputs=("power", "heat",)),
    "WBOI": _device(full_name="Abfallkessel", abbreviation="AK", slot="heat_source", wrapped_name="Abfall-\nkessel", inputs=("waste",), outputs=("heat",)),
    "ELYZ": _device(full_name="Elektrolyseur", abbreviation="ELY", slot="hydrogen_converter", inputs=("dc",), outputs=("hydrogen",)),
    "FC": _device(full_name="H2-BHKW", abbreviation="H2BHKW", slot="hydrogen_converter", wrapped_name="H2-\nBHKW", inputs=("hydrogen",), outputs=("dc", "heat",)),
    "H2S": _device(full_name="Wasserstoffspeicher", abbreviation="H2S", slot="hydrogen_storage", inputs=("hydrogen",), outputs=("hydrogen",)),
    "SAB": _device(full_name="Sabatier-Reaktor", abbreviation="SAB", slot="hydrogen_converter", inputs=("hydrogen",), outputs=("gas",)),
    "TES": _device(full_name="Wärmespeicher", abbreviation="TES", slot="heat_storage", wrapped_name="Wärme-\nspeicher", inputs=("heat",), outputs=("heat",)),
    "CTES": _device(full_name="Kältespeicher", abbreviation="CTES", slot="cool_storage", wrapped_name="Kälte-\nspeicher", inputs=("cool",), outputs=("cool",)),
    "BAT": _device(full_name="Batteriespeicher", abbreviation="BESS", slot="dc_storage", wrapped_name="Batterie-\nspeicher", inputs=("dc",), outputs=("dc",)),
    "GS": _device(full_name="Gasspeicher", abbreviation="GS", slot="gas_storage", inputs=("gas",), outputs=("gas",)),
}

# Labels für Netze, Busse und andere Hilfsknoten
TOPOLOGY_AUXILIARY_LABELS: dict[str, dict[str, str]] = {
    "GRID": _label_variants(full_name="Stromnetz", wrapped_name="Strom-\nnetz", abbreviation="POW"),
    "GAS_IMPORT": _label_variants(full_name="Gasbezug", wrapped_name="Gas-\nbezug", abbreviation="GAS"),
    "GAS_BUS": _label_variants(full_name="Dezentrales Gasnetz", wrapped_name="Dezentrales\nGasnetz", abbreviation="GAS"),
    "WASTE_IMPORT": _label_variants(full_name="Abfallbezug", wrapped_name="Abfall-\nbezug", abbreviation="ABF"),
    "BIOMASS_IMPORT": _label_variants(full_name="Biomassebezug", wrapped_name="Biomasse-\nbezug", abbreviation="BIO"),
    "OIL_IMPORT": _label_variants(full_name="Ölbezug", wrapped_name="Öl-\nbezug", abbreviation="ÖL"),
    "AC_BUS": _label_variants(full_name="AC-Bus", wrapped_name="AC-Bus", abbreviation="AC"),
    "DC_BUS": _label_variants(full_name="DC-Bus", wrapped_name="DC-Bus", abbreviation="DC"),
    "INVERTER": _label_variants(full_name="Inverter", wrapped_name="Inver-\nter", abbreviation="INV"),
    "HEAT_GRID": _label_variants(full_name="Wärmenetz", wrapped_name="Wärme-\nnetz", abbreviation="WÄRME"),
    "COOL_GRID": _label_variants(full_name="Kältenetz", wrapped_name="Kälte-\nnetz", abbreviation="KÄLTE"),
    "H2_IMPORT": _label_variants(full_name="Wasserstoffbezug", wrapped_name="H2-\nbezug", abbreviation="H2"),
    "H2_BUS": _label_variants(full_name="Dezentrales H2-Netz", wrapped_name="Dezentrales\nH2-Netz", abbreviation="H2-Netz"),
    "LOAD": _label_variants(full_name="Last", wrapped_name="Last", abbreviation="Last"),
}

def _decentral(
    *,
    full_name: str,
    abbreviation: str,
    slot: str,
    wrapped_name: str | None = None,
    dg_components: tuple[str, ...] | None = None,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Erzeugt Metadaten eines dezentralen Geräts einschließlich nativer DG-Komponenten."""

    candidate_labels = _label_variants(
        full_name=full_name,
        abbreviation=abbreviation,
        wrapped_name=wrapped_name,
    )
    return {
        "full_name": full_name,
        "abbreviation": abbreviation,
        "topology_labels": dict(candidate_labels),
        "candidate_labels": candidate_labels,
        "slot": slot,
        "dg_components": dg_components,
        "inputs": inputs,
        "outputs": outputs,
    }

# Dezentrale Komponenten
HEO_DECENTRAL_DEVICE_CATALOG: dict[str, dict[str, Any]] = {
    "HP": _decentral(full_name="Wärmepumpe", abbreviation="WP", slot="heater"),
    "GHP": _decentral(full_name="Wärmepumpe + Gaskessel", abbreviation="WP+GK", slot="heater", dg_components=("HP", "BOI")),
    "BHP": _decentral(full_name="Wärmepumpe + Biomassekessel", abbreviation="WP+BK", slot="heater", dg_components=("HP", "BBOI")),
    "H2HP": _decentral(full_name="Wärmepumpe + H2-Kessel", abbreviation="WP+H2K", slot="heater", dg_components=("HP", "H2BOI"), inputs=("dc", "hydrogen"), outputs=("heat",),),
    "OHP": _decentral(full_name="Wärmepumpe + Ölkessel", abbreviation="WP+ÖK", slot="heater", dg_components=("HP", "OBOI")),
    "BOI": _decentral(full_name="Gaskessel", abbreviation="GK", slot="heater"),
    "BBOI": _decentral(full_name="Biomassekessel", abbreviation="BK", slot="heater"),
    "OBOI": _decentral(full_name="Ölkessel", abbreviation="ÖK", slot="heater", inputs=("oil",), outputs=("heat",),),
    "H2BOI": _decentral(full_name="Wasserstoffkessel", abbreviation="H2K", slot="heater", inputs=("hydrogen",), outputs=("heat",),),
    "CHP": _decentral(full_name="Blockheizkraftwerk", abbreviation="BHKW", slot="heater", inputs=("gas",), outputs=("ac", "heat"),),
    "DH": _decentral(full_name="Fernwärmeanschluss", abbreviation="FW", slot="heater"),
    "FC": _decentral(full_name="Wasserstoff-BHKW", abbreviation="H2BHKW", slot="heater", wrapped_name="H2-\nBHKW", inputs=("hydrogen",), outputs=("ac", "heat"),),
    "EH": _decentral(full_name="Elektroheizung", abbreviation="EH", slot="heater"),
    "CC": _decentral(full_name="Kompressionskältemaschine", abbreviation="KKM", slot="cooling"),
    "PV": _decentral(full_name="Photovoltaik", abbreviation="PV", slot="pv"),
    "STC": _decentral(full_name="Solarthermie", abbreviation="ST", slot="stc"),
    "TES": _decentral(full_name="Wärmespeicher", abbreviation="TES", slot="heat_storage"),
    "BAT": _decentral(full_name="Batteriespeicher", abbreviation="BAT", slot="battery"),
    "EV": _decentral(full_name="Elektrofahrzeug", abbreviation="EV", slot="ev", inputs=("dc",), outputs=("dc",), ),
    "EH_DHW": _decentral(full_name="Elektrischer Durchlauferhitzer", abbreviation="DLE", slot="dhw"),
    "TES_DHW": _decentral(full_name="Trinkwarmwasserspeicher", abbreviation="TWS", slot="dhw_storage"),
}


# Hilfsbezeichnungen für das DG-Backend
HEATER_SYSTEM_PARTS: dict[str, frozenset[str]] = {
    "HP": frozenset({"HP", "EH"}),
    "GHP": frozenset({"HP", "BOI"}),
    "BHP": frozenset({"HP", "BBOI"}),
    "H2HP": frozenset({"HP", "H2BOI"}),
    "OHP": frozenset({"HP", "OBOI"}),
    "EH": frozenset({"EH"}),
    "BOI": frozenset({"BOI"}),
    "BBOI": frozenset({"BBOI"}),
    "OBOI": frozenset({"OBOI"}),
    "H2BOI": frozenset({"H2BOI"}),
    "CHP": frozenset({"CHP"}),
    "FC": frozenset({"FC"}),
    "DH": frozenset({"DH"}),
}


def normalize_building_heater(value: Any) -> str:
    """Normalisiert kanonische und ``x+y``-Heizsysteme für den DG.

    Nicht bekannte Kombinationen bleiben bewusst unverändert. Dadurch gehen
    Informationen aus importierten CSVs nicht verloren und der nachgelagerte
    DG-Validator kann eine fachlich verständliche Meldung ausgeben.
    """

    raw = str(value or "").strip()
    if not raw or raw.lower() in {"none", "0", "heat_grid"}:
        return "heat_grid" if raw.lower() == "heat_grid" else raw
    upper = raw.upper().replace(" ", "")
    if upper in HEATER_SYSTEM_PARTS:
        return upper
    parts = frozenset(part for part in upper.split("+") if part)
    for code, system_parts in HEATER_SYSTEM_PARTS.items():
        if parts == system_parts:
            return code
    return upper


def building_heater_parts(value: Any) -> frozenset[str]:
    """Gibt die atomaren Teile eines dezentralen Heizsystems zurück."""

    normalized = normalize_building_heater(value)
    if normalized in HEATER_SYSTEM_PARTS:
        return HEATER_SYSTEM_PARTS[normalized]
    return frozenset(
        part for part in normalized.split("+")
        if part and part not in {"HEAT_GRID", "NONE", "0"}
    )


CENTRAL_CODE_ALIASES = {
    "GroundHP": "GROUNDHP",
}


def normalize_central_device_code(code: str) -> str:
    """Übersetzt einen nativen DG-Code in den HEO-Schlüssel."""

    return CENTRAL_CODE_ALIASES.get(code, code)


def central_device_metadata(code: str) -> dict[str, Any] | None:
    """Liefert zentrale Metadaten nach Code-Normalisierung oder None bei unbekanntem Code."""

    return HEO_CENTRAL_DEVICE_CATALOG.get(normalize_central_device_code(code))


def decentral_device_metadata(code: str) -> dict[str, Any] | None:
    """Liefert dezentrale Metadaten zum HEO-Code oder None bei unbekanntem Code."""

    return HEO_DECENTRAL_DEVICE_CATALOG.get(code)


def decentral_device_codes(slot: str) -> tuple[str, ...]:
    """Liefert die dezentralen HEO-Gerätecodes eines Slots in Katalogreihenfolge."""

    return tuple(
        code
        for code, metadata in HEO_DECENTRAL_DEVICE_CATALOG.items()
        if metadata["slot"] == slot
    )


def building_has_automatic_dhw_storage(row: Mapping[str, Any]) -> bool:
    """Prüft den abgeleiteten dezentralen TWW-Speicher eines Gebäudes.

    Der DistrictGenerator deaktiviert ``TES_DHW`` ausschließlich beim
    elektrischen Durchlauferhitzer (``EH_DHW``). In der Gebäude-UI wird der
    Speicher für die dezentrale Wärmeversorgung sichtbar gemacht; er ist
    daher kein frei wählbarer oder separat löschbarer Geräteslot.
    """

    heater = str(row.get("heater") or "").strip().upper()
    has_decentral_heat = heater not in {"", "0", "NONE", "HEAT_GRID"}
    explicit_codes = {
        str(item.get("code") or "").upper()
        for item in (row.get("decentral_devices") or [])
        if isinstance(item, Mapping) and item.get("code")
    }
    has_direct_heater = (
        bool(row.get("dhw"))
        or str(row.get("dhw_heater") or "").strip().upper() == "EH_DHW"
        or bool({"EH_DHW", "DL"} & explicit_codes)
    )
    return has_decentral_heat and not has_direct_heater


def decentral_device_components(code: str) -> tuple[str, ...]:
    """Liefert die nativen DG-Komponenten hinter einem dezentralen HEO-System."""

    metadata = decentral_device_metadata(code) or {}
    components = metadata.get("dg_components")
    return tuple(components) if components else (code,)


# Gebäude


