"""HEO-Topologieknoten, Kanten, Komponenten und Rasterdaten."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from heo.display.device_labels import catalog_display_name
from heo.model.devices import HEO_DECENTRAL_DEVICE_CATALOG, TOPOLOGY_AUXILIARY_LABELS
from heo.topology.definitions import (
    CENTRAL_DEVICES,
    EdgeRouting,
    EnergyCarrier,
    NodeGroup,
    NodeRole,
    NodeShape,
    PortSide,
    energy_carrier_color,
)
from heo.topology.sizing import topology_node_content_ratio

@dataclass(frozen=True)
class TopologyNode:
    """Sichtbare Graph-Node mit normierter Position, Pixelgröße und Beschriftungsvarianten."""

    id: str
    title: str
    icon: str
    group: NodeGroup
    role: NodeRole
    color: str
    radius: int
    x: float
    y: float
    device_code: str | None = None
    shape: NodeShape = "circle"
    width: float | None = None
    height: float | None = None
    cell_id: str | None = None
    parent_id: str | None = None
    z_index: int = 0
    content_width: float = 58.0
    content_height: float = 44.0
    segments: tuple["TopologySegment", ...] = ()
    # Die drei Beschriftungsstufen bleiben Teil der zentralen Szene. Die
    # Renderer wählen abhängig vom *tatsächlich* verfügbaren Platz zwischen
    # ihnen, statt einen bei der Szenenerzeugung geschätzten Text zu übernehmen.
    label_full: str | None = None
    label_wrapped: str | None = None
    label_short: str | None = None
    # Aufgelöste Rasterzelle der Node. Sie erlaubt HTML-Renderern, die
    # physisch kleinere Zellachse erst nach responsiver Skalierung zu wählen.
    cell_width: float | None = None
    cell_height: float | None = None


@dataclass(frozen=True)
class TopologyEdge:
    """Gerichtete Energieträgerverbindung mit Wert, Ports und optional bereits aufgelöstem Pfad."""

    id: str
    source: str
    target: str
    carrier: EnergyCarrier
    value: float = 0.0
    curvature: float = 0.12
    source_port: "TopologyPort | None" = None
    target_port: "TopologyPort | None" = None
    routing: EdgeRouting = "bezier"
    # Zentrale Szenen können Sonderrouten bereits vollständig auflösen.
    # Datenansichten dürfen den Pfad verwenden, ohne ihn tab-spezifisch neu
    # zu berechnen.
    path: str | None = None
    dotted: bool = False


@dataclass(frozen=True)
class TopologyColumn:
    """Benannte Topologiespalte mit normierter horizontaler Position."""

    id: str
    label: str
    x: float


@dataclass(frozen=True)
class TopologyBounds:
    """Rechteckige Fläche in normierten Topologiekoordinaten."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TopologyCell:
    """Logische Gruppe von Nodes gleicher Rolle und Energieträger mit gemeinsamer Fläche."""

    id: str
    title: str
    carrier: EnergyCarrier
    role: NodeRole
    node_ids: tuple[str, ...]
    bounds: TopologyBounds


@dataclass(frozen=True)
class TopologyPort:
    """Benannter Anschluss einer Node mit Energieträger, Seite und normierter Position."""

    id: str
    carrier: EnergyCarrier
    side: PortSide
    x: float
    y: float


TopologyComponentRole = Literal["source", "generator", "converter", "storage"]
TopologyComponentColumn = Literal["ac", "dc", "heat", "dhw", "cooling", "gas_hydrogen"]
ThermalConverterGroup = Literal[
    "heat_generator", "heat_pump_system", "chp_system"
]


@dataclass(frozen=True)
class TopologyComponentFlow:
    """Beschrifteter Anschluss eines dokumentierten DG-Geräts."""

    label: str
    carrier: EnergyCarrier


