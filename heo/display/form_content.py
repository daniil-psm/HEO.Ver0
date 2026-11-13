"""Plant Formularinhalt und Abhängigkeiten vor dem Erzeugen von UI-Komponenten.

Der Plan enthält keine Pixelgrößen oder Fensterkoordinaten. Verborgene Felder
bleiben enthalten, damit Renderer ihre Eingabewerte und IDs erhalten können.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping

from heo.display.field_presentation import (
    range_counterpart_key, range_parameter_noun,
)
from heo.display.parameter_catalog import ACTIVATION_FIELD_GROUPS

LayoutProfile = Literal["automatic", "microgrid_start", "scenario_load"]
GroupKind = Literal["activation", "period", "range"]
Field = dict[str, Any]
ValueGetter = Callable[[Field], Any]


def field_key(field: Mapping[str, Any]) -> str:
    """Liefert den Katalogschlüssel, unabhängig von einer abweichenden Eingabe-ID."""
    return str(field.get("env_key") or field["input_key"])


@dataclass(frozen=True)
class FormCondition:
    """Bedingung für den Inhalt einer Gruppe oder ein einzelnes Feld."""

    key: str
    equals: Any = True
    source: Literal["value", "range_enabled"] = "value"


@dataclass(frozen=True)
class FormItem:
    """Feld oder gemeinsame Box mit geordneten, beliebig verschachtelten Kindern."""

    key: str
    field: Field
    order: float
    kind: Literal["field", "activation", "period", "range"] = "field"
    title: str = ""
    children: tuple[FormItem, ...] = ()
    condition: FormCondition | None = None
    children_condition: FormCondition | None = None
    visible: bool = True
    children_visible: bool = True

    def fields(self) -> tuple[Field, ...]:
        """Liefert jedes Katalogfeld einschließlich ausgeblendeter Kinder einmal."""
        # Bei MIN/MAX ist MIN bereits das erste Kind und kein eigener Schalter.
        own = () if self.kind == "range" else (self.field,)
        return own + tuple(field for child in self.children for field in child.fields())


@dataclass(frozen=True)
class FormContentPlan:
    """Geordneter Inhalt eines Formularbereichs mit explizitem Layoutprofil."""

    items: tuple[FormItem, ...]
    layout_profile: LayoutProfile = "automatic"

    def visible_keys(self) -> tuple[str, ...]:
        """Liefert die aktuell sichtbaren Parameter, ohne verborgene Nachfahren."""
        def visit(item: FormItem) -> tuple[str, ...]:
            """Berücksichtigt die Sichtbarkeit aller übergeordneten Gruppen."""
            if not item.visible:
                return ()
            own = () if item.kind == "range" else (field_key(item.field),)
            return own + (
                tuple(key for child in item.children for key in visit(child))
                if item.children_visible else ()
            )
        return tuple(key for item in self.items for key in visit(item))


def range_is_enabled(minimum: Field, maximum: Field, state: Mapping[str, Any]) -> bool:
    """Liest die manuelle Grenzwertfreigabe mit Rückfall auf gespeicherte Overrides."""
    keys = [str(field.get("input_key") or field_key(field)) for field in (minimum, maximum)]
    enabled = state.get("_range_enabled", {})
    explicit = [bool(enabled[key]) for key in keys if key in enabled]
    overrides = {str(key).upper() for key in state.get("overrides", [])}
    return any(explicit) if explicit else any(key.upper() in overrides for key in keys)


def plan_form_content(
    fields: Iterable[Field],
    value_getter: ValueGetter | None = None,
    *,
    activation_groups: Mapping[str, Mapping[str, Any]] | None = None,
    range_enabled: Callable[[Field, Field], bool] | None = None,
    layout_profile: LayoutProfile = "automatic",
) -> FormContentPlan:
    """Ordnet Felder, Sichtbarkeit und Gruppen ohne Render- oder Größenlogik.

    ``ui.order`` überschreibt die Eingabereihenfolge. ``ui.visible_when`` enthält
    ``key`` und optional ``equals`` für eine Feldbedingung. Gruppen werden an der
    Position ihres Controllers, MIN/MAX an der MIN-Position eingeordnet.
    Unvollständige Gruppen bleiben einzelne Felder. Identische Wiederholungen
    werden zusammengeführt; widersprüchliche Metadaten, mehrdeutige
    Zugehörigkeiten und zyklische Abhängigkeiten lösen einen ValueError aus.
    """
    by_key: dict[str, Field] = {}
    for field in fields:
        key = field_key(field)
        if key in by_key and by_key[key] != field:
            raise ValueError(f"Widersprüchliche Feldmetadaten für {key}")
        by_key.setdefault(key, field)
    field_list = list(by_key.values())
    get_value = value_getter or (lambda field: field.get("default"))
    order = {field_key(field): index for index, field in enumerate(field_list)}
    groups: dict[str, tuple[GroupKind, tuple[str, ...], str]] = {}

    # Zugehörigkeit steht vor der Ausgabe fest, auch wenn Kinder zuerst vorkommen.
    definitions = ACTIVATION_FIELD_GROUPS if activation_groups is None else activation_groups
    for key, definition in definitions.items():
        members = tuple(definition.get("fields") or ())
        if key in by_key and members and all(member in by_key for member in members):
            kind = "period" if definition.get("kind") == "period" else "activation"
            if kind == "period" and len(members) != 2:
                raise ValueError(f"Zeitraum {key} benötigt Anfang und Ende")
            groups[key] = (kind, members, str(definition.get("title") or by_key[key].get("label") or key))
    for key, field in by_key.items():
        maximum = range_counterpart_key(key, "MIN", "MAX")
        if maximum in by_key and key not in groups:
            groups[key] = ("range", (key, maximum), f"{range_parameter_noun(field)} begrenzen")

    # Ein Grenzwertpaar innerhalb einer Aktivierung ist selbst eine innere Box.
    for key, (kind, members, title) in tuple(groups.items()):
        if kind == "activation":
            paired_maxima = {
                groups[member][1][1] for member in members
                if member in groups and groups[member][0] == "range"
                and groups[member][1][1] in members
            }
            groups[key] = (kind, tuple(member for member in members if member not in paired_maxima), title)

    owners: dict[str, str] = {}
    for key, (kind, members, _) in groups.items():
        for member in members:
            if kind == "range" and member == key:
                continue
            if member in owners:
                raise ValueError(f"Parameter {member} gehört zu mehreren Formulargruppen")
            owners[member] = key
    for key in owners:
        visited: set[str] = set()
        current = key
        while current in owners:
            if current in visited:
                raise ValueError(f"Zyklische Formulargruppe bei {current}")
            visited.add(current)
            current = owners[current]

    def leaf(key: str) -> FormItem:
        """Übernimmt Feldmetadaten und löst eine optionale Sichtbarkeit auf."""
        field = by_key[key]
        definition = (field.get("ui") or {}).get("visible_when")
        condition = FormCondition(**definition) if definition else None
        if condition and condition.key not in by_key:
            raise ValueError(f"Sichtbarkeitsbedingung verweist auf fehlenden Parameter {condition.key}")
        return FormItem(
            key=key, field=field,
            order=float((field.get("ui") or {}).get("order", order[key])),
            condition=condition,
            visible=condition is None or get_value(by_key[condition.key]) == condition.equals,
        )

    def sort_key(key: str) -> tuple[float, int]:
        """Ordnet explizite Prioritäten stabil zur übergebenen Reihenfolge."""
        return float((by_key[key].get("ui") or {}).get("order", order[key])), order[key]

    def build(key: str) -> FormItem:
        """Baut eine Gruppe einschließlich ihrer inneren Abhängigkeiten."""
        item = leaf(key)
        if key not in groups:
            return item
        kind, members, title = groups[key]
        if kind == "range":
            children = tuple(leaf(member) for member in members)
            active = range_enabled(*(by_key[member] for member in members)) if range_enabled else True
            condition = FormCondition("|".join(members), source="range_enabled")
        else:
            child_keys = sorted(members, key=sort_key) if kind == "activation" else members
            children = tuple(build(member) for member in child_keys)
            active = bool(get_value(by_key[key]))
            condition = FormCondition(key)
        return FormItem(
            key=key, field=item.field, order=item.order, kind=kind, title=title,
            children=children, condition=item.condition, children_condition=condition, visible=item.visible,
            children_visible=active,
        )

    return FormContentPlan(
        tuple(build(key) for key in sorted(by_key, key=sort_key) if key not in owners),
        layout_profile=layout_profile,
    )
