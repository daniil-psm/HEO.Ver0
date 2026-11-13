"""Zentrale HEO-Bezeichnungen, Hilfetexte und Abschnittsdefinitionen."""

from __future__ import annotations

from typing import Any

# Einheitliche HEO-Abschnittstitel für Eingabeformulare und Projektinformationen.
ECO_SECTION_TITLE = "Energiepreise und Emissionsfaktoren"
SECTION_TITLES = {
    "location": "Allgemeine Projektdaten",
    "calendar": "Heiz- und Kühlperioden",
    "design_building": "Gebäudeauslegung",
    "decentral": "Dezentrale Anlagen",
    "heatgrid": "Wärmenetz",
    "central": "Zentrale Anlagen",
    "eco": ECO_SECTION_TITLE,
    "time": "Zeit und Cluster",
    "ehdo": "Zentrale Versorgung",
    "pyomo": "Optimierung",
    "physics": "Physikalische Kennwerte",
    "report": "Ausgabe und Berichte",
    "building_connection": "Gebäudeanschluss",
    "microgrid_economics": ECO_SECTION_TITLE,
    "microgrid_frame": "Microgrid-Rahmen",
}


PROJECT_SECTION_PRESENTATION = {
    "location": {
        "title": SECTION_TITLES["location"],
        "description": "Standort-, Klima- und wirtschaftliche Projektrahmendaten.",
    },
}
BUILDING_SECTION_PRESENTATION = {
    "calendar": {
        "title": SECTION_TITLES["calendar"],
        "description": "Heiz- und Kühlperioden für Simulation und Clustering.",
    },
    "design_building": {
        "title": SECTION_TITLES["design_building"],
        "description": "Solltemperaturen und allgemeine Parameter der Gebäudeauslegung.",
    },
    "decentral": {
        "title": SECTION_TITLES["decentral"],
        "description": "Technische und wirtschaftliche Daten dezentraler Anlagen.",
    },
}
MICROGRID_SECTION_PRESENTATION = {
    "heatgrid": {
        "title": SECTION_TITLES["heatgrid"],
        "description": "Technische und wirtschaftliche Parameter des Wärmenetzes.",
    },
    "central": {
        "title": SECTION_TITLES["central"],
        "description": "Technische und wirtschaftliche Daten zentraler Anlagen.",
    },
    "eco": {
        "title": SECTION_TITLES["eco"],
        "description": "Bezugs- und Einspeisepreise sowie ökologische Kennwerte des Microgrids.",
    },
}
SIMULATION_SECTION_PRESENTATION = {
    "time": {"title": SECTION_TITLES["time"], "description": "Zeitauflösung, Clusterlänge und Länge der Eingangsdaten."},
    "ehdo": {"title": SECTION_TITLES["ehdo"], "description": "Freigaben und Grenzen des zentralen Energiesystemmodells."},
    "pyomo": {"title": SECTION_TITLES["pyomo"], "description": "Solver und Abbruchkriterien der Optimierung."},
    "physics": {"title": SECTION_TITLES["physics"], "description": "Physikalische Stoffwerte für Luft und Wasser."},
    "report": {"title": SECTION_TITLES["report"], "description": "Ausgabeformat und Darstellung des DG-Berichts."},
}

MICROGRID_CONFIG_SECTION_KEYS = ("heatgrid", "central")
SIMULATION_CONFIG_SECTION_KEYS = ("time", "ehdo", "pyomo")
ADVANCED_CONFIG_SECTION_KEYS = ("physics", "report")
ECO_SIMULATION_FIELD_KEYS = (
    "OPTIMIZATION_FOCUS", "NUM_INTERPOLATION_POINTS", "INTERPOLATION_POINTS",
)
ECO_MICROGRID_FIELD_KEYS = (
    "PRICE_SUPPLY_EL", "PRICE_SUPPLY_EL_EH", "PRICE_SUPPLY_GAS",
    "PRICE_SUPPLY_GAS_EH", "PRICE_GASOLINE_LITER", "PRICE_HYDROGEN",
    "PRICE_WASTE", "PRICE_BIOMASS", "PRICE_OIL", "PRICE_DISTRICT_HEAT",
    "REVENUE_FEED_IN_EL", "REVENUE_FEED_IN_EL_EH", "REVENUE_FEED_IN_GAS",
    "CO2_EL_GRID", "CO2_GAS", "CO2_BIOM", "CO2_WASTE", "CO2_HYDROGEN",
    "CO2_OIL", "CO2_DISTRICT_HEAT", "CO2_TAX",
)


BUILDING_CONFIG_SECTION_KEYS = ("calendar", "design_building", "decentral")
ECO_PROJECT_FIELD_KEYS = ("INTEREST_RATE", "OBSERVATION_TIME")
BUILDING_CSV_SECTION = "buildings"
PROJECT_LOAD_SECTION = "project_load"
SIMULATION_CONFIG_SECTION = "simulation"
BUILDING_GROUP_SECTION = "building_configuration"
MICROGRID_GROUP_SECTION = "microgrid_configuration"
ADVANCED_CONFIG_SECTION = "advanced_configuration"

GROUP_LABELS = {
    "GENERAL": "Allgemein",
    "SCENARIO": "Szenario",
    "SOLVER_OPTIONS": "Solver-Optionen",
    "COLORS": "Farben",
    "SIZES": "Größen",
    "LAYOUT_OPTIONS": "Layout-Optionen",
    "FONTS": "Schriften",
    "T_HOT_HEATING_NETWORK": "Vorlauftemperaturen Heizen",
    "T_COLD_HEATING_NETWORK": "Rücklauftemperaturen Heizen",
    "FLUID": "Fluid",
    "PUMP": "Pumpe",
    "PIPE": "Rohrnetz",
}


