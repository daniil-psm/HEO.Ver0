"""Gemeinsamer Belegungsplan aller Topology-Bereiche vor der Pixelprojektion."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import Any, Iterable, Literal, Mapping, Sequence

from heo.model.building_supply import central_connections
from heo.topology.axis_plan import Anchor, AxisPlan, ColumnPacking
from heo.topology.building import (
    _building_has_central_cooling, _building_has_central_dhw, _building_has_heat,
    _building_is_decentral, _visible_building_plan, building_ring_placements,
)
from heo.topology.definitions import (
    CENTRAL_DEVICES, COUPLED_SOURCE_CODES, HEAT_RESOURCE_STACK_ORDER,
    INDIVIDUAL_COMPONENT_CONTROLS, RESOURCE_FOR_DEVICE, has_cooling_system, has_dc_system,
    ordered_slot_devices, unused_candidates,
)
from heo.topology.model import GridPosition
from heo.topology.sizing import MAX_BUILDING_COLUMNS

BUILDING_EXTRA_TRACKS = 4  # bestehende Kapazitätsregel: zwei zusätzliche Gebäudezeilen
NODE_TRACK_SIZE = 2  # eine volle Zelle; Koordinatenschritt = halbe Zeile


@dataclass(frozen=True)
class TrackSpan:
    """Erster/letzter belegter Anker; Zellgrenzen liegen je einen Track außen."""

    first: int
    last: int


@dataclass
class TrackOccupancy:
    """Nachvollziehbare Belegung durch Nodes, Controls und Anschlussflächen."""

    claims: dict[str, tuple[int, ...]] = field(default_factory=dict)

    @property
    def span(self) -> TrackSpan | None:
        """Liefert die äußersten belegten Tracks oder None bei leerer Belegung."""

        tracks = [track for claim in self.claims.values() for track in claim]
        return TrackSpan(min(tracks), max(tracks)) if tracks else None


@dataclass(frozen=True)
class _ResolvedRows:
    """Gemeinsam aufgelöste Bereichsbelegung und Anschlüsse vor der Pixelprojektion."""

    ac_active: bool
    chp_ac_lane_last_track: int
    chp_ac_lane_track: int | None
    chp_ac_track_by_code: dict[str, int]
    cold_active: bool
    cool_start: int
    cool_storage_last: int
    coupled_codes: list[str]
    coupled_placeholder_track: int | None
    coupled_track_by_code: dict[str, int]
    dc_active: bool
    dc_port_track_by_code: dict[str, int]
    dc_storage_last: int
    external_source_track_by_id: dict[str, int]
    external_start: int
    heat_half_column_by_code: dict[str, float]
    heat_plus_half_column: float
    heat_plus_track: int
    heat_port_track_by_code: dict[str, int]
    heat_stack_codes: list[str]
    heat_storage_last: int
    heat_track_by_code: dict[str, int]
    selected: list[str]
    slot_codes: dict[str, list[str]]
    slot_has_plus: dict[str, bool]
    slot_tracks: dict[str, list[int]]
    pill_spans: dict[str, TrackSpan]
    ac_occupancy: TrackOccupancy
    dc_occupancy: TrackOccupancy
    heat_occupancy: TrackOccupancy
    cool_occupancy: TrackOccupancy
    row_anchors: dict[str, int]
    hydrogen_order: tuple[str, ...]
    hydrogen_codes: tuple[str, ...]
    gas_port_track_by_code: dict[str, int]
    elyz_dc_lane_track_bounds: tuple[int, int] | None


def _resolve_rows(area_input: AreaLayoutInput) -> _ResolvedRows:
    """Übersetzt Bereichsbeziehungen in Anker; erst danach werden Tracks gelöst."""
    areas, arrangements = area_input.areas, area_input.slots
    selected = list(area_input.selected)
    dc_active, cold_active = areas["dc"].active, areas["cool"].active
    grid_enabled, editing = area_input.grid_enabled, area_input.editing
    slot_codes = {key: list(slot.device_codes) for key, slot in arrangements.items()}
    slot_has_plus = {key: bool(slot.control_ids) for key, slot in arrangements.items()}
    axis = AxisPlan("row")
    axis.add("origin")
    axis.add("scene.origin", ("origin", 0))
    slot_names: dict[str, tuple[str, ...]] = {}

    def relative(area: str, rule: str) -> Anchor:
        """Liest den benannten Zeilenbezug eines Bereichs als Anker und Abstand."""

        return areas[area].dependency(rule).binding("row")

    def allocate(slot: str, start: Anchor) -> str:
        """Registriert sichtbare Slot-Tracks einschließlich Plus-Platz und liefert den Endanker."""

        arrangement = arrangements[slot]
        count = len(arrangement.device_codes) + bool(arrangement.control_ids)
        if not arrangement.active:
            count = int(editing)
        elif editing:
            count = max(1, count)
        slot_names[slot] = tuple(f"slot.{slot}.{i}" for i in range(count))
        return axis.stack(slot_names[slot], start, arrangement.track_step)

    # Strom: AC-Anschlüsse, Inverter und DC-Belegung bestimmen den unteren Stromanker.
    coupled_codes = list(areas["power"].connection_order)
    coupled_names = {code: axis.add(f"power.port.{code}", ("origin", i + int(grid_enabled)))
                     for i, code in enumerate(coupled_codes)}
    plus_name = axis.add("power.plus", ("origin", len(coupled_codes) + int(grid_enabled))) if slot_has_plus["electric_source"] else None
    ac_ports = [*(("origin",) if grid_enabled else ()), *coupled_names.values()]
    axis.add("power.ports", *((key, 0) for key in ac_ports))
    axis.add("dc.source_start", relative("dc", "source_start"))
    axis.add("power.inverter", ("dc.source_start", -1))
    dc_last = allocate("dc_source", ("dc.source_start", 0))
    dc_storage_end = allocate("dc_storage", (dc_last, 1))
    dc_inputs = {}
    if "FC" in selected:
        storage = slot_names["dc_storage"][:len(slot_codes["dc_storage"])]
        dc_inputs["FC"] = axis.add("dc.port.FC", (storage[-1] if storage else dc_storage_end, 1))
    right_ids = {*areas["heat"].element_ids, *areas["cool"].element_ids, "ELYZ"}
    right_consumers = {r.element_id for r in area_input.connections
                       if r.bus_id == "DC_BUS" and r.direction == "input" and r.element_id in right_ids}
    dc_consumer_names = tuple(axis.add(f"dc.consumer.{i}", ("power.inverter", i + 1))
                              for i in range(len(right_consumers))) if dc_active else ()
    ac_claims = {"ac_ports": ac_ports or ["origin"]}
    dc_claims = {"dc_source": slot_names["dc_source"], "dc_storage": slot_names["dc_storage"],
                 "dc_inputs": tuple(dc_inputs.values())}
    if dc_active:
        ac_claims["inverter"] = ["power.inverter"]
        dc_claims.update(inverter=["power.inverter"], dc_consumers=dc_consumer_names)
    power_names = [key for claims in (ac_claims, dc_claims) for names in claims.values() for key in names]
    axis.add("power.bottom", *((key, 0) for key in power_names))

    # Wärme: lokale Spaltenfolge und direkte DC-Verbraucher vor den eQ-Stacks anordnen.
    heat_stack_codes = list(areas["heat"].placement_order)
    offsets = {code: arrangements["heat_source"].column_offset(i) for i, code in enumerate(heat_stack_codes)}
    offsets.update({code: offset for code, offset in areas["heat"].column_overrides if code in offsets})
    column_cycle = arrangements["heat_source"].column_offsets
    last_offset = offsets[heat_stack_codes[-1]] if heat_stack_codes else None
    next_column_index = column_cycle.index(last_offset) + 1 if last_offset in column_cycle else 0
    heat_plus_offset = arrangements["heat_source"].column_offset(next_column_index)
    dc_heat_ids = {r.element_id for r in area_input.connections if r.bus_id == "DC_BUS" and r.direction == "input"}
    pre_eq = [code for code in heat_stack_codes if code not in RESOURCE_FOR_DEVICE]
    heat_names = {}
    axis.add("heat.dc_sources", relative("heat", "dc_sources"))
    for i, code in enumerate(code for code in pre_eq if code in dc_heat_ids):
        heat_names[code] = axis.add(f"heat.{code}", ("heat.dc_sources", i))
    if "STC" in pre_eq:
        alignment = "power.bottom" if dc_active or editing else "dc.source_start"
        heat_names["STC"] = axis.add("heat.STC", (alignment, 0), *(
            (key, NODE_TRACK_SIZE if offsets[code] == offsets["STC"] else 1)
            for code, key in heat_names.items()))
    for code in pre_eq:
        if code not in heat_names:
            heat_names[code] = axis.add(f"heat.{code}", *((key, 1) for key in heat_names.values()))
    pre_eq_bottom = [(key, 0) for key in heat_names.values()] or [("origin", -1)]
    axis.add("heat.pre_eq_bottom", *pre_eq_bottom)
    # BHKW-Leitungsband und eQ-Gruppen folgen den zuvor belegten Strom-/Wärmezeilen.
    chp_rule = areas["heat"].dependency("chp_ac")
    if coupled_codes:
        axis.add("heat.chp_ac", relative("heat", "chp_ac"), ("heat.pre_eq_bottom", chp_rule.distance))
        axis.add("heat.chp_bottom", ("heat.chp_ac", chp_rule.extent))
    else:
        axis.add("heat.chp_bottom", ("heat.pre_eq_bottom", 0))
    axis.add("heat.external_start", ("heat.chp_bottom", 1))
    predecessor = ("heat.external_start", 0)
    gas_heat_ids = {r.element_id for r in area_input.connections if r.bus_id == "GAS_BUS" and r.direction == "input"}
    for code in (code for code in heat_stack_codes if code in RESOURCE_FOR_DEVICE):
        heat_names[code] = axis.add(f"heat.{code}", predecessor,
                                    *((relative("gas", "power"),) if code in gas_heat_ids else ()))
        predecessor = (heat_names[code], 1)

    # Ressourcenbezüge am ersten Verbraucher ausrichten; Speicher und Zusatzports folgen.
    resource_ids = {resource[0] for resource in RESOURCE_FOR_DEVICE.values()}
    resource_source_ids = [key for key in areas["imports"].placement_order if key in resource_ids]
    external_names = {}
    for source_id in resource_source_ids:
        consumers = [key for code, key in heat_names.items()
                     if RESOURCE_FOR_DEVICE.get(code, (None,))[0] == source_id]
        if consumers:
            external_names[source_id] = axis.add(f"imports.{source_id}", *((key, 0) for key in consumers), reduce="min")
    if areas["gas"].active and "GAS_IMPORT" not in external_names:
        external_names["GAS_IMPORT"] = axis.add("imports.GAS_IMPORT", ("heat.external_start", 0), relative("gas", "power"))
    heat_plus_refs = [(key, 1) for key in heat_names.values()] or [relative("heat", "empty_source")]
    axis.add("heat.plus", *heat_plus_refs)
    slot_names["heat_source"] = tuple(heat_names.values()) + (("heat.plus",) if slot_has_plus["heat_source"] else ())
    heat_claims = {"heat_source": slot_names["heat_source"]}
    if coupled_codes:
        heat_claims["chp_ac"] = ("heat.chp_ac", "heat.chp_bottom")
    heat_base = [key for names in heat_claims.values() for key in names]
    axis.add("heat.storage_start", *((key, 1) for key in heat_base))
    heat_storage_end = allocate("heat_storage", ("heat.storage_start", 0))
    heat_claims["heat_storage"] = slot_names["heat_storage"]
    heat_base.extend(slot_names["heat_storage"])
    heat_ports = {}
    for code, distance in (("FC", 1), ("AC", 2)):
        if code in selected:
            heat_ports[code] = axis.add(f"heat.port.{code}",
                *((key, distance) for key in heat_base),
                *((key, 1) for key in heat_ports.values()),
                *( () if heat_base else (("origin", 0),)))
    heat_claims["heat_ports"] = tuple(heat_ports.values())
    axis.add("heat.bottom", *((key, 0) for names in heat_claims.values() for key in names))
    # Kälte schließt mit einer vollständigen Node-Zelle an die letzte Wärmezeile an.
    axis.add("cool.start", relative("cool", "heat"))
    cool_last = allocate("cool_source", ("cool.start", 0))
    cool_storage_end = allocate("cool_storage", (cool_last, 1))
    cool_claims = {"cool_source": slot_names["cool_source"], "cool_storage": slot_names["cool_storage"]}

    # Gas und H2 beziehen sich auf dieselben Bereichsanker einschließlich ihrer Controls.
    gas_import = external_names.get("GAS_IMPORT", "heat.external_start")
    gas_consumers = [heat_names[code] for code in heat_stack_codes if code in gas_heat_ids]
    axis.add("gas.GS", (gas_import, 1), *((relative("gas", "power"),) if editing and not areas["gas"].active else ()))
    gas_names = [gas_import, *gas_consumers, *(("gas.GS",) if "GS" in selected else ())]
    gas_ports = {}
    if "SAB" in selected:
        gas_ports["SAB"] = axis.add("gas.port.SAB", *((key, 1) for key in (["gas.GS"] if "GS" in selected else gas_names)))
    axis.add("gas.top", *((key, 0) for key in (gas_import, *gas_consumers)), reduce="min")
    axis.add("gas.bottom", *((key, 0) for key in gas_names), *((key, 0) for key in gas_ports.values()))
    axis.add("gas.controls_bottom", ("gas.bottom", 0), ("gas.GS", 1))
    # Die sichtbare Gasfläche und die aufgeklappten Controls teilen denselben
    # unteren Anker; die H2-Gruppe bindet an diesen statt an Pixelverschiebungen.
    axis.add("gas.occupied_bottom", ("gas.controls_bottom" if editing else "gas.bottom", 0))
    h2_order = tuple(code for code in areas["hydrogen"].placement_order if code in selected)
    h2_order += tuple(code for code in areas["hydrogen"].placement_order if editing and code not in selected)
    h2_codes = tuple(code for code in (*h2_order, "ELYZ") if code in selected)
    bridge = "ELYZ" in h2_codes and areas["gas"].active
    local_offsets = dict(areas["hydrogen"].local_track_offsets)
    first_offset = 0 if any(code in selected for code in h2_order) else local_offsets["ELYZ"]
    axis.add("hydrogen.start", relative("hydrogen", "gas"), relative("hydrogen", "power"),
             *((("gas.bottom", 3 - first_offset),) if bridge else ()))
    h2_names = {code: axis.add(f"hydrogen.{code}", ("hydrogen.start", i)) for i, code in enumerate(h2_order)}
    for code, offset in local_offsets.items():
        h2_names[code] = axis.add(f"hydrogen.{code}", ("hydrogen.start", offset))
    hydrogen_refs = [(h2_names[code], 0) for code in h2_codes] or [("hydrogen.start", 0)]
    axis.add("hydrogen.top", *hydrogen_refs, reduce="min")
    axis.add("hydrogen.bottom", *hydrogen_refs)
    # Die Last berücksichtigt alle belegten Komponenten, auch Quellen ohne Speicher.
    component_names = [key for claims in (ac_claims, dc_claims, heat_claims, cool_claims)
                       for names in claims.values() for key in names]
    component_names += [*(("power.plus",) if plus_name else ()), *external_names.values()]
    if areas["gas"].active:
        component_names.append("gas.bottom")
    component_names += [*h2_names.values(), "gas.GS"] if editing else [h2_names[code] for code in h2_codes]
    if "GS" in selected:
        component_names.append("gas.GS")
    axis.add("components.bottom", *((key, 0) for key in component_names))
    values = axis.resolve()

    def occupancy(claims: Mapping[str, Sequence[str]]) -> TrackOccupancy:
        """Übersetzt benannte Flächenansprüche in die gemeinsam gelösten Track-Werte."""

        return TrackOccupancy({owner: tuple(values[key] for key in names) for owner, names in claims.items() if names})

    ac, dc, heat, cool = map(occupancy, (ac_claims, dc_claims, heat_claims, cool_claims))
    # Portnachfrage wird vor Pillen, Gebäudekapazität und Routen aufgelöst.
    # Die belegten DC-Zeilen sind dabei bereits Teil derselben Achsenplanung.
    node_anchors = {**heat_names, **h2_names,
                    **dict(zip(slot_codes["cool_source"], slot_names["cool_source"]))}
    preferred = {code: values[node_anchors[code]] for code in right_consumers}
    consumer_order = sorted(right_consumers, key=lambda code: (
        0 if code in areas["heat"].element_ids else 1 if code in areas["cool"].element_ids else 2,
        preferred[code], code,
    ))
    dc_ports = {code: values[key] for code, key in dc_inputs.items()}
    if consumer_order:
        available = range(dc.span.first + 1, dc.span.last + 1)
        if len(available) < len(consumer_order):
            raise ValueError("Die DC-Belegung enthält zu wenige Anschlusszeilen")
        assignment = min(combinations(available, len(consumer_order)), key=lambda ports: (
            sum(track != preferred[code] for code, track in zip(consumer_order, ports) if code in heat_names),
            sum(abs(track - preferred[code]) for code, track in zip(consumer_order, ports) if code in heat_names),
            sum(abs(track - preferred[code]) for code, track in zip(consumer_order, ports)), ports,
        ))
        dc_ports.update(zip(consumer_order, assignment))
        dc.claims["dc_consumers"] = tuple(dc_ports[code] for code in consumer_order)
    values.update({f"dc.port.{code}": track for code, track in dc_ports.items()})
    # Pillen entstehen erst aus der vollständigen Belegung von Nodes, Controls und Ports.
    pill_spans = {name: occupancy.span for name, occupancy, visible in (
        ("ac", ac, True), ("dc", dc, dc_active), ("heat", heat, True),
        ("cool", cool, cold_active),
    ) if visible and occupancy.span is not None}
    pill_spans.setdefault("heat", TrackSpan(0, 0))
    if areas["gas"].active:
        pill_spans["gas_bus"] = TrackSpan(values["gas.top"], values["gas.bottom"])
    if h2_codes:
        pill_spans["hydrogen_bus"] = TrackSpan(values["hydrogen.top"], values["hydrogen.bottom"])
    return _ResolvedRows(
        ac_active=areas["power"].active, dc_active=dc_active, cold_active=cold_active,
        selected=selected,
        coupled_codes=coupled_codes,
        coupled_track_by_code={code: values[key] for code, key in coupled_names.items()},
        coupled_placeholder_track=values[plus_name] if plus_name else None,
        chp_ac_lane_track=values["heat.chp_ac"] if coupled_codes else None,
        chp_ac_lane_last_track=values["heat.chp_bottom"],
        chp_ac_track_by_code={code: values["heat.chp_ac"] for code in coupled_codes},
        dc_port_track_by_code=dc_ports,
        heat_port_track_by_code={code: values[key] for code, key in heat_ports.items()},
        heat_track_by_code={code: values[key] for code, key in heat_names.items()},
        heat_stack_codes=heat_stack_codes, heat_half_column_by_code=offsets,
        heat_plus_half_column=heat_plus_offset, heat_plus_track=values["heat.plus"],
        dc_storage_last=values[dc_storage_end], heat_storage_last=values[heat_storage_end],
        cool_start=values["cool.start"], cool_storage_last=values[cool_storage_end],
        external_start=values["heat.external_start"],
        external_source_track_by_id={code: values[key] for code, key in external_names.items()},
        slot_codes=slot_codes, slot_has_plus=slot_has_plus,
        slot_tracks={slot: [values[key] for key in names] for slot, names in slot_names.items()},
        pill_spans=pill_spans,
        ac_occupancy=ac, dc_occupancy=dc, heat_occupancy=heat, cool_occupancy=cool,
        row_anchors=values, hydrogen_order=h2_order, hydrogen_codes=h2_codes,
        gas_port_track_by_code={code: values[key] for code, key in gas_ports.items()},
        elyz_dc_lane_track_bounds=(values["gas.bottom"] + 1, values["gas.bottom"] + 2) if bridge else None,
    )


@dataclass(frozen=True)
class GridBox:
    """Begrenzung in Spalten und Halbzeilen; unabhängig vom Seitenverhältnis."""

    left: float
    top: int
    right: float
    bottom: int

    @classmethod
    def union(cls, boxes: Iterable[GridBox]) -> GridBox:
        """Liefert die kleinste umschließende Fläche; eine leere Eingabe löst ValueError aus."""

        items = tuple(boxes)
        if not items:
            raise ValueError("Eine Belegung benötigt mindestens eine Fläche")
        return cls(min(b.left for b in items), min(b.top for b in items),
                   max(b.right for b in items), max(b.bottom for b in items))


@dataclass(frozen=True)
class PlannedElement:
    """Geplante Node, Control- oder Auswahlfläche mit Bereichszugehörigkeit und logischer Belegung."""

    id: str
    area: str
    role: Literal["node", "control", "area"]
    shape: str
    position: GridPosition
    carrier: str
    footprint: GridBox


@dataclass(frozen=True)
class PlannedAttachment:
    """Ringelement auf dem Elternradius innerhalb der reservierten Gebäudezelle.

    Erst die Pixelprojektion bestimmt den Radius; hier werden Sichtbarkeit,
    Winkel und Rolle geplant.
    """

    parent_id: str
    key: str
    device_code: str
    carrier: str
    angle: float
    role: Literal["node", "control"]
    slot_index: int


@dataclass(frozen=True)
class _BuildingLayout:
    """Gewählte Gebäudeanordnung mit Gruppen, Ringelementen und ergänzten Zeilenankern."""

    positions: dict[str, GridPosition]
    groups: dict[str, tuple[int, ...]]
    attachments: tuple[PlannedAttachment, ...]
    row_anchors: dict[str, int]


@dataclass(frozen=True)
class PlannedSlot:
    """Logischer Slot-Anker mit Energieträger, Track-Abstand und Node-Form."""

    position: GridPosition
    carrier: str
    step_tracks: int = 1
    shape: str = "circle"


@dataclass(frozen=True)
class AreaDependency:
    """Relative Bindung an einen benannten Anker eines anderen Bereichs."""

    name: str
    reference: str
    axis: Literal["row", "column"]
    anchor: str
    distance: float
    extent: int = 0

    # Die Achsenprüfung verhindert das Vermischen von Zeilen- und Spaltenabhängigkeiten.
    def binding(self, axis: str) -> Anchor:
        """Liefert Ankername und Abstand; eine abweichende Rasterachse löst ValueError aus."""

        if self.axis != axis:
            raise ValueError(f"Abhängigkeit {self.name}: {self.axis} statt {axis}")
        return f"{self.reference}.{self.anchor}", self.distance


@dataclass(frozen=True)
class SlotArrangement:
    """Geräte, Controls und lokale Zeilen-/Spaltenfolge eines Slots vor der Koordinatenauflösung."""

    device_codes: tuple[str, ...]
    control_ids: tuple[str, ...]
    active: bool = True
    track_step: int = 1
    column_offsets: tuple[float, ...] = (0.0, 0.5)

    def column_offset(self, index: int) -> float:
        """Liefert den zyklisch wiederholten Spaltenversatz für den angegebenen Elementindex."""

        return self.column_offsets[index % len(self.column_offsets)]


@dataclass(frozen=True)
class PlannedArea:
    """Bereichsvorgabe vor der Platzierung, danach ergänzt um belegte Grenzen.

    Element- und Anschlusszugehörigkeit sowie lokale Reihenfolgen stehen ohne
    Koordinaten fest. ``bounds`` entsteht erst beim Auflösen dieser Vorgaben.
    """

    id: str
    element_ids: tuple[str, ...]
    bounds: GridBox | None = None
    active: bool = True
    slot_ids: tuple[str, ...] = ()
    placement_order: tuple[str, ...] = ()
    connection_order: tuple[str, ...] = ()
    dependencies: tuple[AreaDependency, ...] = ()
    connections: tuple[ConnectionRequest, ...] = ()
    column_overrides: tuple[tuple[str, float], ...] = ()
    local_track_offsets: tuple[tuple[str, int], ...] = ()
    packing: ColumnPacking | None = None

    def dependency(self, name: str) -> AreaDependency:
        """Liefert die benannte Bereichsabhängigkeit oder löst bei fehlender Vorgabe KeyError aus."""

        for dependency in self.dependencies:
            if dependency.name == name:
                return dependency
        raise KeyError(f"Bereich {self.id}: Abhängigkeit {name!r} fehlt")


@dataclass(frozen=True)
class ConnectionRequest:
    """Benötigter logischer Anschluss eines Elements an eine Buspille."""

    element_id: str
    bus_id: str
    carrier: str
    direction: Literal["input", "output"]
    track: int | None = None


@dataclass(frozen=True)
class AreaLayoutInput:
    """Koordinatenfreie Eingabe für die gemeinsame Bereichsplanung."""

    areas: dict[str, PlannedArea]
    slots: dict[str, SlotArrangement]
    connections: tuple[ConnectionRequest, ...]
    selected: tuple[str, ...]
    buildings: tuple[Mapping[str, Any], ...]
    grid_enabled: bool
    editing: bool


def _with_area_connections(
    areas: Mapping[str, PlannedArea], requests: Sequence[ConnectionRequest],
) -> dict[str, PlannedArea]:
    """Liefert Bereichskopien mit allen Anschlüssen, deren Endpunkte zum jeweiligen Bereich gehören."""

    return {key: replace(area, connections=tuple(
        request for request in requests
        if request.element_id in area.element_ids or request.bus_id in area.element_ids
    )) for key, area in areas.items()}


def define_area_layout(
    state: Mapping[str, Any], buildings: Sequence[Mapping[str, Any]] = (), *,
    force_dc: bool = False, force_cooling: bool = False,
    include_editing_placeholders: bool = True,
) -> AreaLayoutInput:
    """Beschreibt Bereiche und Anschlussbedarf, ohne Positionen zu berechnen.

    Fachliche Unterschiede stehen hier als Eingabe des gemeinsamen Planers.
    Die Abstände zählen Spalten bzw. Halbzeilen, keine Pixelverschiebungen.
    """
    selected = tuple(state.get("central_devices") or ())
    grid = bool(state.get("grid_enabled"))
    editing = include_editing_placeholders
    dc = has_dc_system(selected) or force_dc
    cool = has_cooling_system(selected) or force_cooling
    coupled = tuple(ordered_slot_devices(state, "coupled_source"))
    power = grid or dc or bool(coupled)
    gas = any("gas" in (*CENTRAL_DEVICES[code].get("inputs", ()),
                        *CENTRAL_DEVICES[code].get("outputs", ()))
              for code in selected)
    h2_order = ("SAB", "FC", "H2S")
    hydrogen = any(code in selected for code in (*h2_order, "ELYZ"))
    # Gewählte Geräte und sichtbare Plus-Plätze pro Slot erfassen.
    slots = {}
    for slot in (
        "coupled_source", "dc_source", "dc_storage", "heat_source", "heat_storage",
        "cool_source", "cool_storage", "hydrogen_converter",
        "hydrogen_storage", "gas_storage", "electric_source",
    ):
        codes = tuple(ordered_slot_devices(state, slot)) if slot != "electric_source" else ()
        controls = (slot,) if editing and unused_candidates(slot, selected, grid) else ()
        if slot == "coupled_source":
            controls = ()  # Bedienung des BHKW-Stacks erfolgt über electric_source.
        elif slot in ("hydrogen_converter", "hydrogen_storage", "gas_storage"):
            controls = tuple(key for key, code in INDIVIDUAL_COMPONENT_CONTROLS.items()
                             if editing and code not in selected
                             and CENTRAL_DEVICES[code]["slot"] == slot)
        active = True
        if slot.startswith("dc_"):
            active = dc
        elif slot.startswith("cool_"):
            active = cool
        slots[slot] = SlotArrangement(codes, controls, active)
    cool_visible = cool and (editing or any(
        slots[key].device_codes for key in ("cool_source", "cool_storage")
    ))

    # eQ-Reihenfolge und Bereichszugehörigkeit unabhängig von Positionen festlegen.
    resources = list(dict.fromkeys(RESOURCE_FOR_DEVICE[code][0]
                                  for code in selected if code in RESOURCE_FOR_DEVICE))
    resources = [*(key for key in HEAT_RESOURCE_STACK_ORDER if key in resources),
                 *(key for key in resources if key not in HEAT_RESOURCE_STACK_ORDER)]
    heat_codes = slots["heat_source"].device_codes
    heat_order = (
        *(code for code in heat_codes if code not in RESOURCE_FOR_DEVICE),
        *(code for resource in resources for code in (*coupled, *heat_codes)
          if RESOURCE_FOR_DEVICE.get(code, (None,))[0] == resource),
    )
    imports = tuple(dict.fromkeys((
        *(("GRID",) if grid else ()), *resources,
        *(("GAS_IMPORT",) if gas else ()), *(("H2_IMPORT",) if hydrogen else ()),
    )))

    def members(*slot_ids: str) -> tuple[str, ...]:
        """Liefert Geräte- und Control-IDs der angegebenen Slots in ihrer lokalen Reihenfolge."""

        return tuple(key for slot in slot_ids
                     for key in (*slots[slot].device_codes, *slots[slot].control_ids))

    areas = {
        "power": PlannedArea("power", (
            *(("AC_BUS",) if power or editing else ()),
            *(("INVERTER",) if dc else ()), *slots["electric_source"].control_ids,
        ), active=power, slot_ids=("electric_source",),
            connection_order=coupled),
        "dc": PlannedArea("dc", (
            *(("DC_BUS",) if dc else ()), *members("dc_source", "dc_storage"),
            *(("dc_area",) if editing and not dc else ()),
        ), active=dc, slot_ids=("dc_source", "dc_storage"),
            dependencies=(
                AreaDependency("source_start", "power", "row", "ports", 2),
                AreaDependency("sources", "power", "column", "entry_right", 1),
                AreaDependency("storage", "dc", "column", "sources_right", 1),
                AreaDependency("bus", "dc", "column", "components_right", 1.5),
            )),
        "heat": PlannedArea("heat", (
            "HEAT_GRID", *coupled, *members("heat_source", "heat_storage"),
        ), slot_ids=("heat_source", "heat_storage"),
            placement_order=heat_order, column_overrides=(("STC", 0.0),),
            dependencies=(
                AreaDependency("empty_source", "power", "row", "bottom", 1),
                AreaDependency("dc_sources", "dc", "row", "source_start", 0),
                AreaDependency("chp_ac", "power", "row", "bottom", 1, extent=1),
                AreaDependency("power", "power", "column", "right", 1.5),
                AreaDependency("imports", "imports", "column", "center", 1),
                AreaDependency("storage", "heat", "column", "sources_right", 1),
                AreaDependency("network", "heat", "column", "components_right", 1.5),
            )),
        "cool": PlannedArea("cool", (
            *(("COOL_GRID",) if cool_visible else ()), *members("cool_source", "cool_storage"),
            *(("cool_area",) if editing and not cool else ()),
        ), active=cool, slot_ids=("cool_source", "cool_storage"),
            dependencies=(
                AreaDependency("heat", "heat", "row", "bottom", NODE_TRACK_SIZE),
                AreaDependency("storage", "cool", "column", "sources_right", 1),
                AreaDependency("network", "cool", "column", "components_right", 1.5),
            )),
        "gas": PlannedArea("gas", (
            *(("GAS_BUS",) if gas else ()), *members("gas_storage"),
        ), active=gas, slot_ids=("gas_storage",),
            dependencies=(AreaDependency("power", "power", "row", "bottom", NODE_TRACK_SIZE),)),
        "hydrogen": PlannedArea("hydrogen", (
            *(("H2_BUS",) if hydrogen else ()),
            *members("hydrogen_converter", "hydrogen_storage"),
        ), active=hydrogen, placement_order=h2_order,
            slot_ids=("hydrogen_converter", "hydrogen_storage"),
            local_track_offsets=(("ELYZ", 2),), dependencies=(
                AreaDependency("bus", "imports", "column", "frame", 1),
                AreaDependency("stack", "hydrogen", "column", "bus", 1.5),
                AreaDependency("gas", "gas" if gas or editing else "scene", "row",
                               "occupied_bottom" if gas or editing else "origin", NODE_TRACK_SIZE if gas or editing else 0),
                AreaDependency("power", "power" if power or editing else "scene", "row",
                               "bottom" if power or editing else "origin", NODE_TRACK_SIZE if power or editing else 0),
            )),
        "imports": PlannedArea("imports", imports, active=bool(imports), placement_order=imports),
        "load": PlannedArea("load", ("LOAD",), dependencies=(
            AreaDependency("network", "heat", "column", "network", 1.5),
            AreaDependency("components", "components", "row", "bottom", 0),
            AreaDependency("buildings", "buildings", "row", "bottom", 0),
        )),
        "buildings": PlannedArea("buildings", (
            *(f"BUILDING:{int(row.get('uid', index))}" for index, row in enumerate(buildings)),
            *(("building",) if editing else ()),
        ), packing=ColumnPacking(max_columns=MAX_BUILDING_COLUMNS), dependencies=(
            AreaDependency("load", "load", "column", "right", 1.5),
            AreaDependency("capacity", "components", "row", "bottom", BUILDING_EXTRA_TRACKS if selected else 0),
        )),
        "additional": PlannedArea("additional", (
            ("other_area",) if editing and not set(selected).intersection(
                INDIVIDUAL_COMPONENT_CONTROLS.values()) else ()
        )),
    }
    # Anschlussbedarf aus dem Gerätekatalog und den Gebäudeversorgungen ableiten.
    requests = []
    carrier_bus = {"dc": "DC_BUS", "power": "AC_BUS", "heat": "HEAT_GRID",
                   "cool": "COOL_GRID", "gas": "GAS_BUS", "hydrogen": "H2_BUS"}
    visible_ids = {key for area in areas.values() for key in area.element_ids}
    for code in selected:
        for direction, key in (("input", "inputs"), ("output", "outputs")):
            for carrier in CENTRAL_DEVICES[code].get(key, ()):
                bus = carrier_bus.get(carrier) or RESOURCE_FOR_DEVICE.get(code, (None,))[0]
                if bus in visible_ids:
                    requests.append(ConnectionRequest(code, bus, carrier, direction))
    for carrier, bus in (("power", "AC_BUS"), ("heat", "HEAT_GRID"), ("cool", "COOL_GRID")):
        if bus in visible_ids:
            requests.append(ConnectionRequest("LOAD", bus, carrier, "input"))
    if dc:
        requests.extend((ConnectionRequest("INVERTER", "AC_BUS", "power", "input"),
                         ConnectionRequest("INVERTER", "DC_BUS", "dc", "output")))
    for index, row in enumerate(buildings):
        requests.extend(ConnectionRequest(f"BUILDING:{int(row.get('uid', index))}",
                                          "LOAD", carrier, "input")
                        for carrier in _building_carriers(row, cool_visible))
    for source_id in imports:
        bus = {"GRID": "AC_BUS", "GAS_IMPORT": "GAS_BUS", "H2_IMPORT": "H2_BUS"}.get(source_id)
        if bus in visible_ids:
            requests.append(ConnectionRequest(source_id, bus,
                {"GRID": "power", "GAS_IMPORT": "gas", "H2_IMPORT": "hydrogen"}[source_id], "output"))
    areas = _with_area_connections(areas, requests)
    return AreaLayoutInput(areas, slots, tuple(requests), selected, tuple(buildings), grid, editing)


@dataclass(frozen=True)
class PlannedLaneGroup:
    """Geordnete Leitungen innerhalb einer vor der Projektion belegten Fläche."""

    axis: Literal["x", "y"]
    bounds: GridBox
    keys: tuple[str, ...]


@dataclass(frozen=True)
class PlannedRoute:
    """Logische Verbindung mit Pfadtyp, Anschlusszeilen und Verweisen auf Leitungsspuren."""

    id: str
    source: str
    target: str
    carrier: str
    kind: Literal["straight", "dc", "hvh", "akm", "chp", "elyz", "resource", "external"]
    source_track: float
    target_track: float
    # Versatz in Linienbreiten für die optionale zentrierte Portdarstellung.
    source_offset: float = 0.0
    target_offset: float = 0.0
    # (Pfadparameter, Spurkorridor, Schlüssel innerhalb des Korridors)
    lanes: tuple[tuple[str, str, str], ...] = ()

    @property
    def corridor_ids(self) -> tuple[str, ...]:
        """Liefert die eindeutigen Korridor-IDs, die diese Route belegt."""

        return ("external_sources",) if self.kind == "external" else tuple(dict.fromkeys(
            group for _, group, _ in self.lanes
        ))


@dataclass(frozen=True)
class TopologyLayoutPlan:
    """Gemeinsame Belegung; keine Pixelgrößen, Canvas oder Rendererobjekte."""

    elements: dict[str, PlannedElement]
    areas: dict[str, PlannedArea]
    attachments: tuple[PlannedAttachment, ...]
    connections: tuple[ConnectionRequest, ...]
    corridors: dict[str, GridBox]
    slots: dict[str, PlannedSlot]
    reserved_positions: dict[str, GridPosition]
    columns: dict[str, float]
    pill_spans: dict[str, TrackSpan]
    building_groups: dict[str, tuple[int, ...]]
    occupied_bounds: GridBox = field(init=False)
    active_external_source_ids: tuple[str, ...]
    external_source_offset: float
    gas_port_track_by_code: dict[str, int]
    elyz_dc_lane_track_bounds: tuple[int, int] | None
    tracks: _ResolvedRows
    routes: tuple[PlannedRoute, ...] = ()
    lane_groups: dict[str, PlannedLaneGroup] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Leitet alle Grenzen aus derselben endgültigen Belegung ab.

        Auch ``replace`` eines Plans aktualisiert diese abgeleiteten Daten.
        Unbenutzte Kapazitäten und reservierte Zielpositionen zählen nicht.
        """
        route_boxes = []
        owners: dict[str, list[GridBox]] = {key: [] for key in self.areas}
        groups = dict(self.lane_groups)
        # Vertikale Korridore reichen nur über tatsächlich genutzte Anschluss- und Querzeilen.
        for name, group in groups.items():
            if group.axis != "x":
                continue
            related = [route for route in self.routes if name in route.corridor_ids]
            tracks = [track for route in related for track in (route.source_track, route.target_track)]
            for route in related:
                for _, other, _ in route.lanes:
                    band = self.lane_groups[other]
                    if band.axis == "y":
                        tracks.extend((band.bounds.top, band.bounds.bottom))
            if tracks:
                groups[name] = replace(group, bounds=replace(group.bounds, top=min(tracks), bottom=max(tracks)))
        corridors = {**self.corridors, **{name: group.bounds for name, group in groups.items()}}
        # Jede Kante belegt Fläche in den Bereichen ihrer beiden Endpunkte.
        for route in self.routes:
            source, target = self.elements[route.source], self.elements[route.target]
            box = GridBox(min(source.position.column, target.position.column),
                          min(route.source_track, route.target_track),
                          max(source.position.column, target.position.column),
                          max(route.source_track, route.target_track))
            claims = [box, *(corridors[name] for name in route.corridor_ids)]
            for owner in {source.area, target.area}:
                owners[owner].extend(claims)
            route_boxes.append(box)
        # Sichtbare Mitglieder und ihre Kanten bestimmen Bereichs- und Szenengrenzen.
        areas = {}
        for name, specification in self.areas.items():
            members = tuple(key for key, element in self.elements.items() if element.area == name)
            if members:
                areas[name] = replace(specification, element_ids=members,
                    bounds=GridBox.union([*(self.elements[key].footprint for key in members), *owners[name]]))
        object.__setattr__(self, "areas", _with_area_connections(areas, self.connections))
        object.__setattr__(self, "lane_groups", groups)
        object.__setattr__(self, "corridors", corridors)
        object.__setattr__(self, "occupied_bounds", GridBox.union([
            *(element.footprint for element in self.elements.values()), *corridors.values(), *route_boxes,
        ]))

    @property
    def column_origin(self) -> float:
        """Mittelpunkt der ersten belegten Spalte im logischen Raster."""

        return self.occupied_bounds.left + 0.5

    @property
    def column_count(self) -> float:
        """Gesamte belegte Breite in logischen Spalteneinheiten."""

        return self.occupied_bounds.right - self.occupied_bounds.left

    @property
    def max_row_track(self) -> int:
        """Letzter Zellmittelpunkt-Track der belegten Szenenhöhe."""

        return self.occupied_bounds.bottom - 1


