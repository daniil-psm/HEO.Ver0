"""Datenmodelle und Animationsskala der HEO-Powerflow Card."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class FlowSnapshot:
    """Leistungen und Speicherfüllstände für einen stündlichen PFC-Zustand."""

    hour: int

    grid_ac: float
    pv_dc: float

    ac_bus_to_converter: float
    converter_to_dc_bus: float

    dc_bus_to_converter: float
    converter_to_ac_bus: float
    ac_bus_to_grid: float

    dc_bus_to_bess: float
    bess_to_dc_bus: float
    bess_soc: float

    ac_load: float
    dc_load: float
    heat_load: float
    cooling_load: float

    dc_bus_to_heatpump: float
    heatpump_to_heat_load: float
    heatpump_to_cooling_load: float
    heatpump_to_thermal_storage: float

    thermal_storage_to_heat_load: float
    thermal_storage_soc: float

@dataclass(frozen=True)
class ClusterOption:
    """Kennung, Nummer und sichtbare Bezeichnung eines auswählbaren PFC-Clusters."""

    key: str
    number: int
    label: str

@dataclass(frozen=True)
class FlowAnimationScale:
    """Globale PFC-Geschwindigkeit über alle Zeitschritte und Cluster."""

    minimum_kw: float
    maximum_kw: float
    minimum_speed: float = 90.0
    maximum_speed: float = 260.0
    particle_gap: float = 74.0

    def normalized(self, value_kw: float) -> float:
        """Normiert den Leistungsbetrag auf 0 bis 1; Nullleistung ergibt 0."""

        magnitude = abs(float(value_kw))
        if magnitude <= 1e-9:
            return 0.0
        span = self.maximum_kw - self.minimum_kw
        if span <= 1e-9:
            return 1.0
        return clamp((magnitude - self.minimum_kw) / span, 0.0, 1.0)

    def speed(self, value_kw: float) -> float:
        """Liefert die Partikelgeschwindigkeit aus der global normierten Leistung."""

        share = self.normalized(value_kw)
        return self.minimum_speed + share * (self.maximum_speed - self.minimum_speed)

    def gap(self, value_kw: float) -> float:
        """Konstanter Abstand; die Leistung verändert ausschließlich das Tempo."""

        return self.particle_gap

@dataclass(frozen=True)
class PfcFrame:
    """Darstellungszustand eines PFC-Zeitschritts mit Cluster, Node-Werten und Animationsskala."""

    cluster_key: str | None
    cluster_number: int | None
    cluster_label: str
    step_index: int
    step_count: int
    step_hours: float
    title: str
    node_values: dict[str, str]
    animation_scale: FlowAnimationScale

def clamp(value: float, lower: float, upper: float) -> float:
    """Begrenzt einen Wert auf das durch lower und upper angegebene Intervall."""

    return max(lower, min(upper, value))

