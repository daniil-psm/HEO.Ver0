"""Zuordnung der Parameter zu den main- und more-Dialogbereichen"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable

from heo.display.form_content import field_key, plan_form_content

# Winkelparameter der zentralen Anlagen und deren Neigungswinkel.
CENTRAL_ANGLE_FIELD_KEYS = {
    "C_PV__BETA", "C_PV__GAMMA", "C_STC__BETA", "C_STC__GAMMA",
}
CENTRAL_INCLINATION_FIELD_KEYS = {"C_PV__BETA", "C_STC__BETA"}


# Fachliche Feldgruppen der HEO-Eingabedialoge.
RESOURCE_ECO_FIELDS = {
    "gas": ("PRICE_SUPPLY_GAS_EH", "CO2_GAS", "CO2_TAX"),
    "biomass": ("PRICE_BIOMASS", "CO2_BIOM", "CO2_TAX"),
    "waste": ("PRICE_WASTE", "CO2_WASTE", "CO2_TAX"),
    "oil": ("PRICE_OIL", "CO2_OIL", "CO2_TAX"),
    "hydrogen": ("PRICE_HYDROGEN", "CO2_HYDROGEN", "CO2_TAX"),
}

BUILDING_ECO_FIELDS = (
    "PRICE_SUPPLY_EL",
    "REVENUE_FEED_IN_EL",
    "ENABLE_BUILDINGMAX_W",
    "BUILDINGMAX_W",
)


# Parameter, die beim Anklicken einer dezentralen Komponenten eines Gebäudes angezeigt werden


# Gemeinsame Parameter von Stromnetz und Strompille. Die Freigabe des
# Strombezugs ist kein manuelles Feld, sondern folgt ``grid_enabled``.
POWER_SHARED_FIELDS = (
    "ENABLE_TRAFOMAX_W",
    "TRAFOMAX_W",
    "PRICE_SUPPLY_EL_EH",
    "REVENUE_FEED_IN_EL_EH",
    "CO2_EL_GRID",
    "ENABLE_FEED_IN_EL",
    "ENABLE_PRICE_CAP_EL",
    "PRICE_CAP_EL",
    "ENABLE_CAP_LIMIT_EL",
    "CAP_LIMIT_EL",
    "ENABLE_SUPPLY_LIMIT_EL",
    "SUPPLY_LIMIT_EL",
)
GRID_FIELDS = POWER_SHARED_FIELDS

PROJECT_FIELDS = (
    "SCENARIO_NAME",
    "DISTRICT_AREA_M2",
    "INTEREST_RATE",
    "OBSERVATION_TIME",
)

# Aktivierungsschalter und die dadurch relevanten Eingaben werden in sämtlichen
# Formularen als ein Parameterblock dargestellt. Technische DG-Schlüssel
# bleiben dabei unverändert.

# Felder, die in mehreren Einblendungen angeboten werden dürfen, bis sie dort
# erstmals manuell geändert wurden. Danach gehört das Feld für die laufende
# Konfigurator-Sitzung der bearbeitenden Einblendung.
HEATING_PERIOD_FIELDS = (
    "CONSIDER_HEATING_PERIOD", "HEATING_PERIOD_START", "HEATING_PERIOD_END",
)
COOLING_PERIOD_FIELDS = (
    "CONSIDER_COOLING_PERIOD", "COOLING_PERIOD_START", "COOLING_PERIOD_END",
)
HEAT_NETWORK_FIELDS = (
    "TEMPERATURE_MODE", "D_HEATING_NETWORK",
)
COOL_NETWORK_FIELDS = (
    "T_HOT_COOLING_NETWORK", "T_COLD_COOLING_NETWORK", "D_COOLING_NETWORK",
)
SHARED_NETWORK_FIELDS = (
    "GENERATION", "TOPOLOGY_OPTION", "HEURISTIC", "DELTA_T_HEATTRANSFER",
    "LIFE_TIME", "ASPHALTLAYER", "D_ASPH", "GRID_DEPTH", "K_SOIL",
    "K_PUF", "K_PE", "H_LOSS_SUBST", "DP_SUBSTATION", "DP_ENERGY_HUB",
    "C_SUBST", "COST_OM_SUBST", "LIFETIME_SUBST", "C_OM",
)



def split_parameter_dialog_fields(
    fields: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Teilt Felder auf, ohne Gruppen zwischen main und more zu zerlegen."""

    field_list = list(fields)
    plan = plan_form_content(field_list)
    # Die Zuordnung des Controllers gilt für den gesamten abhängigen Inhalt.
    main_keys = {
        field_key(field)
        for item in plan.items if item.field.get("konfigurator_view") == "main"
        for field in item.fields()
    }
    unique_fields = {field_key(field): field for field in field_list}.values()
    main = [field for field in unique_fields if field_key(field) in main_keys]
    more = [field for field in unique_fields if field_key(field) not in main_keys]
    return main, more