def _resolve_columns(area_input: AreaLayoutInput, tracks: _ResolvedRows) -> dict[str, float]:
    """Packt sichtbare Gruppen und Routingflächen über relative Kantenanker."""
    areas, arrangements = area_input.areas, area_input.slots
    axis = AxisPlan("column")
    axis.add("origin")

    def relative(area: str, rule: str) -> Anchor:
        """Liest den benannten Spaltenbezug eines Bereichs als Anker und Abstand."""

        return areas[area].dependency(rule).binding("column")

    def offsets(slot: str) -> tuple[float, ...]:
        """Liefert die sichtbaren lokalen Spaltenversätze eines Slots einschließlich Controls."""

        arrangement = arrangements[slot]
        if not arrangement.active and not area_input.editing:
            return ()
        if slot == "heat_source":
            return (*tracks.heat_half_column_by_code.values(),
                    *((tracks.heat_plus_half_column,) if arrangement.control_ids else ()))
        count = len(arrangement.device_codes) + len(arrangement.control_ids)
        return tuple(arrangement.column_offset(i) for i in range(count))

    visible = {slot: offsets(slot) for slot in
               ("dc_source", "dc_storage", "heat_source", "heat_storage", "cool_source", "cool_storage")}
    # Eintritt und BHKW-Leitungsbündel sind belegte halbe Routing-Spalten.
    # Sie werden nur angelegt, wenn die zugehörigen Quellen/Leitungen existieren.
    axis.add("imports.center", ("origin", .5 if areas["imports"].element_ids else 0))
    axis.add("imports.frame", ("imports.center", .5 if areas["hydrogen"].active else 0))
    ac_count = int(area_input.grid_enabled) + len(tracks.coupled_codes) + int(tracks.coupled_placeholder_track is not None)
    ac_width = max((arrangements["electric_source"].column_offset(i) for i in range(ac_count)), default=0)
    axis.add("power.entry_right", ("imports.frame", ac_width + (.5 if tracks.coupled_codes else 0)))
    axis.add("hydrogen.bus", relative("hydrogen", "bus"))
    axis.add("hydrogen.stack", relative("hydrogen", "stack"))
    axis.add("dc.sources", relative("dc", "sources"))
    axis.add("dc.sources_right", ("dc.sources", max(visible["dc_source"], default=0)))
    storage_binding = relative("dc", "storage") if visible["dc_source"] else ("power.entry_right", 1)
    axis.add("dc.storage", storage_binding)
    dc_right = []
    for slot, anchor in (("dc_source", "dc.sources"), ("dc_storage", "dc.storage")):
        dc_right.extend((anchor, offset) for offset in visible[slot])
    # Gas und DC teilen eine Busspalte. GS nutzt die vorhandene Speicherspalte.
    gs_visible = any(key in areas["gas"].element_ids for key in ("GS", "gas_storage:GS"))
    if gs_visible:
        dc_right.append(("dc.storage", 0))
    axis.add("dc.components_right", *(dc_right or [("power.entry_right", 0)]))
    bus_constraints = [relative("dc", "bus")]
    if "FC" in tracks.hydrogen_codes:
        index = tracks.hydrogen_order.index("FC")
        bus_constraints.append(("hydrogen.stack", arrangements["hydrogen_converter"].column_offset(index) + 1))
    axis.add("power.right", *bus_constraints)

    # Wärme-/Kältequellen müssen rechts von ihren tatsächlich vorhandenen Nachbarn liegen.
    converter_constraints = []
    if any(request.bus_id in areas["imports"].element_ids
           for request in areas["heat"].connections):
        converter_constraints.append(relative("heat", "imports"))
    if any(key in areas[area].element_ids for area, key in
           (("power", "AC_BUS"), ("dc", "DC_BUS"), ("gas", "GAS_BUS"))):
        converter_constraints.append(relative("heat", "power"))
    h2_member_codes = {*areas["hydrogen"].element_ids,
                       *(INDIVIDUAL_COMPONENT_CONTROLS[key] for key in areas["hydrogen"].element_ids
                         if key in INDIVIDUAL_COMPONENT_CONTROLS)}
    h2_visible = [code for code in tracks.hydrogen_order if code in h2_member_codes]
    if h2_visible:
        converter_constraints.append(("hydrogen.stack", max(
            arrangements["hydrogen_converter"].column_offset(tracks.hydrogen_order.index(code))
            for code in h2_visible) + 1.5))
    axis.add("heat.sources", *(converter_constraints or [("imports.frame", 0)]))
    axis.add("cool.sources", ("heat.sources", 0))
    for area in ("heat", "cool"):
        axis.add(f"{area}.sources_right", (f"{area}.sources", max(visible[f"{area}_source"], default=0)))
        axis.add(f"{area}.storage", relative(area, "storage"))
        claims = [(f"{area}.sources", offset) for offset in visible[f"{area}_source"]]
        claims += [(f"{area}.storage", offset) for offset in visible[f"{area}_storage"]]
        axis.add(f"{area}.components_right", *(claims or [(f"{area}.sources", 0)]))
    # Netze, Last und Gebäude folgen dem äußersten belegten Wärme-/Kälteelement.
    thermal_constraints = [areas[area].dependency("network").binding("column")
                           for area in ("heat", "cool")
                           if visible[f"{area}_source"] or visible[f"{area}_storage"]]
    axis.add("heat.network", *(thermal_constraints or [("heat.sources", 0)]))
    axis.add("load.right", relative("load", "network"))
    axis.add("buildings.left", relative("buildings", "load"))
    values = axis.resolve()
    return {key: values[anchor] for key, anchor in {
        "resource": "imports.center", "ac_source": "imports.center",
        "dc_source": "dc.sources", "dc_storage": "dc.storage", "power_bus": "power.right",
        "converter": "heat.sources", "storage": "heat.storage", "cool_storage": "cool.storage",
        "network": "heat.network", "load": "load.right", "building": "buildings.left",
        "hydrogen_bus": "hydrogen.bus", "hydrogen_stack": "hydrogen.stack",
    }.items()}