# Zentrale Präsentationsmetadaten für die deutschsprachige Oberfläche
# technische DG-Schlüssel bleiben unverändert und werden ausschließlich beim Speichern/Exportieren verwendet
PARAMETER_PRESENTATION: dict[str, dict[str, Any]] = {
    "TIMERESOLUTION": {
        "label": "Zeitauflösung", "unit": "h",
        "display_divisor": 3600, "display_number_kind": "decimal",
    },
    "SOLVER_OPTIONS__TIME_LIMIT": {
        "label": "Zeitlimit je Solver-Aufruf", "unit": "min",
        "display_divisor": 60, "display_number_kind": "decimal",
    },
    "SOLVER_OPTIONS__MIP_GAP": {"label": "Relative Optimalitätslücke (MIP)"},
    "CLUSTERNUMBER": {"label": "Anzahl Cluster"},
    "CLUSTERLENGTH": {"label": "Clusterlänge"},
    "SOLVER_NAME": {"label": "Solver"},
    "SCENARIO_NAME": {
        "label": "Szenarioname",
        "help_text_de": "Name des Microgrids und des zugehörigen Szenarios.",
    },
    "ALBEDO": {
        "label": "Albedo",
        "help_text_de": "Mittlerer Reflexionsgrad der Geländeoberfläche.",
    },
    "DISTRICT_AREA": {
        "label": "Quartiersfläche",
        "help_text_de": "Gesamtfläche des betrachteten Quartiers.",
    },
    "INTEREST_RATE": {
        "label": "Kalkulationszinssatz",
        "help_text_de": "Zinssatz für die wirtschaftliche Bewertung des Projekts.",
    },
    "OBSERVATION_TIME": {
        "label": "Projektlaufzeit",
        "help_text_de": "Zeitraum der wirtschaftlichen Projektbetrachtung.",
    },
    "NUM_INTERPOLATION_POINTS": {
        "label": "Anzahl Stützjahre",
        "unit": "Jahre",
    },
    "INTERPOLATION_POINTS": {
        "label": "Stützjahre",
        "unit": "",
    },
    "OPTIMIZATION_FOCUS": {
        "label": "Optimierungsziel",
        "help_text_de": "Legt fest, ob wirtschaftliche oder ökologische Ziele priorisiert werden.",
        "option_labels": {
            "economic": "Ökonomisch",
            "ecological": "Ökologisch",
            0: "Ökonomisch",
            1: "Ökologisch",
        },
    },
    "TRYYEAR": {
        "label": "Klimadatensatz",
        "help_text_de": "Verwendeter Zeitraum für die Klimadaten.",
        "option_labels": {
            "measured_1995_2012": "Gemessenes Klima (1995–2012)",
            "forecast_2031_2060": "Klimaprognose (2031–2060)",
            "TRY2015": "Gemessenes Klima (1995–2012)",
            "TRY2045": "Klimaprognose (2031–2060)",
        },
    },
    "ENABLE_TRAFOMAX_W": {
        "label": "Transformatorgrenze berücksichtigen",
        "help_text_de": "Begrenzt die elektrische Leistung des Quartiertransformators für Bezug und Einspeisung.",
    },
    "TRAFOMAX_W": {
        "label": "Transformatorleistung",
        "help_text_de": "Maximale Wirkleistung des Quartiertransformators für Bezug und Einspeisung.",
    },
    "PRICE_SUPPLY_EL_EH": {
        "label": "Strombezugspreis",
        "help_text_de": "Preis für den Bezug von Strom aus dem Stromnetz in das Quartier.",
    },
    "REVENUE_FEED_IN_EL_EH": {
        "label": "Einspeisevergütung",
        "help_text_de": "Erlös für die Einspeisung von Strom aus dem Quartier ins Stromnetz.",
    },
    "CO2_EL_GRID": {
        "label": "CO₂-Emissionen des Strombezugs",
        "help_text_de": "Spezifische CO₂-Emissionen des aus dem Stromnetz bezogenen Stroms.",
    },
    "ENABLE_SUPPLY_EL": {
        "label": "Strombezug zulassen",
        "help_text_de": "Legt fest, ob das Quartier Strom aus dem Stromnetz beziehen darf.",
    },
    "ENABLE_FEED_IN_EL": {
        "label": "Stromeinspeisung zulassen",
        "help_text_de": "Legt fest, ob das Quartier Strom in das Stromnetz einspeisen darf.",
    },
    "ENABLE_PRICE_CAP_EL": {
        "label": "Leistungspreis berücksichtigen",
        "help_text_de": "Berücksichtigt einen zusätzlichen Preis für die beanspruchte elektrische Leistung.",
    },
    "PRICE_CAP_EL": {
        "label": "Leistungspreis",
        "help_text_de": "Preis für die beanspruchte elektrische Anschlussleistung.",
    },
    "ENABLE_CAP_LIMIT_EL": {
        "label": "Netzanschlussleistung begrenzen",
        "help_text_de": "Aktiviert eine obere Grenze für die elektrische Netzanschlussleistung.",
    },
    "CAP_LIMIT_EL": {
        "label": "Netzanschlussleistung",
        "help_text_de": "Maximal zulässige elektrische Leistung am Netzanschlusspunkt.",
    },
    "ENABLE_SUPPLY_LIMIT_EL": {
        "label": "Strombezug begrenzen",
        "help_text_de": "Aktiviert eine jährliche Obergrenze für den Strombezug aus dem Netz.",
    },
    "SUPPLY_LIMIT_EL": {
        "label": "Jährlicher Strombezug",
        "help_text_de": "Maximal zulässiger jährlicher Strombezug des Quartiers.",
    },
    "ENABLE_BUILDINGMAX_W": {
        "label": "Gebäudeanschluss begrenzen",
        "help_text_de": "Aktiviert eine Leistungsgrenze für den elektrischen Anschluss des Gebäudes.",
    },
    "BUILDINGMAX_W": {
        "label": "Gebäudeanschlussleistung",
        "help_text_de": "Maximal zulässige elektrische Anschlussleistung des Gebäudes.",
    },
    "PRICE_SUPPLY_EL": {
        "label": "Strombezugspreis des Gebäudes",
        "help_text_de": "Preis für den Strombezug des einzelnen Gebäudes.",
    },
    "REVENUE_FEED_IN_EL": {
        "label": "Einspeisevergütung des Gebäudes",
        "help_text_de": "Erlös für die Einspeisung von Strom aus dem Gebäude ins Stromnetz.",
    },
    "PRICE_SUPPLY_GAS": {
        "label": "Gasbezugspreis", 
        "help_text_de": "Preis für den Gasbezug der Komponente.", 
        },
    "PRICE_SUPPLY_GAS_EH": {
        "label": "Gasbezugspreis des Quartiers", 
        "help_text_de": "Preis für den Gasbezug des Quartiers.", 
        },
    "PRICE_BIOMASS": {
        "label": "Biomassepreis", 
        "help_text_de": "Preis für den Bezug von Biomasse.", 
        },
    "PRICE_WASTE": {
        "label": "Abfallbezugspreis", 
        "help_text_de": "Preis für den Bezug des energetisch genutzten Abfalls.", 
        },
    "PRICE_OIL": {
        "label": "Heizölpreis", 
        "help_text_de": "Preis für den Bezug von Heizöl.", 
        },
    "PRICE_DISTRICT_HEAT": {
        "label": "Fernwärmepreis", 
        "help_text_de": "Preis für den Bezug von Fernwärme.", 
        },
    "PRICE_GASOLINE_LITER": {
        "label": "Kraftstoffpreis", 
        "help_text_de": "Preis je Liter Kraftstoff.", 
        },
    "CO2_GAS": {
        "label": "CO₂-Emissionen von Gas", 
        "help_text_de": "Spezifische CO₂-Emissionen des Gasbezugs.", 
        },
    "CO2_BIOM": {
        "label": "CO₂-Emissionen von Biomasse", 
        "help_text_de": "Spezifische CO₂-Emissionen des Biomassebezugs.", 
        },
    "CO2_WASTE": {
        "label": "CO₂-Emissionen von Abfall", 
        "help_text_de": "Spezifische CO₂-Emissionen der energetischen Abfallnutzung.", 
        },
    "CO2_OIL": {
        "label": "CO₂-Emissionen von Heizöl", 
        "help_text_de": "Spezifische CO₂-Emissionen des Heizölbezugs.", 
        },
    "CO2_DISTRICT_HEAT": {
        "label": "CO₂-Emissionen von Fernwärme", 
        "help_text_de": "Spezifische CO₂-Emissionen des Fernwärmebezugs."},
    "CO2_TAX": {
        "label": "CO₂-Preis", 
        "help_text_de": "Preis je ausgestoßener Tonne CO₂.", 
        },
    "CONSIDER_HEATING_PERIOD": {
        "label": "Heizperiode berücksichtigen", 
        "help_text_de": "Begrenzt den Heizbetrieb auf die festgelegte Heizperiode.", 
        },
    "HEATING_PERIOD_START": {
        "label": "Beginn der Heizperiode", 
        "help_text_de": "Erster Tag der jährlichen Heizperiode.", 
        },
    "HEATING_PERIOD_END": {
        "label": "Ende der Heizperiode", "help_text_de": "Letzter Tag der jährlichen Heizperiode."},
    "CONSIDER_COOLING_PERIOD": {
        "label": "Kühlperiode berücksichtigen", "help_text_de": "Begrenzt den Kühlbetrieb auf die festgelegte Kühlperiode."},
    "COOLING_PERIOD_START": {
        "label": "Beginn der Kühlperiode", "help_text_de": "Erster Tag der jährlichen Kühlperiode."},
    "COOLING_PERIOD_END": {
        "label": "Ende der Kühlperiode", "help_text_de": "Letzter Tag der jährlichen Kühlperiode."},
    "GENERATION": {
        "label": "Netzgeneration", "help_text_de": "Ausbaustufe des verwendeten Wärmenetzmodells.", "option_labels": {"3rd": "3. Generation", "4th": "4. Generation", "5th": "5. Generation"}},
    "TOPOLOGY_OPTION": {
        "label": "Netztopologie", "help_text_de": "Methode zur Bildung der Wärmenetztopologie.", "option_labels": {"node": "Nach Gebäudeknoten", "road": "Entlang des Straßennetzes"}},
    "TEMPERATURE_MODE": {
        "label": "Temperaturführung", "help_text_de": "Regelung der Netztemperatur während des Betriebs.", "option_labels": {"constant": "Konstant", "heating_curve": "Nach Heizkurve"}},
    "HEURISTIC": {
        "label": "Heuristik verwenden", "help_text_de": "Verwendet eine vereinfachte Methode zur Auslegung des Netzes."},
    "D_HEATING_NETWORK": {
        "label": "Leitungsabstand des Wärmenetzes", "help_text_de": "Abstand zwischen Vor- und Rücklaufleitung des Wärmenetzes."},
    "D_COOLING_NETWORK": {
        "label": "Leitungsabstand des Kältenetzes", "help_text_de": "Abstand zwischen Vor- und Rücklaufleitung des Kältenetzes."},
    "T_HOT_COOLING_NETWORK": {
        "label": "Vorlauftemperatur des Kältenetzes", "help_text_de": "Temperatur des wärmeren Leitungsstrangs im Kältenetz."},
    "T_COLD_COOLING_NETWORK": {
        "label": "Rücklauftemperatur des Kältenetzes", "help_text_de": "Temperatur des kälteren Leitungsstrangs im Kältenetz."},
    "DELTA_T_HEATTRANSFER": {
        "label": "Temperaturdifferenz am Wärmeübertrager", "help_text_de": "Auslegungs-Temperaturdifferenz am Wärmeübertrager."},
    "C_TES__DELTA_T": {
        "unit": "°C",
    },
    "D_PV__GAMMA": {
        "label": "Temperaturkoeffizient der PV-Leistung",
        "help_text_de": "Relative Abnahme des PV-Wirkungsgrads je Kelvin über der Referenz-Zelltemperatur. Ein Wert von 0,003 entspricht 0,3 % je Kelvin.",
    },
    "C_ELYZ__ETA_EL": {
        "help_text_de": "Verhältnis der erzeugten Wasserstoffenergie zur aufgenommenen elektrischen Energie. Ein höherer Wirkungsgrad senkt den Strombedarf je erzeugter Wasserstoffmenge.",
    },
    "ASPHALTLAYER": {
        "label": "Asphaltdeckschicht berücksichtigen", "help_text_de": "Legt fest, ob über dem Leitungsnetz eine Asphaltdeckschicht berücksichtigt wird."},
    "D_ASPH": {
        "label": "Dicke der Asphaltdeckschicht", "help_text_de": "Dicke der Asphaltdeckschicht über dem Leitungsnetz."},
    "GRID_DEPTH": {
        "label": "Verlegetiefe des Netzes", "help_text_de": "Tiefe des Leitungsnetzes unter der Geländeoberkante."},
    "K_SOIL": {
        "label": "Wärmeleitfähigkeit des Bodens", "help_text_de": "Wärmeleitfähigkeit des umgebenden Bodens."},
    "K_PUF": {
        "label": "Wärmeleitfähigkeit der PU-Dämmung", "help_text_de": "Wärmeleitfähigkeit der Polyurethan-Dämmung der Rohrleitung."},
    "K_PE": {
        "label": "Wärmeleitfähigkeit des PE-Mantels", "help_text_de": "Wärmeleitfähigkeit des Polyethylen-Außenmantels der Rohrleitung."},
    "H_LOSS_SUBST": {
        "label": "Wärmeverlust der Übergabestation", "help_text_de": "Prozentualer Wärmeverlust an der Übergabestation."},
    "DP_SUBSTATION": {
        "label": "Druckverlust der Übergabestation", "help_text_de": "Druckverlust an der Übergabestation."},
    "DP_ENERGY_HUB": {
        "label": "Druckverlust der Energiezentrale", "help_text_de": "Druckverlust in der Energiezentrale."},
    "C_SUBST": {
        "label": "Investitionskosten der Übergabestation", "help_text_de": "Spezifische Investitionskosten der Übergabestation."},
    "COST_OM_SUBST": {
        "label": "Betriebs- und Wartungskosten der Übergabestation", "help_text_de": "Betriebs- und Wartungskosten der Übergabestation."},
    "LIFETIME_SUBST": {
        "label": "Lebensdauer der Übergabestation", "help_text_de": "Technische Lebensdauer der Übergabestation."},
    "C_OM": {
        "label": "Jährliche Betriebs- und Wartungskosten", "help_text_de": "Jährliche Betriebs- und Wartungskosten in Prozent der Investitionskosten."},
    "T_SET_MIN": {
        "label": "Minimale Raumtemperatur", "help_text_de": "Unterer Sollwert der Raumtemperatur während der Nutzung."},
    "T_SET_MIN_NIGHT": {
        "label": "Minimale Raumtemperatur nachts", "help_text_de": "Unterer Sollwert der Raumtemperatur während der Nachtabsenkung."},
    "T_SET_MIN_FREE_DAY": {
        "label": "Minimale Raumtemperatur an freien Tagen", "help_text_de": "Unterer Sollwert der Raumtemperatur an nutzungsfreien Tagen."},
    "T_SET_MAX": {
        "label": "Maximale Raumtemperatur", "help_text_de": "Oberer Sollwert der Raumtemperatur während der Nutzung."},
    "T_SET_MAX_NIGHT": {
        "label": "Maximale Raumtemperatur nachts", "help_text_de": "Oberer Sollwert der Raumtemperatur während der Nacht."},
    "T_BIVALENT": {
        "label": "Bivalenztemperatur", "help_text_de": "Außentemperatur für den Wechsel zwischen den Wärmeerzeugern."},
    "T_HEATLIMIT": {
        "label": "Heizgrenztemperatur", "help_text_de": "Außentemperatur, oberhalb der kein Heizbetrieb erforderlich ist."},
    "VENTILATION_RATE": {
        "label": "Luftwechselrate", "help_text_de": "Stündlicher Luftwechsel des Gebäudes."},
    "THERMAL_MODEL_TYPE": {
        "label": "Thermisches Gebäudemodell", "help_text_de": "Detaillierungsgrad des thermischen Gebäudemodells.", "option_labels": {"5R1C": "5R1C-Modell", "7R2C": "7R2C-Modell"}},
}