# Projektdialog
PROJECT_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "SCENARIO_NAME": "main",
    "DISTRICT_AREA": "main",
    "INTEREST_RATE": "main",
    "OBSERVATION_TIME": "main",
    "OPTIMIZATION_FOCUS": "main",
    "ENABLE_TRAFOMAX_W": "main",
    "TRAFOMAX_W": "main",
    "ENABLE_BUILDINGMAX_W": "main",
    "BUILDINGMAX_W": "main",
    "PRICE_SUPPLY_EL": "main",
    "PRICE_SUPPLY_EL_EH": "main",
    "PRICE_SUPPLY_GAS": "main",
    "PRICE_SUPPLY_GAS_EH": "main",
    "PRICE_GASOLINE_LITER": "main",
    "PRICE_WASTE": "main",
    "PRICE_BIOMASS": "main",
    "PRICE_OIL": "main",
    "PRICE_DISTRICT_HEAT": "main",
    "REVENUE_FEED_IN_EL": "main",
    "REVENUE_FEED_IN_EL_EH": "main",
    "CO2_EL_GRID": "main",
    "CO2_GAS": "main",
    "CO2_BIOM": "main",
    "CO2_WASTE": "main",
    "CO2_OIL": "main",
    "CO2_DISTRICT_HEAT": "main",
    # Weitere Parameter
    "WEATHER_FILE": "more",
    "TIMEZONE": "more",
    "ALBEDO": "more",
    "LOCATION_NAME": "more",
    "USE_GERMAN_ZIP": "more",
    "TRYYEAR": "more",
    "TRYTYPE": "more",
    "ZIP": "more",
    "NUM_INTERPOLATION_POINTS": "more",
    "INTERPOLATION_POINTS": "more",
    "PRICE_HYDROGEN": "more",
    "REVENUE_FEED_IN_GAS": "more",
    "CO2_HYDROGEN": "more",
    "CO2_TAX": "more",
}


# Stromnetz- und Energieträgerdialoge
SUPPLY_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "ENABLE_SUPPLY_EL": "main",
    "ENABLE_FEED_IN_EL": "main",
    # Weitere Parameter
    "ENABLE_PRICE_CAP_EL": "more",
    "PRICE_CAP_EL": "more",
    "ENABLE_CAP_LIMIT_EL": "more",
    "CAP_LIMIT_EL": "more",
    "ENABLE_SUPPLY_LIMIT_EL": "more",
    "SUPPLY_LIMIT_EL": "more",
    "ENABLE_SUPPLY_GAS": "more",
    "ENABLE_PRICE_CAP_GAS": "more",
    "PRICE_CAP_GAS": "more",
    "ENABLE_FEED_IN_GAS": "more",
    "ENABLE_CAP_LIMIT_GAS": "more",
    "CAP_LIMIT_GAS": "more",
    "ENABLE_SUPPLY_BIOMASS": "more",
    "ENABLE_SUPPLY_LIMIT_BIOMASS": "more",
    "SUPPLY_LIMIT_BIOMASS": "more",
    "ENABLE_SUPPLY_HYDROGEN": "more",
    "ENABLE_SUPPLY_LIMIT_HYDROGEN": "more",
    "SUPPLY_LIMIT_HYDROGEN": "more",
    "ENABLE_SUPPLY_WASTE": "more",
    "ENABLE_SUPPLY_LIMIT_WASTE": "more",
    "SUPPLY_LIMIT_WASTE": "more",
    "PEAK_DEM_MET_CONV": "more",
    "CO2_EL_FEED_IN": "more",
    "CO2_GAS_FEED_IN": "more",
    "N_CLUSTERS": "more",
}


