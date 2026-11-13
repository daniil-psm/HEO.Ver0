"""HEO-Gebäudezustand, Nutzungsarten und Bearbeitungsregeln."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from heo.model.building_types import BUILDING_TYPES, EV_CHARGING_TYPES
from heo.model.building_supply import cooling_supply
from heo.model.devices import building_has_automatic_dhw_storage, normalize_building_heater

BOOLEAN_FIELDS = {"night_setback", "dhw", "cooling"}


def normalize_building_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalisiert ein HEO-Gebäude vor Validierung und Topologieaufbau."""

    normalized = dict(row)
    normalized["heater"] = normalize_building_heater(row.get("heater")) or "heat_grid"
    return normalized


RESIDENTIAL_BUILDING_TYPES = ("SFH", "MFH", "TH", "AB")
MIXED_BUILDING_TYPES = ("MFH+GR", "AB+GR", "MFH+RE", "AB+RE")
NON_RESIDENTIAL_BUILDING_TYPES = tuple(
    item for item in BUILDING_TYPES
    if item not in RESIDENTIAL_BUILDING_TYPES + MIXED_BUILDING_TYPES
)
BUILDING_CATEGORIES = ("residential", "non_residential", "mixed")
CATEGORY_BUILDING_TYPES = {
    "residential": RESIDENTIAL_BUILDING_TYPES,
    "non_residential": NON_RESIDENTIAL_BUILDING_TYPES,
    "mixed": MIXED_BUILDING_TYPES,
}
def active_decentral_devices(row: dict[str, Any]) -> list[tuple[str, str]]:
    """Leitet die aktivierten dezentralen Geräte eines Gebäudes ab."""

    explicit = {
        str(item.get("code") or "").upper()
        for item in (row.get("decentral_devices") or [])
        if isinstance(item, dict) and item.get("code")
    }
    heater = str(row.get("heater") or "").strip().upper()
    if heater in {"", "0", "NONE", "HEAT_GRID"}:
        heater = ""
    candidates = [
        ("pv", "PV" if (
            "PV" in explicit
            or float(row.get("f_PV1") or 0) + float(row.get("f_PV2") or 0) > 0
        ) else ""),
        ("stc", "STC" if "STC" in explicit or float(row.get("f_STC") or 0) > 0 else ""),
        ("heater", heater),
        ("dhw", "EH_DHW" if (
            "EH_DHW" in explicit or "DL" in explicit or bool(row.get("dhw"))
        ) else ""),
        ("dhw_storage", "TES_DHW" if (
            "TES_DHW" in explicit or building_has_automatic_dhw_storage(row)
        ) else ""),
        ("battery", "BAT" if "BAT" in explicit or float(row.get("f_BAT") or 0) > 0 else ""),
        ("ev", "EV" if "EV" in explicit or bool(row.get("EV")) else ""),
        ("heat_storage", "TES" if "TES" in explicit or float(row.get("f_TES") or 0) > 0 else ""),
        ("cooling", "CC" if (
            "CC" in explicit
            or cooling_supply(row) == "decentral"
        ) else ""),
    ]
    return [(slot, code) for slot, code in candidates if code]


def _new_building(uid: int, automatic_id: int) -> dict[str, Any]:
    """Erzeugt einen Gebäudedatensatz mit stabiler UID, automatischer Nummer und Standardwerten."""

    return {
        "uid": uid,
        "auto_id": automatic_id,
        "id": automatic_id,
        "id_manual": False,
        "name": "",
        "category": None,
        "building": None,
        "year": 1960,
        "retrofit": 0,
        "construction_type": 2,
        "night_setback": False,
        "area": 140.0,
        "heater": "HP",
        "dhw": False,
        "cooling": False,
        "EV": False,
        "f_TES": 35.0,
        "f_BAT": 1.0,
        "f_PV1": 0.2,
        "f_PV2": 0.2,
        "f_STC": 0.0,
        "beta_PV": 35,
        "gamma_PV": 0,
        "ev_charging": "on_demand",
    }


DEFAULT_BUILDING_SCENARIO_STATE = {
    "rows": [_new_building(0, 1)],
    "next_uid": 1,
    "next_auto_id": 2,
}


def empty_building_state() -> dict[str, Any]:
    """Erzeugt einen leeren Gebäudeentwurf für ein neues Szenario."""

    return {"rows": [], "next_uid": 0, "next_auto_id": 1}


def building_by_uid(state: dict, uid: int) -> dict | None:
    """Findet ein Gebäude anhand seiner stabilen internen Kennung."""

    return next(
        (row for row in state.get("rows", []) if int(row.get("uid", -1)) == int(uid)),
        None,
    )


def building_category(row: dict[str, Any]) -> str | None:
    """Liefert die explizite oder aus dem DG-Typ abgeleitete Nutzungskategorie."""

    category = row.get("category")
    if category in BUILDING_CATEGORIES:
        return category
    building_type = row.get("building")
    return next(
        (key for key, values in CATEGORY_BUILDING_TYPES.items() if building_type in values),
        None,
    )


def _reindex_automatic_ids(state: dict[str, Any]) -> dict[str, Any]:
    """Nummeriert die übergebenen Gebäude in-place und setzt deren manuelle Nummern zurück."""

    for automatic_id, row in enumerate(state["rows"], start=1):
        row.update(auto_id=automatic_id, id=automatic_id, id_manual=False)
    state["next_auto_id"] = len(state["rows"]) + 1
    return state