PARAMETER_SUFFIX_PRESENTATION: dict[str, tuple[str, str]] = {
    "ETA": ("Wirkungsgrad", "Elektrischer oder thermischer Wirkungsgrad der Komponente."),
    "COP": ("Leistungszahl", "Verhältnis von abgegebener Wärme- oder Kälteleistung zur eingesetzten Energie."),
    "GRADE": ("Carnot-Gütegrad", "Anteil der real erreichten Leistungszahl an der idealen Carnot-Leistungszahl."),
    "BETA": ("Neigungswinkel", "Neigungswinkel der Kollektor- oder Modulfläche."),
    "GAMMA": ("Ausrichtung", "Azimut der Fläche; 0° entspricht Süden, negative Werte Osten und positive Werte Westen."),
    "LIFE_TIME": ("Lebensdauer", "Technische Lebensdauer der Komponente."),
    "INV_BASE": ("Investitionskosten", "Spezifische Investitionskosten ohne Förderung."),
    "COST_OM": ("Betriebskosten", "Jährliche Betriebs- und Wartungskosten als Anteil der Investitionskosten."),
    "INV_SUBSIDY_RATE": ("Förderanteil", "Anteil der Investitionskosten, der durch eine Förderung gedeckt wird."),
    "MIN_AREA": ("PV-Fläche", "Kleinste zulässige Installationsfläche."),
    "MAX_AREA": ("PV-Fläche", "Größte zulässige Installationsfläche."),
    "MIN_CAP": ("Kapazität", "Kleinste zulässige Kapazität der Komponente."),
    "MAX_CAP": ("Kapazität", "Größte zulässige Kapazität der Komponente."),
    "MIN_VOL": ("Speichervolumen", "Kleinstes zulässiges Speichervolumen."),
    "MAX_VOL": ("Speichervolumen", "Größtes zulässiges Speichervolumen."),
    "FEASIBLE": ("Komponente berücksichtigen", "Legt fest, ob die Komponente bei der Optimierung berücksichtigt wird."),
    "ASCC_MODEL_FEASIBLE": ("Konstantes Kältemodell", "Berücksichtigt das Modell mit konstanter Leistungszahl für die Kälteerzeugung."),
    "ASHP_CARNOT_EFF": ("Carnot-Gütegrad", "Gütegrad der Wärmepumpe gegenüber dem idealen Carnot-Prozess."),
    "ASHP_CARNOT_FEASIBLE": ("Carnot-Modell", "Berücksichtigt das temperaturabhängige Carnot-Modell der Wärmepumpe."),
    "ASHP_MODEL_FEASIBLE": ("Wärmepumpenmodell", "Berücksichtigt das detaillierte Modell der Luftwärmepumpe."),
    "ASHP_SUPPLY_TEMP": ("Vorlauftemperatur", "Vorlauftemperatur der Luftwärmepumpe."),
    "CCOP_FEASIBLE": ("Konstante Leistungszahl", "Berücksichtigt eine konstante Leistungszahl im Modell."),
    "COP_CONST": ("Konstante Leistungszahl", "Fest vorgegebene Leistungszahl der Komponente."),
    "CSV_FEASIBLE": ("Kennfeld aus Datei", "Berücksichtigt das hinterlegte Komponentenkennfeld aus der CSV-Datei."),
    "DELTA_T": ("Temperaturdifferenz", "Temperaturdifferenz zwischen Vor- und Rücklauf."),
    "ETA_TH": ("Thermischer Wirkungsgrad", "Thermischer Wirkungsgrad der Komponente."),
    "G_STC": ("Referenzeinstrahlung", "Solare Einstrahlung unter Standard-Testbedingungen."),
    "HUB_H": ("Nabenhöhe", "Höhe der Rotornabe über dem Gelände."),
    "H_COEFF": ("Hellmann-Exponent", "Exponent zur Umrechnung der Windgeschwindigkeit von der Referenzhöhe auf die Nabenhöhe: Windgeschwindigkeit × (Nabenhöhe / Referenzhöhe)^Exponent."),
    "NORM_POWER": ("Nennleistung", "Nennleistung der Komponente unter Referenzbedingungen."),
    "POTENTIAL": ("Potenzial", "Maximal nutzbares technisches Potenzial der Komponente."),
    "REF_H": ("Referenzhöhe", "Höhe, auf die sich die hinterlegten Eingangsdaten beziehen."),
    "SOC_INIT": ("Anfangsladezustand", "Ladezustand des Speichers zu Beginn der Berechnung."),
    "STO_LOSS": ("Speicherverlust", "Anteil der gespeicherten Energie, der je Stunde durch Selbstentladung oder Wärmeverluste verloren geht. Das Modell rechnet den Verlust auf die Zeitschrittlänge um."),
    "ETA_EL": ("Elektrischer Wirkungsgrad", "Anteil der zugeführten Brennstoffenergie, der als elektrische Energie abgegeben wird; der übrige Anteil wird zu Wärme oder Verlusten."),
    "ENABLE_HEAT_DISS": ("Wärmeabgabe an die Umgebung zulassen", "Erlaubt der Brennstoffzelle, nicht benötigte Wärme an die Umgebung abzugeben und dadurch auch ohne vollständige Wärmenutzung Strom zu erzeugen."),
    "ENABLE_MEASURES": ("Temperatursenkende Maßnahmen", "Berücksichtigt zusätzliche Maßnahmen am Heizsystem, die das erforderliche Temperaturniveau und damit den Strombedarf der Wärmepumpe senken können. Die zusätzlichen Investitionskosten werden mitgerechnet."),
    "MEASURES_INV_FIX": ("Kosten temperatursenkender Maßnahmen", "Zusätzliche Investition je kW thermischer Wärmepumpenleistung für aktivierte Maßnahmen zur Senkung der Heizsystemtemperaturen."),
    "CAP_FEE": ("Leistungspreis Fernwärme", "Jährliches Entgelt je kW installierter Fernwärme-Anschlussleistung, zusätzlich zum Preis der bezogenen Wärmemenge."),
    "AREA_REAL": ("Modulfläche", "Fläche eines einzelnen PV-Moduls; beschreibt die Modulgeometrie und nicht die gesamte belegte Dachfläche."),
    "ETA_EL_REF": ("Elektrischer Referenzwirkungsgrad", "Anteil der auf das PV-Modul einfallenden Strahlungsleistung, der bei Referenzbedingungen in elektrische Leistung umgewandelt wird. Ausgangswert für die Temperaturkorrektur."),
    "T_CELL_REF": ("Referenz-Zelltemperatur", "Zelltemperatur, auf die sich der elektrische PV-Referenzwirkungsgrad bezieht. Abweichungen davon gehen über den Temperaturkoeffizienten in die Ertragsberechnung ein."),
    "G_REF": ("Referenzeinstrahlung", "Bestrahlungsstärke, auf die sich die elektrischen Referenzdaten des PV-Moduls beziehen."),
    "T_CELL_NOCT": ("Zelltemperatur bei NOCT", "Zelltemperatur unter nominalen Betriebsbedingungen (NOCT). Zusammen mit der Einstrahlung dient sie zur Abschätzung der Modulerwärmung und des PV-Wirkungsgrads."),
    "T_AIR_NOCT": ("Lufttemperatur bei NOCT", "Umgebungstemperatur der nominalen Betriebsbedingungen (NOCT), bei denen die zugehörige Zelltemperatur des PV-Moduls angegeben ist."),
    "G_NOCT": ("Einstrahlung bei NOCT", "Bestrahlungsstärke der nominalen Betriebsbedingungen (NOCT); Bezugswert für die Berechnung der einstrahlungsbedingten Erwärmung der PV-Zellen."),
    "ETA_INV": ("Wechselrichterwirkungsgrad", "Verhältnis der abgegebenen Wechselstromleistung zur aufgenommenen Gleichstromleistung des Wechselrichters."),
    "ETA_OPT": ("Optischer Wirkungsgrad", "Anteil der einfallenden Sonnenstrahlung, der nach optischen Verlusten, etwa durch Reflexion, nutzbar bleibt."),
    "P_NOMINAL": ("PV-Nennleistung je Fläche", "Elektrische PV-Nennleistung je Quadratmeter Modulfläche. Dient bei der dezentralen Auslegung als Bezugsgröße für die Batteriekapazität."),
    "T_FLOW": ("Kollektortemperatur", "Temperaturniveau des Solarthermiekollektors. Die Differenz zur Außenlufttemperatur bestimmt die thermischen Verluste und damit den nutzbaren Solarertrag."),
    "ZERO_LOSS": ("Optischer Kollektorwirkungsgrad", "Kollektorwirkungsgrad ohne thermische Verluste, also bei gleicher Kollektor- und Außenlufttemperatur. Ausgangswert vor Abzug der linearen und quadratischen Wärmeverluste."),
    "FIRST_ORDER": ("Linearer Wärmeverlustkoeffizient", "Wärmeverlust je Kollektorfläche und Kelvin Temperaturdifferenz zwischen Kollektor und Außenluft. Ein größerer Wert verringert den Solarthermieertrag."),
    "SECOND_ORDER": ("Quadratischer Wärmeverlustkoeffizient", "Zusätzlicher Wärmeverlust je Kollektorfläche, multipliziert mit dem Quadrat der Temperaturdifferenz zur Außenluft. Erfasst stärker zunehmende Verluste bei hohen Kollektortemperaturen."),
    "SOC_MIN": ("Minimaler Ladezustand", "Untergrenze der gespeicherten Energie als Anteil der Speicherkapazität (0 bis 1). Unterhalb dieser Reserve darf der Speicher nicht entladen werden."),
    "SOC_MAX": ("Maximaler Ladezustand", "Obergrenze der gespeicherten Energie als Anteil der Speicherkapazität (0 bis 1). Zusammen mit dem minimalen Ladezustand bestimmt sie den nutzbaren Speicherbereich."),
    "ETA_STANDBY": ("Stündlicher Speichererhalt", "Anteil der gespeicherten Energie, der nach einer Stunde ohne Laden oder Entladen erhalten bleibt. Beispielsweise bedeuten 99,8 % einen stündlichen Verlust von 0,2 %."),
    "ETA_CH": ("Lade- und Entladewirkungsgrad", "Wirkungsgrad für jeden Lade- und Entladevorgang. Er wird beim Laden und beim Entladen angesetzt; der Wirkungsgrad eines vollständigen Zyklus ergibt sich aus dem Produkt beider Vorgänge."),
    "COEFF_CH": ("Lade- und Entladerate", "Maximale Lade- bzw. Entladeleistung je gespeicherter Wattstunde Kapazität. Beispielsweise entspricht 0,5 W/Wh bei 10 kWh Kapazität einer Leistungsgrenze von 5 kW."),
    "INIT": ("Anfangsladezustand", "Zu Beginn der Betriebsoptimierung gespeicherte Energie als Anteil der Speicherkapazität (0 bis 1)."),
    "T_DIFF_MAX": ("Nutzbare Temperaturspreizung", "Maximale nutzbare Temperaturdifferenz im Wärmespeicher. Zusammen mit Volumen, Dichte und Wärmekapazität des Wassers bestimmt sie dessen speicherbare Wärmeenergie."),
    "T_DHW_NEEDED": ("Warmwassertemperatur", "Erforderliche Temperatur des Trinkwarmwassers; bestimmt das Temperaturniveau der Warmwasserbereitung und die nutzbare Temperaturspreizung des Warmwasserspeichers."),
}