# Wärme- und Kältenetzdialoge
NETWORK_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "GENERATION": "main",
    "TOPOLOGY_OPTION": "main",
    # Weitere Parameter
    "LIFE_TIME": "more",
    "TEMPERATURE_MODE": "more",
    "D_HEATING_NETWORK": "more",
    "D_COOLING_NETWORK": "more",
    "T_HOT_COOLING_NETWORK": "more",
    "T_COLD_COOLING_NETWORK": "more",
    "DELTA_T_HEATTRANSFER": "more",
    "HEURISTIC": "more",
    "ASPHALTLAYER": "more",
    "D_ASPH": "more",
    "GRID_DEPTH": "more",
    "K_SOIL": "more",
    "K_PUF": "more",
    "K_PE": "more",
    "H_LOSS_SUBST": "more",
    "DP_SUBSTATION": "more",
    "DP_ENERGY_HUB": "more",
    "C_SUBST": "more",
    "COST_OM_SUBST": "more",
    "LIFETIME_SUBST": "more",
    "C_OM": "more",
}


# Gebäudelastdialog
BUILDING_LOAD_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "T_SET_MIN": "main",
    "T_SET_MAX": "main",
    "CONSIDER_HEATING_PERIOD": "main",
    "HEATING_PERIOD_START": "main",
    "HEATING_PERIOD_END": "main",
    "CONSIDER_COOLING_PERIOD": "main",
    "COOLING_PERIOD_START": "main",
    "COOLING_PERIOD_END": "main",
    # Weitere Parameter
    "T_SET_MIN_NIGHT": "more",
    "VENTILATION_RATE": "more",
    "THERMAL_MODEL_TYPE": "more",
    "T_SET_MIN_FREE_DAY": "more",
    "T_SET_MAX_NIGHT": "more",
    "T_BIVALENT": "more",
    "T_HEATLIMIT": "more",
}


# Gebäudedialog
BUILDING_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "category": "main",
    "building": "main",
    "year": "main",
    "area": "main",
    "heater": "main",
    "retrofit": "main",
    "construction_type": "main",
    # Szenarioweite Gebäudelastparameter, die zusätzlich an jedem Gebäude bearbeitet werden können.
    "T_SET_MIN": "main",
    "T_SET_MAX": "main",
    # Weitere Parameter
    "cooling": "more",
    "dhw": "more",
    "EV": "main",
    "night_setback": "more",
    "T_SET_MIN_NIGHT": "more",
    "T_SET_MAX_NIGHT": "more",
    "T_SET_MIN_FREE_DAY": "more",
    "VENTILATION_RATE": "more",
    "THERMAL_MODEL_TYPE": "more",
    "CONSIDER_HEATING_PERIOD": "more",
    "HEATING_PERIOD_START": "more",
    "HEATING_PERIOD_END": "more",
    "CONSIDER_COOLING_PERIOD": "more",
    "COOLING_PERIOD_START": "more",
    "COOLING_PERIOD_END": "more",
}

BUILDING_PARAMETER_VISIBILITY = {
    "retrofit": ("residential", "mixed", "non_residential"),
    "construction_type": ("non_residential", "mixed"),
}


# Gemeinsame Parameter der dezentralen PV- und Solarthermiedialoge
DECENTRAL_SOLAR_ANGLE_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "beta_PV": "main",
    "gamma_PV": "main",
    # Weitere Parameter

}


