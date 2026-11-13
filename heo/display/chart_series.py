"""Zentrale HEO-Beschriftungen, Datenfelder und Farben für Ergebniszeitreihen."""

from __future__ import annotations

TEMP_COLOR = "#ff6678"

SOLAR_COLOR = "#f2b43c"

ENVIRONMENT_SERIES = {
    "temperature": {
        "label": "Temperatur",
        "data_key": "daily_temperature_mean_C",
        "color": TEMP_COLOR,
        "axis_title": "Temperatur [°C]",
        "unit": "°C",
        "step": 10.0,
        "special_decimals": 1,
        "regular_decimals": 0,
        "hover_decimals": 1,
    },
    "solar": {
        "label": "Globalstrahlung",
        "data_key": "daily_solar_Wh_m2_day",
        "color": SOLAR_COLOR,
        "axis_title": "Globalstrahlung [Wh/(m²·Tag)]",
        "unit": "Wh/(m²·Tag)",
        "step": 1000.0,
        "special_decimals": 0,
        "regular_decimals": 0,
        "hover_decimals": 0,
    },
    "direct_solar": {
        "label": "Direktstrahlung",
        "data_key": "daily_direct_solar_Wh_m2_day",
        "color": "#ff8a3d",
        "axis_title": "Direktstrahlung [Wh/(m²·Tag)]",
        "unit": "Wh/(m²·Tag)",
        "step": 1000.0,
        "special_decimals": 0,
        "regular_decimals": 0,
        "hover_decimals": 0,
    },
    "diffuse_solar": {
        "label": "Diffusstrahlung",
        "data_key": "daily_diffuse_solar_Wh_m2_day",
        "color": "#ffe082",
        "axis_title": "Diffusstrahlung [Wh/(m²·Tag)]",
        "unit": "Wh/(m²·Tag)",
        "step": 500.0,
        "special_decimals": 0,
        "regular_decimals": 0,
        "hover_decimals": 0,
    },
    "wind": {
        "label": "Windgeschwindigkeit",
        "data_key": "daily_wind_speed_mean_m_s",
        "color": "#60d5e8",
        "axis_title": "Windgeschwindigkeit [m/s]",
        "unit": "m/s",
        "step": 2.0,
        "special_decimals": 1,
        "regular_decimals": 0,
        "hover_decimals": 1,
    },
    "humidity": {
        "label": "Luftfeuchte",
        "data_key": "daily_relative_humidity_mean_pct",
        "color": "#5aa2ff",
        "axis_title": "Relative Luftfeuchte [%]",
        "unit": "%",
        "step": 10.0,
        "special_decimals": 1,
        "regular_decimals": 0,
        "hover_decimals": 1,
    },
    "pressure": {
        "label": "Luftdruck",
        "data_key": "daily_pressure_mean_hPa",
        "color": "#b995ff",
        "axis_title": "Luftdruck [hPa]",
        "unit": "hPa",
        "step": 10.0,
        "special_decimals": 1,
        "regular_decimals": 0,
        "hover_decimals": 1,
    },
    "clouds": {
        "label": "Bewölkung",
        "data_key": "daily_cloud_cover_mean_pct",
        "color": "#d7dce2",
        "axis_title": "Bewölkung [%]",
        "unit": "%",
        "step": 10.0,
        "special_decimals": 1,
        "regular_decimals": 0,
        "hover_decimals": 1,
    },
}

ENVIRONMENT_SERIES_OPTIONS = [
    {"label": profile["label"], "value": key}
    for key, profile in ENVIRONMENT_SERIES.items()
]

LOAD_COLOR = "#e5ab37"      # AC

DC_COLOR = "#0f8f50"        # DC

EV_COLOR = "#9f7aea"

DHW_COLOR = "#e5ab37"

HEAT_COLOR = "#ff5a52"      # Wärme

COOLING_COLOR = "#4ea8ff"   # Kälte

ELECTRICITY_COLOR = "#48d597"

DEMAND_SERIES = {
    "heat": {
        "label": "Wärmebedarf",
        "column": "heat_kwh_day",
        "color": HEAT_COLOR,
    },
    "dhw": {
        "label": "Warmwasserbedarf",
        "column": "dhw_kwh_day",
        "color": DHW_COLOR,
    },
    "cooling": {
        "label": "Kältebedarf",
        "column": "cooling_kwh_day",
        "color": COOLING_COLOR,
    },
    "electricity": {
        "label": "Strombedarf",
        "column": "electricity_total_kwh_day",
        "color": ELECTRICITY_COLOR,
    },
}

DEMAND_SERIES_OPTIONS = [
    {"label": profile["label"], "value": key}
    for key, profile in DEMAND_SERIES.items()
]