def _resolve_buildings(
    area_input: AreaLayoutInput, tracks: _ResolvedRows, column: float,
) -> _BuildingLayout:
    """Bewertet zulässige Spaltenbelegungen und löst die Last danach auf.

    Ungenutzte Kapazität belegt keine Fläche. Die gewählte Variante zeigt
    möglichst viele einzelne Gebäude und braucht dafür möglichst wenige
    Spalten. Sammelgruppen und Controls zählen jeweils als vollständige Zelle.
    """
    specification = area_input.areas["buildings"]
    packing = specification.packing
    if packing is None:
        raise ValueError("Die Bereichsvorgabe für Gebäude benötigt eine Spaltenanordnung")
    # Die zentrale Belegung bleibt fest; Gebäude ergänzen deren benannte Zeilenanker.
    axis = AxisPlan("row")
    axis.add("origin")
    for name, value in tracks.row_anchors.items():
        if name != "origin":
            axis.add(name, ("origin", value))
    minimum_items = len({_building_is_decentral(dict(row)) for row in area_input.buildings}) + int(area_input.editing)
    axis.add("buildings.capacity", specification.dependency("capacity").binding("row"),
             ("origin", packing.minimum_last_track(minimum_items)))
    last_track = axis.resolve()["buildings.capacity"]
    # Möglichst viele Einzelgebäude zeigen; bei Gleichstand weniger Spalten verwenden.
    variants = []
    for count in range(1, packing.max_columns + 1):
        cells = packing.slots(last_track, count)
        if len(cells) < minimum_items:
            continue
        visible, groups = _visible_building_plan(
            area_input.buildings, capacity=len(cells), include_editing_placeholder=area_input.editing,
        )
        ids = [f"BUILDING:{int(row.get('uid', index))}" for index, row in enumerate(visible)]
        ids.extend(f"BUILDING_GROUP:{name.upper()}" for name in groups)
        if area_input.editing:
            ids.append("building")
        positions = {key: GridPosition(column + offset, track)
                     for key, (offset, track) in zip(ids, cells)}
        variants.append(((-len(visible), count), positions, groups, visible))
        if len(visible) == len(area_input.buildings):
            break
    _, positions, groups, visible = min(variants, key=lambda variant: variant[0])
    # Nur die gewählte Belegung beeinflusst Last und Gebäuderinge.
    for key, position in positions.items():
        axis.add(f"buildings.{key}", ("origin", position.row_track))
    axis.add("buildings.bottom", *((f"buildings.{key}", 0) for key in positions))
    axis.add("load.bottom", *(area_input.areas["load"].dependency(name).binding("row")
                              for name in ("components", "buildings")))
    attachments = tuple(
        PlannedAttachment(f"BUILDING:{int(row.get('uid', index))}", placement.key,
                          placement.code, placement.carrier, placement.angle,
                          "node" if placement.code else "control", placement.slot_index)
        for index, row in enumerate(visible)
        for placement in building_ring_placements(row, radius=1, include_available=area_input.editing)
    )
    return _BuildingLayout(positions, groups, attachments, axis.resolve())