# Dezentraler PV-Dialog
DECENTRAL_PV_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "f_PV1": "main",
    "f_PV2": "main",
    # Weitere Parameter

}


# Dezentraler Solarthermiedialog
DECENTRAL_STC_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "f_STC": "main",
    # Weitere Parameter

}


# Dezentraler Batteriedialog
DECENTRAL_BATTERY_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "f_BAT": "main",
    # Weitere Parameter
    # Derzeit keine.
}


# Dezentraler Wärmespeicherdialog
DECENTRAL_HEAT_STORAGE_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "f_TES": "main",
    # Weitere Parameter

}


# Dezentraler Elektromobilitätsdialog
DECENTRAL_EV_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "EV": "main",
    "ev_charging": "main",
    # Weitere Parameter

}

# zus. szenarioweite Auslegungsparameter für dezentrale WP bzw. dezentrale WP-Hybridsysteme
DECENTRAL_HEAT_PUMP_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter

    # Weitere Parameter
    "T_BIVALENT": "more",
}

# Dezentrale Gerätedialoge; * steht für das jeweilige Gerätekürzel
DECENTRAL_DEVICE_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "D_*__ETA_EL": "main",
    "D_*__ETA_EL_REF": "main",
    "D_*__ETA_INV": "main",
    "D_*__LIFE_TIME": "main",
    "D_*__INV_BASE": "main",
    "D_*__INV_SUBSIDY_RATE": "main",
    "D_*__ETA_TH": "main",
    "D_*__GAMMA": "main",
    # Weitere Parameter
    "D_*__GRADE": "more",
    "D_*__T_COOLING": "more",
    "D_*__COP_MAX": "more",
    "D_*__COST_OM": "more",
    "D_*__enable_measures": "more",
    "D_*__measures_inv_fix": "more",
    "D_*__CAP_FEE": "more",
    "D_*__AREA_REAL": "more",
    "D_*__T_CELL_REF": "more",
    "D_*__G_REF": "more",
    "D_*__T_CELL_NOCT": "more",
    "D_*__T_AIR_NOCT": "more",
    "D_*__G_NOCT": "more",
    "D_*__ETA_OPT": "more",
    "D_*__P_NOMINAL": "more",
    "D_*__KAPPA_INVERTER": "more",
    "D_*__KAPPA_WIRING": "more",
    "D_*__KAPPA_CONNECTIONS": "more",
    "D_*__KAPPA_SOILING": "more",
    "D_*__KAPPA_SHADING": "more",
    "D_*__KAPPA_MISMATCH": "more",
    "D_*__KAPPA_NPR": "more",
    "D_*__KAPPA_AV": "more",
    "D_*__KAPPA_LID": "more",
    "D_*__T_FLOW": "more",
    "D_*__ZERO_LOSS": "more",
    "D_*__FIRST_ORDER": "more",
    "D_*__SECOND_ORDER": "more",
    "D_*__SOC_MIN": "more",
    "D_*__SOC_MAX": "more",
    "D_*__ETA_STANDBY": "more",
    "D_*__ETA_CH": "more",
    "D_*__COEFF_CH": "more",
    "D_*__INIT": "more",
    "D_*__T_DIFF_MAX": "more",
    "D_*__T_DHW_NEEDED": "more",
}