# Technische Erläuterungen für Parameter ohne eigene Präsentationsmetadaten.
# Wiederkehrende Parameterfamilien werden unten mit ihrem konkreten Bezug ergänzt.
PARAMETER_HELP_TEXT_DE = {
    "TIMEZONE": "Zeitverschiebung der lokalen Wetterdaten gegenüber UTC in Stunden. Sie wird für die zeitliche Zuordnung des Sonnenstands verwendet und sollte zum Wetterdatensatz passen.",
    "LOCATION_NAME": "Anzeigename des Projektstandorts. Die verwendeten Wetterdaten werden separat über Wetterdatei oder Postleitzahl gewählt.",
    "USE_GERMAN_ZIP": "Verwendet die deutsche Postleitzahl zur Standortzuordnung und DWD-Testreferenzjahre als Wetterdaten anstelle der EPW-Wetterdatei.",
    "TRYTYPE": "Klimatische Ausprägung des DWD-Testreferenzjahres: Jahr für mittlere Bedingungen, Somm für einen extrem warmen Sommer und Wint für einen extrem kalten Winter.",
    "ZIP": "Deutsche Postleitzahl zur Auswahl des Standorts und der zugehörigen DWD-Klimadaten bei aktivierter Postleitzahlsuche.",
    "WEATHER_FILE": "Pfad zur EPW-Datei mit stündlichen Wetterdaten wie Temperatur, Sonneneinstrahlung und Wind. Relative Pfade beziehen sich auf das Anwendungsverzeichnis.",
    "TIMERESOLUTION": "Dauer eines Simulationszeitschritts in Stunden, zum Beispiel 1 für Stundenwerte oder 0,25 für Viertelstundenwerte. Kleinere Schritte bilden zeitliche Schwankungen genauer ab und erhöhen den Rechenaufwand.",
    "CLUSTERLENGTH": "Dauer eines zusammenhängenden Zeitabschnitts, der beim Clustering durch eine repräsentative Periode ersetzt wird. 86400 Sekunden entsprechen einem Tag, 604800 einer Woche.",
    "CLUSTERNUMBER": "Anzahl repräsentativer Zeitabschnitte für die Optimierung. Mehr Cluster erhalten mehr Unterschiede der Last- und Wetterprofile, vergrößern aber das Optimierungsproblem.",
    "DATARESOLUTION": "Zeitlicher Abstand der Werte in den Eingangsdaten, in Sekunden. Dieser Wert beschreibt die Quelldaten, bevor sie auf die Simulationsauflösung umgerechnet werden.",
    "DATALENGTH": "Gesamtdauer der Eingangsdaten in Sekunden. Zusammen mit der Datenauflösung ergibt sich die erwartete Anzahl der Datenpunkte; 31536000 Sekunden entsprechen 365 Tagen.",
    "HP_SINK_TEMP_LEVELS": "Vor- und Rücklauftemperaturen des Gebäudeheizsystems nach Baualtersklasse und Sanierungszustand. Ihr Mittelwert wird als Senkentemperatur der dezentralen Wärmepumpe verwendet und beeinflusst deren Leistungszahl.",
    "HP_SINK_TEMP_MEASURES_CAP": "Obere Grenze der Wärmepumpen-Senkentemperatur bei aktivierten temperatursenkenden Maßnahmen am Heizsystem. Bereits niedrigere Temperaturen werden dadurch nicht angehoben.",
    "BUILDINGS_SHORT": "Interne Kürzel der Gebäudetypen. Die Reihenfolge muss zu den ausgeschriebenen Gebäudetypen und den gebäudetypabhängigen Kennwertlisten passen.",
    "BUILDINGS_LONG": "Ausgeschriebene Modellbezeichnungen der Gebäudetypen, positionsweise den Gebäudekürzeln zugeordnet.",
    "RETROFIT_SHORT": "Kennziffern der Sanierungsstufen für Wohngebäude: 0 für Bestand, 1 für saniert und 2 für umfassend saniert.",
    "RETROFIT_LONG": "TABULA-Modellbezeichnungen der Sanierungsstufen für Wohngebäude, in derselben Reihenfolge wie die zugehörigen Kennziffern.",
    "RETROFIT_SHORT_NON_RESIDENTIAL": "Kennziffern der Sanierungsstufen für Nichtwohngebäude: 0 für unsaniert, 1 für teilweise und 2 für vollständig saniert.",
    "RETROFIT_LONG_NON_RESIDENTIAL": "Modellbezeichnungen der Sanierungsstufen für Nichtwohngebäude, positionsweise den Kennziffern zugeordnet.",
    "CONSTRUCTION_TYPE_SHORT": "Kennziffern der Bauweise von Nichtwohngebäuden: 0 für leicht, 1 für mittelschwer und 2 für schwer. Die Bauweise beeinflusst die thermische Speichermasse.",
    "CONSTRUCTION_TYPE_LONG": "Bezeichnungen der leichten, mittelschweren und schweren Bauweise, positionsweise den Bauweisen-Kennziffern zugeordnet.",
    "DHWPOWER": "Zusätzliche Auslegungsleistung für die Trinkwarmwasserbereitung je Quadratmeter Gebäudefläche. Die Listeneinträge gehören zu den jeweiligen Gebäudetypen in der festgelegten Reihenfolge.",
    "MEAN_DRAWOFF_VOL_PER_DAY": "Mittlere tägliche Trinkwarmwasser-Zapfmenge je Person in Litern, getrennt nach Gebäudetyp. Sie bestimmt die Höhe des Warmwasserbedarfs.",
    "NUM_INTERPOLATION_POINTS": "Optional. Bleibt das Feld leer, gilt die ausdrücklich angegebene Stützjahrliste. Eine eingetragene Anzahl verteilt die Stützjahre automatisch über die Projektlaufzeit und hat Vorrang vor der Liste.",
    "INTERPOLATION_POINTS": "Stützjahre der Mehrjahresbetrachtung, gezählt ab Jahr 0, zum Beispiel 0, 5, 10, 15. Sie werden verwendet, wenn keine Anzahl von Stützjahren vorgegeben ist, und müssen innerhalb der Projektlaufzeit liegen.",
    "PRICE_HYDROGEN": "Bezugskosten je kWh Wasserstoffenergie. Geht mit der bezogenen Energiemenge in die Brennstoffkosten ein.",
    "REVENUE_FEED_IN_GAS": "Vergütung je kWh Gas, das aus dem Quartier in das Gasnetz eingespeist wird. Die Erlöse mindern die jährlichen Energiekosten.",
    "CO2_HYDROGEN": "Angesetzte CO₂-Emissionen je kWh bezogener Wasserstoffenergie für die Emissionsbilanz und die ökologische Optimierung.",
    "ENABLE_PRICE_CAP_GAS": "Berücksichtigt zusätzlich zu den verbrauchsabhängigen Gaskosten ein Entgelt für die benötigte Gasanschlussleistung.",
    "PRICE_CAP_GAS": "Kostenfaktor für die benötigte Gasanschlussleistung. Im Modell wird er mit der maximal beanspruchten Gasleistung multipliziert und zu den Bezugskosten addiert.",
    "ENABLE_FEED_IN_GAS": "Erlaubt die Einspeisung von im Quartier erzeugtem Gas in das externe Gasnetz und die Anrechnung der zugehörigen Erlöse.",
    "ENABLE_CAP_LIMIT_GAS": "Aktiviert eine Obergrenze für die momentan beanspruchte Gasanschlussleistung. Die Begrenzung der jährlichen Gasmenge wird separat eingestellt.",
    "CAP_LIMIT_GAS": "Obergrenze der Gasanschlussleistung im Optimierungsmodell. Beschränkt die maximal gleichzeitig aus dem Netz bezogene Gasleistung.",
    "PEAK_DEM_MET_CONV": "Verlangt, dass Lastspitzen auch ohne Beiträge von Photovoltaik, Solarthermie und Windkraft gedeckt werden können. Dadurch wird zusätzliche gesicherte Erzeugungsleistung erforderlich.",
    "CO2_EL_FEED_IN": "Emissionsgutschrift je kWh eingespeistem Strom. Wird von den bilanzierten CO₂-Emissionen abgezogen und beeinflusst die ökologische Bewertung der Einspeisung.",
    "CO2_GAS_FEED_IN": "Emissionsgutschrift je kWh eingespeistem Gas. Vermindert die bilanzierten CO₂-Emissionen des Quartiers.",
    "N_CLUSTERS": "Anzahl der Auslegungstage in der EHDO-Konfiguration. Die repräsentativen Perioden der Zeitreihen werden separat über die Clusteranzahl der Zeitkonfiguration festgelegt.",
    "UNIT_PLACEHOLDER": "Darstellungstext für eine nicht angegebene Einheit in der Ausgabe; hat keine physikalische Wirkung auf die Berechnung.",
    "UNIT_DASH": "Darstellung eines Strichs für Größen ohne Einheit in der Ausgabe; hat keine physikalische Wirkung auf die Berechnung.",
    "RHO_AIR": "Masse je Luftvolumen. Dient zusammen mit Luftvolumenstrom und spezifischer Wärmekapazität zur Berechnung des Wärmetransports durch Luftwechsel.",
    "C_P_AIR": "Wärmemenge, die benötigt wird, um ein Kilogramm Luft um ein Kelvin zu erwärmen. Geht in die Berechnung der Lüftungswärmeverluste ein.",
    "RHO_WATER": "Masse je Wasservolumen. Verknüpft Volumen und Masse bei der Berechnung von Wasserströmen und Wärmespeichern.",
    "C_P_WATER": "Wärmekapazität je Kilogramm Wasser und Kelvin Temperaturänderung. Verknüpft Wassermasse und Temperaturspreizung mit der transportierten oder gespeicherten Wärme.",
    "FLUID__C_F": "Spezifische Wärmekapazität des Wärmenetzfluids. Zusammen mit Massenstrom und Temperaturspreizung bestimmt sie die übertragene Wärmeleistung.",
    "FLUID__RHO_F": "Dichte des Wärmenetzfluids. Dient zur Umrechnung zwischen Massen- und Volumenstrom und beeinflusst die hydraulische Berechnung.",
    "FLUID__NU_F": "Kinematische Viskosität des Wärmenetzfluids bei 40 °C. Beeinflusst Reynolds-Zahl, Rohrreibung und damit den Druckverlust im Netz.",
    "PUMP__ETA_PUMP": "Anteil der elektrischen Pumpenleistung, der als hydraulische Leistung nutzbar ist. Ein kleinerer Wirkungsgrad erhöht den Strombedarf für denselben Förderstrom und Druckunterschied; Eingabe als Anteil von 0 bis 1.",
    "PUMP__INV_PUMP": "Investitionskosten je kW Pumpenleistung. Bestimmt zusammen mit der ausgelegten Pumpenleistung die Investition in die Netzpumpen.",
    "PUMP__PUMP_LIFETIME": "Nutzungsdauer der Netzpumpen für die wirtschaftliche Bewertung und Berücksichtigung von Ersatzinvestitionen.",
    "PUMP__COST_OM_PUMP": "Jährliche Betriebs- und Wartungskosten der Netzpumpen als Anteil ihrer Investitionskosten; beispielsweise bedeutet 0,03 einen jährlichen Anteil von 3 %.",
    "PIPE__F_FRIC": "Dimensionsloser Rohrreibungsbeiwert als Startwert der hydraulischen Iteration. Er beschreibt den Einfluss der Rohrreibung auf den Druckverlust.",
    "PIPE__DP_PIPE_MAX": "Maximal zulässiger Druckverlust je Meter Rohr. Begrenzt bei der Auslegung die Strömungsbelastung und beeinflusst Rohrdurchmesser und Pumpenbedarf.",
    "PIPE__DP_PIPE_MIN": "Unterer Auslegungswert des Druckverlusts je Meter Rohr für die hydraulische Rohrdimensionierung.",
    "PIPE__PIPE_LIFETIME": "Nutzungsdauer des Rohrnetzes für die wirtschaftliche Bewertung und Berücksichtigung von Ersatzinvestitionen.",
    "PIPE__COST_OM_PIPE": "Jährliche Betriebs- und Wartungskosten des Rohrnetzes als Anteil der Rohrinvestition; beispielsweise bedeutet 0,005 einen jährlichen Anteil von 0,5 %.",
    "T_HOT_HEATING_NETWORK": "Vorlauftemperaturen des Wärmenetzes nach Netzgeneration und Betriebsweise. Enthält konstante Werte sowie die Stütztemperaturen der außentemperaturabhängigen Heizkurve.",
    "T_COLD_HEATING_NETWORK": "Rücklauftemperaturen des Wärmenetzes nach Netzgeneration und Betriebsweise. Die Differenz zur Vorlauftemperatur bestimmt den für eine Wärmeleistung erforderlichen Massenstrom.",
    "FLUID": "Stoffwerte des Wärmenetzfluids: Wärmekapazität, Dichte und kinematische Viskosität für Wärmeübertragung und hydraulische Berechnung.",
    "PUMP": "Technische und wirtschaftliche Pumpendaten: Wirkungsgrad, spezifische Investition, Lebensdauer und jährliche Wartungskosten.",
    "PIPE": "Hydraulische Auslegungswerte und wirtschaftliche Kennwerte des Rohrnetzes: Reibung, Druckverlustgrenzen, Lebensdauer und Wartungsanteil.",
    "SOLVER_NAME": "Optimierungsprogramm zur Lösung des mathematischen Energiesystemmodells. Der gewählte Solver muss in der Laufzeitumgebung verfügbar sein.",
    "SOLVER_EXECUTABLE": "Optionaler Pfad zur ausführbaren Solver-Datei, falls die gewählte Solver-Anbindung ein externes Programm benötigt und es nicht automatisch findet.",
    "SOLVER_OPTIONS__TIME_LIMIT": "Maximale Rechenzeit eines einzelnen Optimierungslaufs in Minuten. Bei Erreichen der Grenze kann eine bereits gefundene zulässige Lösung verwendet werden, ohne dass deren Optimalität bewiesen ist.",
    "SOLVER_OPTIONS__MIP_GAP": "Zulässige relative Lücke zwischen der besten gefundenen Lösung und der vom Solver bewiesenen Zielfunktionsschranke. 1 % entspricht intern 0,01; kleinere Werte können die Rechenzeit erhöhen.",
    "SOLVER_OPTIONS__THREADS": "Anzahl der Rechenthreads für den Solver, soweit dieser paralleles Rechnen unterstützt. Dieser Wert ist unabhängig von den Workern der Profilerzeugung. Mehr Threads können die Lösung beschleunigen, benötigen aber zusätzliche Prozessorressourcen.",
    "SOLVER_OPTIONS__NONCONVEX": "Gurobi-Option für die Behandlung nichtkonvexer quadratischer Modelle. Der Wert 2 erlaubt deren Bearbeitung; für Solver ohne entsprechende Option wird die Einstellung nicht übertragen.",
    "SOLVER_OPTIONS__DUAL_REDUCTIONS": "Gurobi-Option für duale Modellreduktionen in der Vorverarbeitung: 1 aktiviert, 0 deaktiviert sie. Abschalten kann die Unterscheidung zwischen Unzulässigkeit und Unbeschränktheit erleichtern.",
    "SOLVER_OPTIONS": "Zusammengefasste Solver-Einstellungen, etwa Zeitlimit, Optimalitätslücke und Threadanzahl. Unterstützte Optionen werden auf den gewählten Solver abgebildet.",
    "PAGESIZE": "Papierformat des erzeugten Berichts, etwa A3 oder A4. Das Berichtslayout ist für A4 ausgelegt.",
    "LANGUAGE": "Sprache der Texte und Beschriftungen im Ergebnisbericht: de für Deutsch und en für Englisch.",
    "KPI_SAVE_TYPE": "Dateiformat für den Export der berechneten Kennzahlen: xlsx als Excel-Arbeitsmappe oder csv als Texttabelle.",
    "COLORS": "Farben für Berichtstexte, Energieträger, Diagramme und die Netzdarstellung. Diese Einstellungen beeinflussen ausschließlich die Darstellung.",
    "SIZES": "Symbolradien, Linienbreiten und Schriftgrößen der Quartiers- und Netzdarstellung im Bericht.",
    "LAYOUT_OPTIONS": "Sichtbarkeit von Gebäude- und Leitungsbeschriftungen in der Quartiersdarstellung des Berichts.",
    "FONTS": "Schriftdateien und Schriftgrößen für Titel, Fließtext, Tabellen und Diagrammbeschriftungen im Bericht.",
    "FONTS__REGULAR": "Schriftdatei für regulären Text im Bericht. Der Pfad muss auf eine für die Berichtserstellung verfügbare Schrift zeigen.",
    "FONTS__BOLD": "Schriftdatei für fett dargestellte Texte, etwa Überschriften im Bericht.",
    "LAYOUT_OPTIONS__SHOW_BUILDING_LABELS": "Blendet die Namen von Gebäuden und Energiezentrale in der Quartiersdarstellung des Berichts ein oder aus.",
    "LAYOUT_OPTIONS__SHOW_PIPE_LABELS": "Blendet die Beschriftungen der Rohrleitungen in der Quartiersdarstellung des Berichts ein oder aus.",
}

