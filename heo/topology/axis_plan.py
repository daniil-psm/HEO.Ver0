"""Auflösung relativer Rasteranker ohne Wissen über Geräte oder Energieträger."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Literal

Anchor = tuple[str, float]


@dataclass(frozen=True)
class ColumnPacking:
    """Zulässige Zellanker einer begrenzten, versetzten Spaltenanordnung."""

    max_columns: int = 2
    row_step: int = 2
    column_step: float = 1
    column_stagger: int = 1

    def __post_init__(self) -> None:
        """Validiert Abstände und Spaltenanzahl; ungültige Vorgaben lösen ValueError aus."""

        integer_values = (self.max_columns, self.row_step, self.column_stagger)
        if (not all(isinstance(value, int) for value in integer_values)
                or self.max_columns < 1 or self.row_step < 1 or self.column_stagger < 0
                or not isfinite(self.column_step) or self.column_step <= 0):
            raise ValueError("Ungültige Rasterabstände oder Spaltenanzahl")

    def slots(self, last_track: int, columns: int) -> tuple[tuple[float, int], ...]:
        """Liefert zulässige Zellanker bis last_track für die angegebene Spaltenanzahl."""

        if not 1 <= columns <= self.max_columns:
            raise ValueError("Spaltenanzahl außerhalb der Bereichsvorgabe")
        return tuple((column * self.column_step, track)
                     for column in range(columns)
                     for track in range(column * self.column_stagger, last_track + 1, self.row_step))

    def minimum_last_track(self, count: int) -> int:
        """Liefert den kleinsten letzten Track, der die benötigte Anzahl von Elementen aufnehmen kann."""

        # Eine Spalte genügt immer als obere Suchgrenze. Im Regelfall werden
        # hier nur die notwendigen Sammelgruppen und ein Control eingeplant.
        return next(track for track in range(max(1, count * self.row_step))
                    if len(self.slots(track, self.max_columns)) >= count)


@dataclass
class AxisPlan:
    """Ein Anker folgt dem äußersten seiner Bezüge samt jeweiligem Abstand.

    Minimum-Anker beschreiben gemeinsame Ober-/Linkskanten. Die Auflösung
    hängt nur vom Abhängigkeitsgraphen ab, nicht von der Definitionsreihenfolge.
    """

    axis: Literal["row", "column"]
    rules: dict[str, tuple[tuple[Anchor, ...], str]] = field(default_factory=dict)

    def add(self, name: str, *references: Anchor, reduce: str = "max") -> str:
        """Registriert einen eindeutigen Anker mit Min-/Max-Bezügen und liefert seinen Namen."""

        if name in self.rules:
            raise ValueError(f"Rasteranker mehrfach definiert: {name}")
        if reduce not in {"min", "max"}:
            raise ValueError(f"Unbekannte Ankerregel: {reduce}")
        self.rules[name] = (references, reduce)
        return name

    def stack(self, names: tuple[str, ...], start: Anchor, step: int = 1) -> str:
        """Registriert Stack-Anker und liefert den letzten Anker oder einen Endanker für den leeren Stack."""

        if step <= 0:
            raise ValueError("Ein Rasterstack benötigt einen positiven Abstand")
        for index, name in enumerate(names):
            self.add(name, (start[0], start[1] + index * step))
        if names:
            return names[-1]
        return self.add(f"{start[0]}:empty:{len(self.rules)}", (start[0], start[1] - 1))

    def resolve(self) -> dict[str, float]:
        """Liefert alle aufgelösten Anker; ungültige Werte, fehlende Bezüge und Zyklen lösen ValueError aus."""

        values: dict[str, float] = {}
        visiting: list[str] = []

        # Ein erneuter Besuch im aktiven Pfad zeigt einen Zyklus; fertige Werte werden wiederverwendet.
        def visit(name: str) -> float:
            """Löst einen Anker samt Abhängigkeiten auf und speichert seinen Wert zwischen."""

            if name in values:
                return values[name]
            if name in visiting:
                raise ValueError("Zyklische Rasterabhängigkeit: " + " -> ".join((*visiting, name)))
            if name not in self.rules:
                raise ValueError(f"Unbekannter Rasteranker: {name}")
            visiting.append(name)
            references, reduction = self.rules[name]
            candidates = [visit(key) + distance for key, distance in references]
            value = (min if reduction == "min" else max)(candidates, default=0)
            if not isfinite(value) or (self.axis == "row" and value != int(value)):
                raise ValueError(f"Ungültiger {self.axis}-Rasterwert für {name}: {value}")
            values[name] = int(value) if self.axis == "row" else value
            visiting.pop()
            return values[name]

        for name in self.rules:
            visit(name)
        return values