# Zentrale Gerätedialoge; * steht für das jeweilige Gerätekürzel
CENTRAL_DEVICE_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "C_*__ETA": "main",
    "C_*__BETA": "main",
    "C_*__GAMMA": "main",
    "C_*__INV_BASE": "main",
    "C_*__MIN_AREA": "main",
    "C_*__MAX_AREA": "main",
    "C_*__MIN_CAP": "main",
    "C_*__MAX_CAP": "main",
    "C_*__NORM_POWER": "main",
    "C_*__POTENTIAL": "main",
    "C_*__ETA_TH": "main",
    "C_*__COP": "main",
    "C_*__COP_CONST": "main",
    "C_*__MIN_VOL": "main",
    "C_*__MAX_VOL": "main",
    "C_*__DELTA_T": "main",
    "C_*__SOC_INIT": "main",
    # Weitere Parameter
    "C_*__FEASIBLE": "more",
    "C_*__LIFE_TIME": "more",
    "C_*__COST_OM": "more",
    "C_*__G_STC": "more",
    "C_*__INV_SUBSIDY_RATE": "more",
    "C_*__H_COEFF": "more",
    "C_*__HUB_H": "more",
    "C_*__REF_H": "more",
    "C_*__ETA_EL": "more",
    "C_*__CCOP_FEASIBLE": "more",
    "C_*__ASHP_CARNOT_FEASIBLE": "more",
    "C_*__ASHP_MODEL_FEASIBLE": "more",
    "C_*__CSV_FEASIBLE": "more",
    "C_*__ASHP_CARNOT_EFF": "more",
    "C_*__ASHP_SUPPLY_TEMP": "more",
    "C_*__ASCC_MODEL_FEASIBLE": "more",
    "C_*__ENABLE_HEAT_DISS": "more",
    "C_*__STO_LOSS": "more",
}


# Simulationsdialog
SIMULATION_PARAMETER_DIALOG_FIELDS = {
    # Main-Parameter
    "TIMERESOLUTION": "main",
    "CLUSTERNUMBER": "main",
    "SOLVER_NAME": "main",
    "LANGUAGE": "main",
    # Weitere Parameter
    "CLUSTERLENGTH": "more",
    "DATARESOLUTION": "more",
    "DATALENGTH": "more",
    "RHO_AIR": "more",
    "C_P_AIR": "more",
    "RHO_WATER": "more",
    "C_P_WATER": "more",
    "SOLVER_EXECUTABLE": "more",
    "SOLVER_OPTIONS__TIME_LIMIT": "more",
    "SOLVER_OPTIONS__MIP_GAP": "more",
    "SOLVER_OPTIONS__THREADS": "more",
    "SOLVER_OPTIONS__NONCONVEX": "more",
    "SOLVER_OPTIONS__DUAL_REDUCTIONS": "more",
    "PAGESIZE": "more",
    "KPI_SAVE_TYPE": "more",
    "COLORS__*": "more",
    "SIZES__*": "more",
    "LAYOUT_OPTIONS__*": "more",
    "FONTS__*": "more",
}


PARAMETER_DIALOG_FIELD_LISTS = (
    PROJECT_PARAMETER_DIALOG_FIELDS,
    SUPPLY_PARAMETER_DIALOG_FIELDS,
    NETWORK_PARAMETER_DIALOG_FIELDS,
    BUILDING_LOAD_PARAMETER_DIALOG_FIELDS,
    BUILDING_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_SOLAR_ANGLE_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_PV_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_STC_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_BATTERY_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_HEAT_STORAGE_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_EV_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_HEAT_PUMP_PARAMETER_DIALOG_FIELDS,
    CENTRAL_DEVICE_PARAMETER_DIALOG_FIELDS,
    DECENTRAL_DEVICE_PARAMETER_DIALOG_FIELDS,
    SIMULATION_PARAMETER_DIALOG_FIELDS,
)


def parameter_dialog_view(key: str) -> str:
    """Liefert den zentral konfigurierten Dialogbereich eines Parameters."""

    for fields in PARAMETER_DIALOG_FIELD_LISTS:
        if key in fields:
            return fields[key]
        for pattern, view in fields.items():
            if "*" in pattern and fnmatchcase(key, pattern):
                return view
    raise KeyError(f"Parameter ist keinem Dialogbereich zugeordnet: {key}")


def building_parameter_visible(key: str, category: str | None) -> bool:
    """Prüft die bedingte Sichtbarkeit eines Gebäudeparameters."""

    categories = BUILDING_PARAMETER_VISIBILITY.get(key)
    return categories is None or category in categories