for _fuel, _name in {"GAS": "Erdgas", "BIOMASS": "Biomasse", "HYDROGEN": "Wasserstoff", "WASTE": "Abfall"}.items():
    PARAMETER_HELP_TEXT_DE.update({
        f"ENABLE_SUPPLY_{_fuel}": f"Erlaubt den externen Bezug von {_name} zur Versorgung des Quartiers. Bei deaktivierter Option steht dieser externe Brennstoffbezug nicht zur Verfügung.",
        f"ENABLE_SUPPLY_LIMIT_{_fuel}": f"Aktiviert eine Obergrenze für die jährlich bezogene Energiemenge aus {_name}, beispielsweise zur Abbildung einer begrenzten Brennstoffverfügbarkeit.",
        f"SUPPLY_LIMIT_{_fuel}": f"Maximal pro Jahr verfügbare Energie aus extern bezogenem {_name} in MWh. Die Grenze gilt bei aktivierter Begrenzung des jährlichen Bezugs.",
    })

for _loss, _meaning in {
    "INVERTER": "die Umwandlung im Wechselrichter",
    "WIRING": "elektrische Widerstände in den Leitungen",
    "CONNECTIONS": "elektrische Steck- und Kontaktverbindungen",
    "SOILING": "Verschmutzung der Moduloberfläche",
    "SHADING": "Verschattung der Module",
    "MISMATCH": "unterschiedliche elektrische Eigenschaften zusammengeschalteter Module",
    "NPR": "Abweichungen der tatsächlichen Modulleistung von der angegebenen Nennleistung",
    "AV": "zeitweilige Nichtverfügbarkeit der Anlage, etwa bei Wartung",
    "LID": "lichtinduzierte Degradation der Module",
}.items():
    PARAMETER_HELP_TEXT_DE[f"D_PV__KAPPA_{_loss}"] = (
        f"Anteil der PV-Leistung, der durch {_meaning} verloren geht. "
        "Eingabe als Anteil, zum Beispiel 0,02 für 2 %. Die Korrekturfaktoren werden im Modell addiert und vom ungekürzten Ertrag abgezogen."
    )