@dataclass(frozen=True)
class TopologyComponentParameter:
    """Kompakter Fachparameter einer dokumentierten DG-Komponente."""

    name: str
    symbol: str

    @property
    def label(self) -> str:
        """Lesbare Parameterbezeichnung mit fachlichem Symbol."""

        return f"{self.name} ({self.symbol})"


@dataclass(frozen=True)
class TopologyComponentModel:
    """Darstellungsunabhängige DG-Komponente für die Topology-Dokumentation."""

    id: str
    title: str
    codes: tuple[str, ...]
    role: TopologyComponentRole
    column: TopologyComponentColumn
    main_output: EnergyCarrier
    inputs: tuple[TopologyComponentFlow, ...]
    outputs: tuple[TopologyComponentFlow, ...]
    parameters: tuple[TopologyComponentParameter, ...]
    thermal_group: ThermalConverterGroup | None = None
    backup_component_id: str | None = None
    bidirectional: bool = False

    @property
    def dg_code_label(self) -> str:
        """Gemeinsame Beschriftung der zugeordneten nativen DG-Gerätecodes."""

        return " / ".join(self.codes)

    @property
    def heo_code_label(self) -> str:
        """Liefert das sichtbare HEO-Kürzel statt des internen DG-Codes."""

        abbreviations: list[str] = []
        for code in self.codes:
            metadata = (
                CENTRAL_DEVICES.get(code)
                or CENTRAL_DEVICES.get(code.upper())
                or HEO_DECENTRAL_DEVICE_CATALOG.get(code)
                or TOPOLOGY_AUXILIARY_LABELS.get(code)
                or {}
            )
            abbreviation = str(
                metadata.get("abbreviation")
                or metadata.get("topology_labels", {}).get("short")
                or metadata.get("short")
                or code
            )
            if abbreviation not in abbreviations:
                abbreviations.append(abbreviation)
        return " / ".join(abbreviations)

    @property
    def display_label(self) -> str:
        """Verbindet den fachlichen Vollnamen mit dem sichtbaren HEO-Kürzel."""

        return f"{self.title} ({self.heo_code_label})"


TOPOLOGY_COMPONENT_ROWS: tuple[tuple[TopologyComponentRole, str], ...] = (
    ("source", "Quellen"),
    ("generator", "Erzeuger"),
    ("converter", "Wandler"),
    ("storage", "Speicher"),
)

TOPOLOGY_COMPONENT_COLUMNS: tuple[tuple[TopologyComponentColumn, str], ...] = (
    ("ac", "AC"),
    ("dc", "DC"),
    ("heat", "Raumwärme"),
    ("dhw", "Trinkwarmwasser"),
    ("cooling", "Raumkälte"),
    ("gas_hydrogen", "Energieträger"),
)

TOPOLOGY_LEGEND_CARRIERS: tuple[str, ...] = (
    "ac", "dc", "heat", "dhw", "cooling", "gas", "hydrogen",
    "biomass", "waste", "oil",
)


def _component_flow(label: str, carrier: EnergyCarrier) -> TopologyComponentFlow:
    """Erzeugt die Beschreibung eines fachlichen Geräteanschlusses."""

    return TopologyComponentFlow(label, carrier)


def _component_parameter(name: str, symbol: str) -> TopologyComponentParameter:
    """Erzeugt einen dokumentierten Geräteparameter aus Name und Symbol."""

    return TopologyComponentParameter(name, symbol)


def _storage_parameters() -> tuple[TopologyComponentParameter, ...]:
    """Liefert die gemeinsamen Speicherparameter für Ladewirkungsgrad und Speicherverlust."""

    return (
        _component_parameter("Ladewirkungsgrad", "η_ch"),
        _component_parameter("Speicherverlust", "η_standby"),
    )


def _space_heat_and_dhw_outputs() -> tuple[TopologyComponentFlow, ...]:
    """Thermische Outputs eines DG-Heizsystems ohne separaten TWW-Erzeuger."""

    return (
        _component_flow("Raumwärme", "heat"),
        _component_flow("Trinkwarmwasser", "dhw"),
    )