def building_state(state: dict | None) -> dict[str, Any]:
    """Liefert eine normalisierte Kopie des Gebäudezustands einschließlich ID-Zählern."""

    resolved = deepcopy(state or DEFAULT_BUILDING_SCENARIO_STATE)
    resolved.setdefault("rows", [])
    for row in resolved["rows"]:
        row.setdefault("name", "")
        if "category" not in row:
            row["category"] = building_category(row)
        elif row.get("category") not in BUILDING_CATEGORIES:
            row["category"] = None
    highest_uid = max((int(row.get("uid", -1)) for row in resolved["rows"]), default=-1)
    resolved["next_uid"] = max(int(resolved.get("next_uid", 0)), highest_uid + 1)
    return _reindex_automatic_ids(resolved)


def add_building(state: dict | None, after_uid: int | None = None) -> dict[str, Any]:
    """Fügt einer Zustandskopie ein Standardgebäude mit neuer UID hinzu und nummeriert die Liste neu."""

    updated = building_state(state)
    uid = int(updated["next_uid"])
    row = _new_building(uid, len(updated["rows"]) + 1)
    updated["next_uid"] = uid + 1
    if after_uid is None or after_uid == -1:
        updated["rows"].append(row)
    else:
        index = next(
            (i for i, existing in enumerate(updated["rows"]) if int(existing["uid"]) == int(after_uid)),
            len(updated["rows"]) - 1,
        )
        updated["rows"].insert(index + 1, row)
    return _reindex_automatic_ids(updated)


def new_central_building(current: dict | None) -> dict[str, Any]:
    """Fügt ein zunächst unkonfiguriertes, zentral versorgtes Gebäude hinzu."""

    updated = add_building(current or empty_building_state(), -1)
    updated["rows"][-1].update(
        category=None, building=None, heater="heat_grid", dhw=False,
        dhw_heater="", cooling=False,
        EV=False, f_TES=0.0,
        f_BAT=0.0, f_PV1=0.0, f_PV2=0.0, f_STC=0.0,
        beta_PV=35, gamma_PV=0,
    )
    return updated


def duplicate_building(state: dict | None, uid: int) -> dict[str, Any]:
    """Dupliziert ein Gebäude direkt hinter seinem Quelldatensatz."""

    updated = building_state(state)
    source_index = next(
        (
            index for index, row in enumerate(updated["rows"])
            if int(row.get("uid", -1)) == int(uid)
        ),
        None,
    )
    if source_index is None:
        return updated

    duplicate = deepcopy(updated["rows"][source_index])
    duplicate["uid"] = int(updated["next_uid"])
    updated["next_uid"] = duplicate["uid"] + 1
    updated["rows"].insert(source_index + 1, duplicate)
    return _reindex_automatic_ids(updated)


def remove_building(state: dict | None, uid: int) -> dict[str, Any]:
    """Entfernt das Gebäude mit der angegebenen UID aus einer Kopie und nummeriert die Liste neu."""

    updated = building_state(state)
    updated["rows"] = [row for row in updated["rows"] if int(row["uid"]) != int(uid)]
    return _reindex_automatic_ids(updated)


def move_building(
    state: dict | None, uid: int, before_uid: int,
) -> dict[str, Any]:
    """Verschiebt ein Gebäude relativ zur Ziel-UID in einer Zustandskopie und nummeriert die Liste neu."""

    updated = building_state(state)
    source_uid = int(uid)
    target_uid = int(before_uid)
    if source_uid == target_uid:
        return updated

    source_index = next(
        (index for index, row in enumerate(updated["rows"])
         if int(row.get("uid", -1)) == source_uid),
        None,
    )
    target_index = next(
        (index for index, row in enumerate(updated["rows"])
         if int(row.get("uid", -1)) == target_uid),
        None,
    )
    if source_index is None or target_index is None:
        return updated

    row = updated["rows"].pop(source_index)
    # Nach dem Entfernen liegt das Ziel bei einer vorher rechts liegenden
    # Position einen Index weiter links.
    if source_index < target_index:
        target_index -= 1
    updated["rows"].insert(target_index, row)
    return _reindex_automatic_ids(updated)


def update_building_values(
    state: dict | None, field_ids: list[dict] | None, field_values: list[Any] | None,
    id_ids: list[dict] | None = None, id_values: list[Any] | None = None,
) -> dict[str, Any]:
    """Übernimmt Feldwerte anhand der Gebäude-UIDs in eine Kopie des Gebäudezustands."""

    updated = building_state(state)
    rows = {int(row["uid"]): row for row in updated["rows"]}
    for component_id, value in [
        *zip(field_ids or [], field_values or []), *zip(id_ids or [], id_values or []),
    ]:
        row = rows.get(int(component_id["uid"]))
        if row is None:
            continue
        field = component_id.get("field", "id")
        category = component_id.get("category")
        if category and category != building_category(row):
            continue
        if field in BOOLEAN_FIELDS:
            row[field] = bool(value)
        elif field == "category":
            row[field] = value if value in BUILDING_CATEGORIES else None
            if row.get("building") not in CATEGORY_BUILDING_TYPES.get(row[field], ()):
                row["building"] = None
        elif field == "id":
            row["id"] = row["auto_id"]
        else:
            row[field] = value
    for row in updated["rows"]:
        if row.get("building") not in CATEGORY_BUILDING_TYPES.get(building_category(row), ()):
            row["building"] = None
    return updated


def automatic_id(state: dict | None, uid: int) -> int:
    """Liefert die automatische Gebäudenummer zur UID oder ersatzweise 1."""

    for row in building_state(state)["rows"]:
        if int(row["uid"]) == int(uid):
            return int(row["auto_id"])
    return 1