for _side, _name in {"HOT": "Vorlauftemperatur", "COLD": "Rücklauftemperatur"}.items():
    for _generation, _number in {"3RD": 3, "4TH": 4, "5TH": 5}.items():
        _prefix = f"T_{_side}_HEATING_NETWORK"
        PARAMETER_HELP_TEXT_DE[f"{_prefix}__CONSTANT__{_generation}"] = (
            f"Zeitlich konstante {_name} des Wärmenetzes der {_number}. Generation. "
            "Wird bei konstanter Temperaturführung verwendet und beeinflusst Wärmeverluste und erforderliche Volumenströme."
        )
        for _bound, _condition in {"MAX": "hoher", "MIN": "niedriger"}.items():
            PARAMETER_HELP_TEXT_DE[f"{_prefix}__HEATING_CURVE__{_bound}__{_generation}"] = (
                f"{_name} des Wärmenetzes der {_number}. Generation bei {_condition} Außentemperatur. "
                "Stützpunkt der Heizkurve; zwischen den Stützpunkten passt das Modell die Netztemperatur an die Außenlufttemperatur an."
            )

for _key, _meaning in {
    "PRIMARY_COLOR": "Rahmen und Hauptlinien", "SECONDARY_COLOR": "ergänzende Diagrammelemente wie Balken",
    "BACKGROUND": "Seiten- und Tabellenhintergründe", "TEXT": "Texte und Überschriften",
    "TEXT_LIGHT": "zurückhaltend dargestellte Zusatzinformationen",
    "ENERGY__ELECTRICITY": "Strombedarf", "ENERGY__HEATING": "Raumwärmebedarf",
    "ENERGY__DHW": "Trinkwarmwasserbedarf", "ENERGY__COOLING": "Kältebedarf", "ENERGY__EV": "Elektromobilität",
    "SOURCE__ELECTRICITY": "Netzstrom", "SOURCE__GAS": "Erdgas", "SOURCE__OIL": "Heizöl",
    "SOURCE__WASTE": "Abfall", "SOURCE__BIOMASS": "Biomasse", "SOURCE__DISTRICT_HEAT": "Fernwärme",
    "SOURCE__HYDROGEN": "Wasserstoff", "SOURCE__WASTE_HEAT": "Abwärme",
    "SOURCE__EH_FIXED": "Fixkosten der Energiezentrale", "SOURCE__DECENTRAL_FIXED": "Fixkosten dezentraler Anlagen",
    "SOURCE__REVENUE_FEED_IN_EL": "Erlöse aus Stromeinspeisung",
    "LAYOUT__BUILDING_CONNECTED": "an das Wärmenetz angeschlossene Gebäude",
    "LAYOUT__BUILDING_NOT_CONNECTED": "Gebäude ohne Wärmenetzanschluss",
    "LAYOUT__EH": "die Energiezentrale", "LAYOUT__PIPE": "Rohrleitungen",
}.items():
    PARAMETER_HELP_TEXT_DE[f"COLORS__{_key}"] = f"Darstellungsfarbe für {_meaning} im Ergebnisbericht und seinen Diagrammen."