def plan_topology_layout(
    state: Mapping[str, Any], buildings: Sequence[Mapping[str, Any]] = (), *,
    force_dc: bool = False, force_cooling: bool = False,
    include_editing_placeholders: bool = True,
    area_input: AreaLayoutInput | None = None,
) -> TopologyLayoutPlan:
    """Plant Bereiche, Elemente, Anschlüsse und Korridore im gemeinsamen Raster."""

    if area_input is None:
        area_input = define_area_layout(
            state, buildings, force_dc=force_dc, force_cooling=force_cooling,
            include_editing_placeholders=include_editing_placeholders,
        )
    # Erst beide Achsen und die Gebäude lösen; danach nur noch geplante Anker auslesen.
    buildings = area_input.buildings
    editing = area_input.editing
    area_specs = area_input.areas
    tracks = _resolve_rows(area_input)
    pill_spans = dict(tracks.pill_spans)
    dc_span = pill_spans.get("dc")
    selected = tracks.selected
    slot_codes = tracks.slot_codes
    slot_has_plus = tracks.slot_has_plus
    slot_tracks = tracks.slot_tracks

    rows = tracks.row_anchors
    h2_right_visual_order = tracks.hydrogen_order
    h2_codes = tracks.hydrogen_codes
    h2_track_by_code = {code: rows[f"hydrogen.{code}"]
                        for code in (*h2_right_visual_order, "ELYZ")}
    h2_start_track, h2_end_track = rows["hydrogen.top"], rows["hydrogen.bottom"]
    gs_track = rows["gas.GS"]
    active_external_source_ids = list(area_specs["imports"].placement_order)

    columns = _resolve_columns(area_input, tracks)
    building_layout = _resolve_buildings(area_input, tracks, columns["building"])
    tracks = replace(tracks, row_anchors=building_layout.row_anchors)
    building_groups = building_layout.groups
    external_source_offset = shared_source_column = columns["resource"]
    converter_column, heat_storage_column = columns["converter"], columns["storage"]
    cool_storage_column, network_column = columns["cool_storage"], columns["network"]
    load_column, building_column = columns["load"], columns["building"]
    elements: dict[str, PlannedElement] = {}
    corridors: dict[str, GridBox] = {}
    slots: dict[str, PlannedSlot] = {}
    area_by_element = {key: area.id for area in area_specs.values() for key in area.element_ids}

    def add_element(element_id: str, column: float, track: int,
                    carrier: str, *, role: str = "node", shape: str = "circle",
                    footprint: GridBox | None = None) -> None:
        """Registriert ein Element mit vorgegebener Bereichszugehörigkeit und logischer Zellfläche."""

        elements[element_id] = PlannedElement(
            element_id, area_by_element[element_id], role, shape, GridPosition(column, track), carrier,
            footprint or GridBox(column - .5, track - 1, column + .5, track + 1),
        )

    def add_slot(slot: str, column: float, carrier: str, empty_start: int = 0) -> None:
        """Registriert Slot-Metadaten sowie die geplanten Nodes und den sichtbaren Plus-Platz."""

        arrangement = area_input.slots[slot]
        active = arrangement.active
        start = min(slot_tracks[slot], default=empty_start)
        slots[slot] = PlannedSlot(GridPosition(column, start), carrier, arrangement.track_step)
        codes = slot_codes[slot] if active else []
        for index, code in enumerate(codes):
            track = tracks.heat_track_by_code[code] if slot == "heat_source" else slot_tracks[slot][index]
            offset = tracks.heat_half_column_by_code[code] if slot == "heat_source" else arrangement.column_offset(index)
            add_element(code, column + offset, track, carrier)
        if editing and ((slot_has_plus[slot] and active) or not active):
            index = len(tracks.heat_stack_codes) if slot == "heat_source" else len(codes)
            track = tracks.heat_plus_track if slot == "heat_source" else slot_tracks[slot][min(index, len(slot_tracks[slot]) - 1)]
            offset = tracks.heat_plus_half_column if slot == "heat_source" else arrangement.column_offset(index)
            add_element(slot, column + offset, track, carrier, role="control")

    # Zentrale Nodes und Plus-Plätze belegen dieselben zuvor gelösten Slot-Anker.
    slots["electric_source"] = PlannedSlot(GridPosition(shared_source_column, 0), "power", 2)
    slots["coupled_source"] = PlannedSlot(GridPosition(converter_column, tracks.external_start), "heat")
    add_slot("dc_source", columns["dc_source"], "dc")
    add_slot("dc_storage", columns["dc_storage"], "dc", tracks.dc_storage_last)
    add_slot("heat_source", converter_column, "heat")
    add_slot("heat_storage", heat_storage_column, "heat", tracks.heat_storage_last)
    add_slot("cool_source", converter_column, "cool", tracks.cool_start)
    add_slot("cool_storage", cool_storage_column, "cool", tracks.cool_storage_last)
    for code in tracks.coupled_codes:
        add_element(code, converter_column + tracks.heat_half_column_by_code[code], tracks.heat_track_by_code[code], "heat")
    if tracks.coupled_placeholder_track is not None:
        offset = area_input.slots["electric_source"].column_offset(tracks.coupled_placeholder_track)
        add_element("electric_source", shared_source_column + offset, tracks.coupled_placeholder_track, "power", role="control")

    # Gas-/H2-Nodes und Ressourcenbezüge verwenden die gemeinsamen Zeilen- und Spaltenanker.
    if h2_codes:
        slots["hydrogen_stack"] = PlannedSlot(GridPosition(columns["hydrogen_stack"], h2_start_track), "hydrogen")
    h2_column_by_code = {
        code: columns["hydrogen_stack"] + area_input.slots["hydrogen_converter"].column_offset(index)
        for index, code in enumerate(h2_right_visual_order)
    }
    h2_column_by_code["ELYZ"] = shared_source_column
    reserved_positions = {"GS": GridPosition(columns["dc_storage"], gs_track)}
    reserved_positions.update({code: GridPosition(column, h2_track_by_code[code]) for code, column in h2_column_by_code.items()})
    for source_id in active_external_source_ids:
        if source_id == "GRID":
            source_track, carrier = 0, "power"
        elif source_id == "H2_IMPORT":
            elyz_track = h2_track_by_code["ELYZ"] if "ELYZ" in h2_codes else None
            spacing = 2 if h2_end_track - h2_start_track >= 2 else 1
            source_track = h2_start_track if elyz_track is None else elyz_track - spacing
            carrier = "hydrogen"
        else:
            source_track = tracks.external_source_track_by_id[source_id]
            carrier = "gas" if source_id == "GAS_IMPORT" else next(
                resource[1] for resource in RESOURCE_FOR_DEVICE.values() if resource[0] == source_id
            )
        add_element(source_id, shared_source_column, source_track, carrier)
    for code in (*h2_codes, *(("GS",) if "GS" in selected else ())):
        pos = reserved_positions[code]
        add_element(code, pos.column, pos.row_track,
                    "gas" if code == "GS" else "hydrogen")
    if editing:
        for control_id, code in INDIVIDUAL_COMPONENT_CONTROLS.items():
            if code not in selected:
                pos = reserved_positions[code]
                carrier = str((CENTRAL_DEVICES[code].get("outputs") or CENTRAL_DEVICES[code]["inputs"])[0])
                add_element(control_id, pos.column, pos.row_track, carrier, role="control")

    # Pillen übernehmen die endgültigen Spannen ihrer belegten Nodes und Anschlüsse.
    pill_definitions = {
        "ac": ("AC_BUS", "power", columns["power_bus"]),
        "dc": ("DC_BUS", "dc", columns["power_bus"]),
        "heat": ("HEAT_GRID", "heat", network_column),
        "cool": ("COOL_GRID", "cool", network_column),
        "gas_bus": ("GAS_BUS", "gas", columns["power_bus"]),
        "hydrogen_bus": ("H2_BUS", "hydrogen", columns["hydrogen_bus"]),
    }
    for key, span in pill_spans.items():
        if key == "ac" and not (tracks.ac_active or editing):
            continue
        node_id, area, column = pill_definitions[key]
        add_element(node_id, column, span.first, area, shape="pill",
                    footprint=GridBox(column - .5, span.first - 1, column + .5, span.last + 1))
        slots[key] = PlannedSlot(GridPosition(column, span.first), area, shape="pill")
    if dc_span is not None:
        add_element("INVERTER", columns["power_bus"], dc_span.first, "neutral", shape="pill")

    # Routingflächen tragen zum selben Flächenmodell bei wie Nodes/Controls.
    if active_external_source_ids:
        source_tracks = [elements[source_id].position.row_track for source_id in active_external_source_ids]
        corridors["external_sources"] = GridBox(-.5, min(source_tracks) - 1, shared_source_column - .5, max(source_tracks) + 1)
    if tracks.coupled_codes:
        corridors["chp_ac"] = GridBox(columns["dc_source"] - 1, tracks.chp_ac_lane_track,
                                       converter_column + 1.5, tracks.chp_ac_lane_last_track)
    if tracks.elyz_dc_lane_track_bounds is not None:
        top, bottom = tracks.elyz_dc_lane_track_bounds
        corridors["elyz_dc"] = GridBox(shared_source_column - .5, top, columns["power_bus"] + .5, bottom)
    if "AC" in selected and not tracks.ac_active:
        akm = elements["AC"].position
        corridors["AC:heat"] = GridBox(akm.column - 1, pill_spans["heat"].last, akm.column - .5, akm.row_track)

    # Aufgeklappte Auswahlflächen zählen nur im editierbaren Konfigurator zur Belegung.
    if editing and not tracks.dc_active:
        add_element("dc_area", columns["dc_source"], 1, "dc", role="area", shape="area",
                    footprint=GridBox(columns["dc_source"] - .5, 0, columns["power_bus"] + .5, tracks.dc_storage_last + 1))
    if editing and not tracks.cold_active:
        add_element("cool_area", converter_column, tracks.cool_start, "cool", role="area", shape="area",
                    footprint=GridBox(converter_column - .5, tracks.cool_start - 1,
                                      network_column + .5, tracks.cool_storage_last + 1))
    if editing and not (set(INDIVIDUAL_COMPONENT_CONTROLS.values()) & set(selected)):
        controls = [elements[key].footprint for key in INDIVIDUAL_COMPONENT_CONTROLS if key in elements]
        if controls:
            box = GridBox.union(controls)
            add_element("other_area", box.left + .5, box.top + 1, "neutral", role="area", shape="area", footprint=box)

    # Gebäude, Sammelgruppen und Last verwenden ausschließlich die gewählte Gebäudeanordnung.
    for element_id, position in building_layout.positions.items():
        if element_id.startswith("BUILDING_GROUP:"):
            area_by_element[element_id] = "buildings"
        add_element(element_id, position.column, position.row_track, "neutral",
                    role="control" if element_id == "building" else "node", shape="building")
    slots["building"] = PlannedSlot(GridPosition(building_column, 0), "neutral",
                                    area_specs["buildings"].packing.row_step, "building")
    load_span = TrackSpan(0, building_layout.row_anchors["load.bottom"])
    pill_spans["load"] = load_span
    add_element("LOAD", load_column, 0, "neutral", shape="pill",
                footprint=GridBox(load_column - .5, -1, load_column + .5, load_span.last + 1))

    requests = []
    port_tracks = {"DC_BUS": tracks.dc_port_track_by_code, "HEAT_GRID": tracks.heat_port_track_by_code,
                   "GAS_BUS": tracks.gas_port_track_by_code, "AC_BUS": tracks.coupled_track_by_code}
    # Der Anschlussbedarf wurde vor der Platzierung ermittelt. Hier werden
    # ausschließlich sichtbare Endpunkte und ihre geplanten Tracks aufgelöst.
    for request in area_input.connections:
        if request.element_id not in elements or request.bus_id not in elements:
            continue
        track = port_tracks.get(request.bus_id, {}).get(request.element_id)
        if request.element_id == "INVERTER":
            track = dc_span.first
        elif request.bus_id == "LOAD" or request.element_id in active_external_source_ids:
            track = elements[request.element_id].position.row_track
        requests.append(replace(request, track=track))
    for group, uids in building_groups.items():
        element_id = f"BUILDING_GROUP:{group.upper()}"
        member_ids = {f"BUILDING:{uid}" for uid in uids}
        carriers = dict.fromkeys(request.carrier for request in area_input.connections
                                 if request.element_id in member_ids and request.bus_id == "LOAD")
        for carrier in carriers:
            requests.append(ConnectionRequest(element_id, "LOAD", carrier, "input", elements[element_id].position.row_track))
    plan = TopologyLayoutPlan(
        elements=elements, areas=area_specs, attachments=building_layout.attachments,
        connections=tuple(requests), corridors=corridors, slots=slots, reserved_positions=reserved_positions,
        columns=columns, pill_spans=pill_spans, building_groups=building_groups,
        active_external_source_ids=tuple(active_external_source_ids), external_source_offset=external_source_offset,
        gas_port_track_by_code=tracks.gas_port_track_by_code,
        elyz_dc_lane_track_bounds=tracks.elyz_dc_lane_track_bounds, tracks=tracks,
    )
    return _complete_routes(plan, buildings)