# Vollständiger, redundanzfreier Gerätekatalog der DG-Energy-Hub- und
# Gebäudemodelle. Identische Technologien erscheinen bewusst nur einmal. Die
# HEO-Hybrid-Aliase (zum Beispiel BHP und OHP) sind keine eigenständigen
# DG-Geräte und gehören daher nicht in diese Dokumentationsmatrix.
TOPOLOGY_COMPONENT_MODELS: tuple[TopologyComponentModel, ...] = (
    # Quellen
    TopologyComponentModel(
        "grid", catalog_display_name("GRID"), ("GRID",), "source", "ac", "ac",
        (_component_flow("Öffentliches Netz", "ac"),),
        (_component_flow("AC", "ac"),),
        (_component_parameter("Maximale Bezugsleistung", "P_grid,max"),),
    ),
    TopologyComponentModel(
        "district_heat", catalog_display_name("DH"), ("DH",), "source", "heat", "heat",
        (_component_flow("Wärmenetz", "heat"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Übertragungswirkungsgrad", "η_DH"),),
    ),
    TopologyComponentModel(
        "biomass_import", catalog_display_name("BIOMASS_IMPORT"), ("BIOMASS_IMPORT",), "source", "gas_hydrogen", "biomass",
        (_component_flow("Biomassemarkt", "biomass"),),
        (_component_flow("Biomasse", "biomass"),),
        (_component_parameter("Maximale Bezugsleistung", "B_bezug,max"),),
    ),
    TopologyComponentModel(
        "waste_import", catalog_display_name("WASTE_IMPORT"), ("WASTE_IMPORT",), "source", "gas_hydrogen", "waste",
        (_component_flow("Abfallaufkommen", "waste"),),
        (_component_flow("Abfall", "waste"),),
        (_component_parameter("Maximale Bezugsleistung", "W_bezug,max"),),
    ),
    TopologyComponentModel(
        "oil_import", catalog_display_name("OIL_IMPORT"), ("OIL_IMPORT",), "source", "gas_hydrogen", "oil",
        (_component_flow("Heizölmarkt", "oil"),),
        (_component_flow("Heizöl", "oil"),),
        (_component_parameter("Brennstoffpreis", "c_oil"),),
    ),
    TopologyComponentModel(
        "gas_import", catalog_display_name("GAS_IMPORT"), ("GAS_IMPORT",), "source", "gas_hydrogen", "gas",
        (_component_flow("Gasmarkt", "gas"),),
        (_component_flow("Erdgas", "gas"),),
        (_component_parameter("Maximale Bezugsleistung", "G_grid,max"),),
    ),
    TopologyComponentModel(
        "hydrogen_import", catalog_display_name("H2_IMPORT"), ("H2_IMPORT",), "source", "gas_hydrogen", "hydrogen",
        (_component_flow("H₂-Markt", "hydrogen"),),
        (_component_flow("Wasserstoff", "hydrogen"),),
        (_component_parameter("Maximale Bezugsleistung", "H_bezug,max"),),
    ),

    # Erzeuger
    TopologyComponentModel(
        "pv", catalog_display_name("PV"), ("PV",), "generator", "dc", "dc",
        (_component_flow("Solarstrahlung", "neutral"),),
        (_component_flow("DC", "dc"),),
        (_component_parameter("Modulwirkungsgrad", "η_PV"),
         _component_parameter("Modulfläche", "A_PV")),
    ),
    TopologyComponentModel(
        "wind", catalog_display_name("WT"), ("WT",), "generator", "dc", "dc",
        (_component_flow("Wind", "neutral"),),
        (_component_flow("DC", "dc"),),
        (_component_parameter("Nennleistung", "P_WT,n"),
         _component_parameter("Nabenhöhe", "h_hub")),
    ),
    TopologyComponentModel(
        "hydro", catalog_display_name("WAT"), ("WAT",), "generator", "dc", "dc",
        (_component_flow("Wasser", "neutral"),),
        (_component_flow("DC", "dc"),),
        (_component_parameter("Wirkungsgrad", "η_WAT"),
         _component_parameter("Leistungspotenzial", "P_WAT,pot")),
    ),
    TopologyComponentModel(
        "solar_thermal", catalog_display_name("STC"), ("STC",), "generator", "heat", "heat",
        (_component_flow("Solarstrahlung", "neutral"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Kollektorwirkungsgrad", "η_STC"),
         _component_parameter("Kollektorfläche", "A_STC")),
    ),

    # Elektrische Wandler
    TopologyComponentModel(
        "inverter", catalog_display_name("INVERTER"), ("INVERTER",), "converter", "ac", "neutral",
        (_component_flow("AC", "ac"), _component_flow("DC", "dc")),
        (_component_flow("DC", "dc"), _component_flow("AC", "ac")),
        (_component_parameter("Wechselrichterwirkungsgrad", "η_inv"),),
        bidirectional=True,
    ),

    # Wandler mit elektrischem Hauptoutput
    TopologyComponentModel(
        "chp", catalog_display_name("CHP"), ("CHP",), "converter", "heat", "heat",
        (_component_flow("Erdgas", "gas"),),
        (_component_flow("AC", "ac"), *_space_heat_and_dhw_outputs()),
        (_component_parameter("Elektrischer Wirkungsgrad", "η_el"),
         _component_parameter("Thermischer Wirkungsgrad", "η_th")),
        thermal_group="chp_system",
    ),
    TopologyComponentModel(
        "biomass_chp", catalog_display_name("BCHP"), ("BCHP",), "converter", "heat", "heat",
        (_component_flow("Biomasse", "biomass"),),
        (_component_flow("AC", "ac"), *_space_heat_and_dhw_outputs()),
        (_component_parameter("Elektrischer Wirkungsgrad", "η_el"),
         _component_parameter("Thermischer Wirkungsgrad", "η_th")),
        thermal_group="chp_system",
    ),
    TopologyComponentModel(
        "waste_chp", catalog_display_name("WCHP"), ("WCHP",), "converter", "heat", "heat",
        (_component_flow("Abfall", "waste"),),
        (_component_flow("AC", "ac"), *_space_heat_and_dhw_outputs()),
        (_component_parameter("Elektrischer Wirkungsgrad", "η_el"),
         _component_parameter("Thermischer Wirkungsgrad", "η_th")),
        thermal_group="chp_system",
    ),
    TopologyComponentModel(
        "fuel_cell", catalog_display_name("FC"), ("FC",), "converter", "heat", "heat",
        (_component_flow("Wasserstoff", "hydrogen"),),
        (_component_flow("AC", "ac"), *_space_heat_and_dhw_outputs()),
        (_component_parameter("Elektrischer Wirkungsgrad", "η_el"),
         _component_parameter("Thermischer Wirkungsgrad", "η_th")),
        thermal_group="chp_system",
    ),

    # Wärmewandler
    TopologyComponentModel(
        "heat_pump", catalog_display_name("HP"), ("HP",), "converter", "heat", "heat",
        (_component_flow("DC", "dc"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Leistungszahl", "COP"),),
        thermal_group="heat_pump_system",
        backup_component_id="electric_heater",
    ),
    TopologyComponentModel(
        "ground_heat_pump", catalog_display_name("GroundHP"), ("GroundHP",), "converter", "heat", "heat",
        (_component_flow("DC", "dc"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Leistungszahl", "COP_GEO"),),
        thermal_group="heat_pump_system",
        backup_component_id="electric_heater",
    ),
    TopologyComponentModel(
        "electric_heater", catalog_display_name("EB"), ("EB", "EH"), "converter", "heat", "heat",
        (_component_flow("Strom", "ac"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),
    TopologyComponentModel(
        "gas_heat_pump", catalog_display_name("GHP"), ("GHP",), "converter", "heat", "heat",
        (_component_flow("DC", "dc"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Leistungszahl", "COP"),),
        thermal_group="heat_pump_system",
        backup_component_id="gas_boiler",
    ),
    TopologyComponentModel(
        "biomass_boiler", catalog_display_name("BBOI"), ("BBOI",), "converter", "heat", "heat",
        (_component_flow("Biomasse", "biomass"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),
    TopologyComponentModel(
        "waste_boiler", catalog_display_name("WBOI"), ("WBOI",), "converter", "heat", "heat",
        (_component_flow("Abfall", "waste"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),
    TopologyComponentModel(
        "oil_boiler", catalog_display_name("OBOI"), ("OBOI",), "converter", "heat", "heat",
        (_component_flow("Heizöl", "oil"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),
    TopologyComponentModel(
        "gas_boiler", catalog_display_name("BOI"), ("BOI",), "converter", "heat", "heat",
        (_component_flow("Erdgas", "gas"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),
    TopologyComponentModel(
        "hydrogen_boiler", catalog_display_name("H2BOI"), ("H2BOI",), "converter", "heat", "heat",
        (_component_flow("Wasserstoff", "hydrogen"),),
        _space_heat_and_dhw_outputs(),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
        thermal_group="heat_generator",
    ),

    # Trinkwarmwasser, Kälte und stoffliche Wandler
    TopologyComponentModel(
        "dhw_heater", catalog_display_name("EH_DHW"), ("EH_DHW",), "converter", "dhw", "dhw",
        (_component_flow("AC", "ac"),),
        (_component_flow("Trinkwarmwasser", "dhw"),),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
    ),
    TopologyComponentModel(
        "compression_chiller", catalog_display_name("CC"), ("CC",), "converter", "cooling", "cooling",
        (_component_flow("DC", "dc"),),
        (_component_flow("Raumkälte", "cooling"),),
        (_component_parameter("Leistungszahl", "COP"),),
    ),
    TopologyComponentModel(
        "absorption_chiller", catalog_display_name("AC"), ("AC",), "converter", "cooling", "cooling",
        (_component_flow("Raumwärme", "heat"),),
        (_component_flow("Raumkälte", "cooling"),),
        (_component_parameter("Thermischer Wirkungsgrad", "η_th"),),
    ),
    TopologyComponentModel(
        "electrolyzer", catalog_display_name("ELYZ"), ("ELYZ",), "converter", "gas_hydrogen", "hydrogen",
        (_component_flow("DC", "dc"),),
        (_component_flow("Wasserstoff", "hydrogen"),),
        (_component_parameter("Elektrischer Wirkungsgrad", "η_el"),),
    ),
    TopologyComponentModel(
        "sabatier", catalog_display_name("SAB"), ("SAB",), "converter", "gas_hydrogen", "gas",
        (_component_flow("Wasserstoff", "hydrogen"),),
        (_component_flow("Erdgas", "gas"),),
        (_component_parameter("Methanisierungswirkungsgrad", "η_SAB"),),
    ),

    # Speicher
    TopologyComponentModel(
        "electric_vehicle", catalog_display_name("EV"), ("EV",), "storage", "dc", "dc",
        (_component_flow("DC", "dc"),),
        (_component_flow("DC / Fahrenergie", "dc"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "battery", catalog_display_name("BAT"), ("BAT",), "storage", "dc", "dc",
        (_component_flow("DC", "dc"),),
        (_component_flow("DC", "dc"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "heat_storage", catalog_display_name("TES"), ("TES",), "storage", "heat", "heat",
        (_component_flow("Raumwärme", "heat"),),
        (_component_flow("Raumwärme", "heat"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "dhw_storage", catalog_display_name("TES_DHW"), ("TES_DHW",), "storage", "dhw", "dhw",
        (_component_flow("Trinkwarmwasser", "dhw"),),
        (_component_flow("Trinkwarmwasser", "dhw"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "cold_storage", catalog_display_name("CTES"), ("CTES",), "storage", "cooling", "cooling",
        (_component_flow("Raumkälte", "cooling"),),
        (_component_flow("Raumkälte", "cooling"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "gas_storage", catalog_display_name("GS"), ("GS",), "storage", "gas_hydrogen", "gas",
        (_component_flow("Erdgas", "gas"),),
        (_component_flow("Erdgas", "gas"),),
        _storage_parameters(),
    ),
    TopologyComponentModel(
        "hydrogen_storage", catalog_display_name("H2S"), ("H2S",), "storage", "gas_hydrogen", "hydrogen",
        (_component_flow("Wasserstoff", "hydrogen"),),
        (_component_flow("Wasserstoff", "hydrogen"),),
        _storage_parameters(),
    ),
)


def topology_component_models(
    role: TopologyComponentRole | None = None,
    column: TopologyComponentColumn | None = None,
) -> tuple[TopologyComponentModel, ...]:
    """Filtert den zentralen DG-Komponentenkatalog für eine Tabellenzelle."""

    return tuple(
        component
        for component in TOPOLOGY_COMPONENT_MODELS
        if (role is None or component.role == role)
        and (column is None or component.column == column)
    )


def topology_component_node(component: TopologyComponentModel) -> TopologyNode:
    """Überführt einen Dokumentationseintrag in die kanonische Topology-Node."""

    group: NodeGroup = {
        "ac": "ac",
        "dc": "dc",
        "heat": "thermal",
        "dhw": "thermal",
        "cooling": "cooling",
        "gas_hydrogen": "load",
    }[component.column]
    node_role: NodeRole = {
        "source": "source",
        "generator": "source",
        "converter": "converter",
        "storage": "storage",
    }[component.role]
    return TopologyNode(
        id=f"DOC:{component.id}",
        title=component.title,
        icon=component.heo_code_label,
        group=group,
        role=node_role,
        color=energy_carrier_color(component.main_output),
        radius=0,
        x=0.5,
        y=0.5,
        device_code=component.dg_code_label,
        shape="pill",
        label_full=component.title,
        label_wrapped=component.title,
        label_short=component.heo_code_label,
    )


def topology_component_ports(
    component: TopologyComponentModel,
    side: Literal["input", "output"],
) -> tuple[TopologyPort, ...]:
    """Ordnet einen oder mehrere Anschlüsse symmetrisch um die Node-Mitte an."""

    flows = component.inputs if side == "input" else component.outputs
    count = len(flows)
    if count == 0:
        return ()
    spread = min(0.54, 0.24 * max(0, count - 1))
    start = 0.5 - spread / 2
    step = spread / (count - 1) if count > 1 else 0.0
    port_side: PortSide = "left" if side == "input" else "right"
    x = 0.0 if side == "input" else 1.0
    return tuple(
        TopologyPort(
            id=f"DOC:{component.id}:{side}:{index}",
            carrier=flow.carrier,
            side=port_side,
            x=x,
            y=start + index * step,
        )
        for index, flow in enumerate(flows)
    )


@dataclass(frozen=True)
class TopologySegment:
    """Beschrifteter Energieträgerabschnitt innerhalb einer Lastpille."""

    id: str
    label: str
    carrier: EnergyCarrier
    y: float


@dataclass(frozen=True)
class GridPosition:
    """Semantische Position in einem überlappenden Topologieraster.

    Ganze Spalten bezeichnen die neun Hauptbereiche. Halbe Spalten bilden
    versetzte Unterspalten. ``row_track`` zählt halbe Zeilenhöhen: gerade
    Werte sind Hauptzeilen, ungerade Werte die dazwischenliegenden Zeilen für
    Inverter, Speicher, Stack-Versätze und Edge-Lanes.
    """

    column: float
    row_track: int


@dataclass(frozen=True)
class ResolvedGrid:
    """In Pixel aufgelöstes, vollständig in den Viewport passendes Raster."""

    canvas_width: float
    canvas_height: float
    column_count: float
    max_row_track: int
    padding: float
    cell_width: float
    cell_height: float
    node_diameter: float

    def center(self, position: GridPosition) -> tuple[float, float]:
        """Liefert den Pixelmittelpunkt einer logischen Rasterposition."""

        return (
            self.padding
            + (position.column + 0.5) * self.cell_width,
            self.padding
            + self.cell_height / 2
            + position.row_track * self.cell_height / 2,
        )

    def row_bounds(self, first_track: int, last_track: int) -> tuple[float, float]:
        """Grenzen einer Pille anhand belegter Rasterzeilen statt Node-Bounds."""

        first_y = self.center(GridPosition(0, first_track))[1]
        last_y = self.center(GridPosition(0, last_track))[1]
        half = self.cell_height / 2
        return first_y - half, last_y + half

    def column_bounds(self, first_column: float, last_column: float) -> tuple[float, float]:
        """Liefert die äußeren Pixelgrenzen der angegebenen ersten und letzten Spalte."""

        first_x = self.center(GridPosition(first_column, 0))[0]
        last_x = self.center(GridPosition(last_column, 0))[0]
        half = self.cell_width / 2
        return first_x - half, last_x + half


def resolve_overlapping_grid(
    *,
    canvas_width: float,
    canvas_height: float,
    column_count: float,
    max_row_track: int,
    field_padding_ratio: float = 0.02,
    content_ratio: float | None = None,
    minimum_node_diameter: float = 42.0,
) -> ResolvedGrid:
    """Löst Haupt- und Zwischenzeilen ohne nachträgliche Skalierung auf.

    Ein Trackschritt entspricht einer halben Zellenhöhe. Dadurch entstehen
    die gewünschten Stack-Überlappungen konstruktiv. Das Raster bleibt immer
    innerhalb der sichtbaren Canvas. ``minimum_node_diameter`` ist eine
    Zielgröße; reicht der Viewport nicht, muss der Aufrufer Gebäude gruppieren
    oder zusätzliche Gebäudespalten anlegen, statt Scrollhöhe zu erzeugen.
    """

    if column_count < 1:
        raise ValueError("column_count muss positiv sein")
    if max_row_track < 0:
        raise ValueError("max_row_track darf nicht negativ sein")
    if not 0 <= field_padding_ratio < 0.25:
        raise ValueError("field_padding_ratio muss zwischen 0 und 0.25 liegen")

    if content_ratio is None:
        content_ratio = topology_node_content_ratio()
    padding = min(canvas_width, canvas_height) * field_padding_ratio / 2
    available_width = max(1.0, canvas_width - 2 * padding)
    available_height = max(1.0, canvas_height - 2 * padding)
    cell_width = available_width / column_count
    occupied_row_units = 1.0 + max_row_track / 2
    cell_height = available_height / occupied_row_units
    node_diameter = content_ratio * min(cell_width, cell_height)
    # Die Mindestgröße ist bewusst nicht durch ein blindes Hochskalieren
    # erzwungen: Das würde den Viewport wieder sprengen. Sie steht den
    # Belegungsoptimierern als Qualitätsgrenze zur Verfügung.
    node_diameter = max(1.0, node_diameter)
    _ = minimum_node_diameter
    return ResolvedGrid(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        column_count=column_count,
        max_row_track=max_row_track,
        padding=padding,
        cell_width=cell_width,
        cell_height=cell_height,
        node_diameter=node_diameter,
    )

@dataclass(frozen=True)
class Topology:
    """Graph der Energiesystemszene mit Nodes, Kanten, Spalten, Zellen und Auswahlzustand."""

    nodes: dict[str, TopologyNode]
    edges: list[TopologyEdge]
    columns: tuple[TopologyColumn, ...] = ()
    selected_devices: frozenset[str] = frozenset()
    cells: tuple[TopologyCell, ...] = ()
    mode: str = "legacy"
    message: str | None = None