for _key, _meaning in {
    "TITLE": "den Berichtstitel", "SECTION_TITLE": "Abschnittsüberschriften",
    "SUBSECTION_TITLE": "Unterabschnittsüberschriften", "HIGHLIGHTED": "hervorgehobene Kennzahlen",
    "BODY": "Fließtext", "SMALL": "kleine Zusatztexte", "TABLE": "Tabellentexte",
    "AXIS_VALUES": "Achsenwerte in Diagrammen", "DENSE": "kompakte, dicht belegte Darstellungen",
    "PAGE_NUMBER": "Seitenzahlen",
}.items():
    PARAMETER_HELP_TEXT_DE[f"FONTS__SIZES__{_key}"] = f"Schriftgröße in Punkt für {_meaning} im Ergebnisbericht."

for _key, _meaning in {
    "BUILDING": "Radius der Kreissymbole für Gebäude",
    "EH": "Radius des Kreissymbols für die Energiezentrale",
    "PIPE": "Strichbreite der Rohrleitungen",
    "LABEL": "Schriftgröße der Gebäude- und Leitungsbeschriftungen",
    "LEGEND_TEXT": "Schriftgröße der Legendentexte",
}.items():
    PARAMETER_HELP_TEXT_DE[f"SIZES__{_key}"] = f"{_meaning} in der Quartiersdarstellung des Berichts. Beeinflusst nur die Darstellung, nicht die physikalische Auslegung."