def _building_carriers(row: Mapping[str, Any], cooling_active: bool) -> tuple[str, ...]:
    """Zentrale Gebäudeanschlüsse aus expliziter Auswahl oder bestehenden Versorgungsregeln lesen."""

    if "central_carriers" in row:
        chosen = set(row.get("central_carriers") or ())
        return tuple(carrier for key, carrier in (
            ("ac", "power"), ("heat", "heat"), ("dhw", "dhw"), ("cooling", "cool"),
        ) if key in chosen and (carrier != "cool" or cooling_active))
    return tuple(carrier for carrier, active in (
        ("power", central_connections(row)["ac"]),
        ("heat", _building_has_heat(dict(row))),
        ("dhw", _building_has_central_dhw(row)),
        ("cool", cooling_active and _building_has_central_cooling(dict(row))),
    ) if active)


def _complete_routes(plan: TopologyLayoutPlan, buildings: Sequence[Mapping[str, Any]]) -> TopologyLayoutPlan:
    """Verwendet geplante Anschlusszeilen für Korridorbelegung und Pfadtypen."""

    elements, columns = plan.elements, plan.columns
    requests = plan.connections

    groups: dict[str, PlannedLaneGroup] = {}
    corridors = dict(plan.corridors)
    low, high = plan.occupied_bounds.top, plan.occupied_bounds.bottom

    def group(name: str, axis: str, box: GridBox, keys: Iterable[str]) -> None:
        """Registriert eine nichtleere Spurgruppe und ihre Korridorfläche mit eindeutiger Reihenfolge."""

        ordered = tuple(dict.fromkeys(keys))
        if ordered:
            groups[name] = PlannedLaneGroup(axis, box, ordered)
            corridors[name] = box

    # Gemeinsame Spurkorridore erhalten eine stabile Reihenfolge ihrer Leitungen.
    has_power = "AC_BUS" in elements or "DC_BUS" in elements
    if has_power:
        x = columns["power_bus"]
        group("converter", "x", GridBox(x + .5, low, x + 1, high),
              [*(["FC:heat"] if "FC" in elements else []),
               *(["ELYZ:dc"] if "ELYZ" in elements else []),
               *(code for code in ("CC", "EB", "GROUNDHP", "HP") if code in elements),
               *(["AC:heat"] if "AC" in elements else [])])
    if has_power or "GAS_BUS" in elements:
        x = columns["power_bus"]
        group("left_bus", "x", GridBox(x - 1, low, x - .5, high),
              [*(["FC:dc"] if "FC" in elements else []),
               *(["SAB:gas"] if "SAB" in elements else [])])
    if not has_power and "AC" in elements:
        box = corridors["AC:heat"]
        group("converter", "x", box, ("AC:heat",))
    if plan.tracks.coupled_codes:
        visible_order = sorted(plan.tracks.coupled_codes,
                               key=lambda code: (elements[code].position.row_track, elements[code].position.column, code))
        target_order = sorted(visible_order, key=plan.tracks.coupled_track_by_code.__getitem__)
        x = columns["dc_source"]
        group("chp_left", "x", GridBox(x - 1, low, x - .5, high), target_order)
        x = columns["converter"]
        group("chp_local", "x", GridBox(x + 1, low, x + 1.5, high), visible_order)
        band = corridors["chp_ac"]
        group("chp_crossing", "y", band, reversed(visible_order))
    if "ELYZ" in elements:
        pos = elements["ELYZ"].position
        band = corridors.get("elyz_dc")
        bridge_top, bridge_bottom = (band.top, band.bottom) if band else (pos.row_track - 1, pos.row_track - 1)
        group("elyz_bridge", "y", GridBox(pos.column - .75, bridge_top, columns["power_bus"] + 1, bridge_bottom), ("ELYZ",))
        group("elyz_left", "x", GridBox(pos.column - .75, bridge_top, pos.column - .75, pos.row_track), ("ELYZ",))
    # Parallelports einmal je Gerät und Gebäude vorbereiten; die Routen lesen diese Zuordnung.
    routes: list[PlannedRoute] = []
    input_offsets, output_offsets = {}, {}
    for code in plan.tracks.selected:
        for key, result in (("inputs", input_offsets), ("outputs", output_offsets)):
            carriers = tuple(dict.fromkeys(CENTRAL_DEVICES[code].get(key, ())))
            result[code] = {carrier: index - (len(carriers) - 1) / 2 for index, carrier in enumerate(carriers)}
    rows = {f"BUILDING:{int(row.get('uid', index))}": (row, index) for index, row in enumerate(buildings)}
    building_names = {"power": "ac", "heat": "heat", "dhw": "dhw", "cool": "cooling"}
    load_carriers: dict[str, list[str]] = {}
    for request in requests:
        if request.bus_id == "LOAD":
            load_carriers.setdefault(request.element_id, []).append(request.carrier)

    def add(route_id, source, target, carrier, kind, source_track, target_track,
            source_offset=0.0, target_offset=0.0, lanes=()):
        """Fügt eine Route mit bereits geplanten Anschlüssen und Spurverweisen hinzu."""

        routes.append(PlannedRoute(route_id, source, target, carrier, kind,
                                   source_track, target_track, source_offset, target_offset, tuple(lanes)))

    # Externe Eintrittskanten, Lastanschlüsse und Gebäude benötigen keine Umlenkspuren.
    for source_id in plan.active_external_source_ids:
        track = elements[source_id].position.row_track
        add(f"external_to_{source_id.lower()}", source_id, source_id,
            elements[source_id].carrier, "external", track, track)
    for request in requests:
        code, bus, carrier = request.element_id, request.bus_id, request.carrier
        if code == "INVERTER":
            continue
        output = request.direction == "output"
        component_track = elements[code].position.row_track
        bus_track = request.track if request.track is not None else component_track
        if code == "LOAD":
            span = plan.pill_spans[{"AC_BUS": "ac", "HEAT_GRID": "heat", "COOL_GRID": "cool"}[bus]]
            bus_track = span.first if bus == "AC_BUS" else (span.first + span.last) / 2
            edge_id = {"power": "ac_to_load", "heat": "heat_to_load", "cool": "cooling_to_load"}[carrier]
            add(edge_id, bus, code, carrier, "straight", bus_track, bus_track)
            continue
        if bus == "LOAD":
            carriers = load_carriers[code]
            offset = carriers.index(carrier) - (len(carriers) - 1) / 2
            if code.startswith("BUILDING_GROUP:"):
                group_name = code.split(":")[-1].lower()
                edge_id = f"load_to_{group_name}_group_{building_names[carrier]}"
            else:
                row, index = rows[code]
                number = int(row.get("id") or index + 1)
                edge_id = f"load_to_building_{number}_{building_names[carrier]}"
            add(edge_id, bus, code, carrier, "straight", component_track, component_track, offset, offset)
            continue
        if code in plan.active_external_source_ids:
            edge_id = {"GRID": "grid_to_ac", "GAS_IMPORT": "gas_import_to_gas_bus", "H2_IMPORT": "h2_import_to_h2_bus"}[code]
            add(edge_id, code, bus, carrier, "straight", component_track, component_track)
            continue
        # Speicher zeichnen nur eine gemeinsame Kante für ihre beiden Flussrichtungen.
        slot = CENTRAL_DEVICES[code]["slot"]
        if (not output and slot in {"dc_storage", "heat_storage", "cool_storage"}) or (output and code in {"H2S", "GS"}):
            continue
        source, target = (code, bus) if output else (bus, code)
        source_track, target_track = (component_track, bus_track) if output else (bus_track, component_track)
        offset = (output_offsets if output else input_offsets).get(code, {}).get(carrier, 0.0)
        source_offset, target_offset = (offset, 0.0) if output else (0.0, offset)
        # Der Energieträger und die Anschlussrolle wählen den Pfadtyp aus den geplanten Spuren.
        kind, lanes = "straight", []
        if bus in {"BIOMASS_IMPORT", "WASTE_IMPORT", "OIL_IMPORT"}:
            edge_id = f"{bus.lower()}_to_{code.lower()}"
            source_track = elements[bus].position.row_track
            lane = (elements[bus].position.column + elements[code].position.column) / 2
            name = f"resource:{code}"
            group(name, "x", GridBox(lane, min(source_track, target_track), lane, max(source_track, target_track)), (code,))
            kind, lanes = "resource", [("lane_x", name, code)]
        elif bus == "AC_BUS":
            edge_id = f"{code.lower()}_to_ac"
            kind, lanes = "chp", [("left_lane_x", "chp_left", code), ("local_lane_x", "chp_local", code), ("horizontal_lane_y", "chp_crossing", code)]
        elif bus == "DC_BUS":
            edge_id = f"{code.lower()}_to_dc" if output else f"dc_to_{code.lower()}"
            if code == "ELYZ":
                kind = "elyz"
                lanes = [("right_lane_x", "converter", "ELYZ:dc"), ("left_lane_x", "elyz_left", "ELYZ"), ("bridge_y", "elyz_bridge", "ELYZ")]
            elif code == "FC":
                kind, lanes = "dc", [("lane_x", "left_bus", "FC:dc")]
            elif not output:
                kind, lanes = "dc", [("lane_x", "converter", code)]
        elif bus == "HEAT_GRID":
            edge_id = f"{code.lower()}_to_heat" if output else f"heat_to_{code.lower()}"
            if code == "AC":
                kind, lanes = "akm", [("lane_x", "converter", "AC:heat")]
            elif code == "FC":
                kind, lanes = "hvh", [("lane_x", "converter", "FC:heat")]
            elif code in COUPLED_SOURCE_CODES:
                target_offset = source_offset
        elif bus == "COOL_GRID":
            edge_id = f"{code.lower()}_to_cooling"
        elif bus == "H2_BUS":
            edge_id = "elyz_to_h2_bus" if output else f"h2_bus_to_{code.lower()}"
        elif bus == "GAS_BUS":
            edge_id = "sab_to_gas_bus" if output else f"gas_bus_to_{code.lower()}"
            if code == "SAB":
                kind, lanes = "hvh", [("lane_x", "left_bus", "SAB:gas")]
        else:
            raise ValueError(f"Unbekannter Topology-Anschluss {code}: {bus}")
        add(edge_id, source, target, carrier, kind, source_track, target_track,
            source_offset, target_offset, lanes)
    return replace(plan, routes=tuple(routes), lane_groups=groups, corridors=corridors)