PERCENT_PARAMETER_SUFFIXES = (
    "ETA", "ETA_TH", "COST_OM", "INV_SUBSIDY_RATE", "SUBSIDY_RATE",
    "ASHP_CARNOT_EFF", "GRADE", "SOC_INIT", "STO_LOSS",
)

SECTION_PRESENTATION = {
    **PROJECT_SECTION_PRESENTATION,
    **MICROGRID_SECTION_PRESENTATION,
    **BUILDING_SECTION_PRESENTATION,
    **SIMULATION_SECTION_PRESENTATION,
}


def _config_navigation_sections() -> list[dict]:
    """Liefert die HEO-Bezeichnungen und Reihenfolge der Konfiguratorbereiche."""

    return [
        {"key": PROJECT_LOAD_SECTION, "label": "🔁 Projekt laden"},
        {"key": "location", "label": SECTION_TITLES["location"]},
        {"key": MICROGRID_GROUP_SECTION, "label": "Microgrid-Konfiguration"},
        {"key": BUILDING_GROUP_SECTION, "label": "Gebäude-Konfiguration"},
        {"key": SIMULATION_CONFIG_SECTION, "label": "Simulationskonfiguration"},
        {"key": ADVANCED_CONFIG_SECTION, "label": "Erweiterte Konfiguration"},
    ]

# Gruppiert Aktivierungsschalter mit den von ihnen freigegebenen HEO-Feldern.
ACTIVATION_FIELD_GROUPS: dict[str, dict[str, Any]] = {
    "CONSIDER_HEATING_PERIOD": {
        "fields": ("HEATING_PERIOD_START", "HEATING_PERIOD_END"),
        "title": "Heizperiode", "kind": "period",
    },
    "CONSIDER_COOLING_PERIOD": {
        "fields": ("COOLING_PERIOD_START", "COOLING_PERIOD_END"),
        "title": "Kühlperiode", "kind": "period",
    },
    "ENABLE_TRAFOMAX_W": {"fields": ("TRAFOMAX_W",)},
    "ENABLE_BUILDINGMAX_W": {"fields": ("BUILDINGMAX_W",)},
    "ENABLE_PRICE_CAP_EL": {"fields": ("PRICE_CAP_EL",)},
    "ENABLE_CAP_LIMIT_EL": {"fields": ("CAP_LIMIT_EL",)},
    "ENABLE_SUPPLY_LIMIT_EL": {"fields": ("SUPPLY_LIMIT_EL",)},
    "ENABLE_PRICE_CAP_GAS": {"fields": ("PRICE_CAP_GAS",)},
    "ENABLE_CAP_LIMIT_GAS": {"fields": ("CAP_LIMIT_GAS",)},
    "ENABLE_SUPPLY_LIMIT_BIOMASS": {"fields": ("SUPPLY_LIMIT_BIOMASS",)},
    "ENABLE_SUPPLY_LIMIT_HYDROGEN": {"fields": ("SUPPLY_LIMIT_HYDROGEN",)},
    "ENABLE_SUPPLY_LIMIT_WASTE": {"fields": ("SUPPLY_LIMIT_WASTE",)},
}
