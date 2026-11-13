# Liest Optimierungs-, Wetter- und Bedarfsprofile für die Powerflow Card.

from __future__ import annotations

import numpy as np
import pandas as pd

# Liest die PFC-Leistungsreihen aus einem Optimierungsergebnis.
def get_optimization_power_series(optimization_data: dict | None) -> dict | None:
    if not optimization_data:
        return None

    powerflow = optimization_data.get("powerflow", {})
    series = powerflow.get("series")

    if not series:
        return None

    return series

# Liest alle Leistungswerte des gewählten Zeitschritts.
def get_optimization_snapshot(
    optimization_data: dict | None,
    tick: int = 0,
) -> dict | None:
    series = get_optimization_power_series(optimization_data)

    if not series:
        return None

    t_list = series.get("t", [])

    if not t_list:
        return None

    idx = int(tick or 0) % len(t_list)

    def value(key: str, default: float = 0.0) -> float:
        values = series.get(key)
        if not values:
            return default
        return float(values[idx])

    return {
        "t": int(value("t", idx)),

        "grid_import_kw": value("grid_import_kw"),
        "grid_export_kw": value("grid_export_kw"),

        "pv_used_kw": value("pv_used_kw"),
        "pv_curtail_kw": value("pv_curtail_kw"),

        "ac_to_dc_kw": value("ac_to_dc_kw"),
        "dc_to_ac_kw": value("dc_to_ac_kw"),

        "battery_charge_kw": value("battery_charge_kw"),
        "battery_discharge_kw": value("battery_discharge_kw"),
        "battery_soc_kwh": value("battery_soc_kwh"),

        "thermal_charge_kw": value("thermal_charge_kw"),
        "thermal_discharge_kw": value("thermal_discharge_kw"),
        "thermal_soc_kwh": value("thermal_soc_kwh"),

        "hp_el_heat_kw": value("hp_el_heat_kw"),
        "hp_el_cool_kw": value("hp_el_cool_kw"),
        "hp_heat_kw": value("hp_heat_kw"),
        "hp_cooling_kw": value("hp_cooling_kw"),

        "ac_load_kw": value("ac_load_kw"),
        "dc_load_kw": value("dc_load_kw"),
        "heat_load_kw": value("heat_load_kw"),
        "cooling_load_kw": value("cooling_load_kw"),
    }

# Findet den ersten vorhandenen Schlüssel einer Datenquelle.
def _find_first_existing_key(data: dict, candidates: list[str]) -> str | None:
    for key in candidates:
        if key in data and data[key] is not None:
            return key
    return None

# Wählt anhand von Temperatur und Strahlung einen repräsentativen Tag oder Monat.
def select_profile_dataframe(
    weather_df: pd.DataFrame,
    profile: str,
) -> pd.DataFrame:

    df = weather_df.copy()

    daily = (
        df.groupby("date")
        .agg(
            temperature_mean_C=("temperature_C", "mean"),
            temperature_max_C=("temperature_C", "max"),
            temperature_min_C=("temperature_C", "min"),
            irradiance_sum_Wh_m2=("irradiance_W_m2", "sum"),
        )
        .reset_index()
    )

    monthly = (
        df.groupby("month")
        .agg(
            temperature_mean_C=("temperature_C", "mean"),
            irradiance_sum_Wh_m2=("irradiance_W_m2", "sum"),
        )
        .reset_index()
    )

    if profile == "summer_day":
        selected_date = daily.sort_values(
            ["temperature_mean_C", "temperature_max_C", "irradiance_sum_Wh_m2"],
            ascending=[False, False, False],
        ).iloc[0]["date"]

        return df[df["date"] == selected_date].reset_index(drop=True)

    if profile == "winter_day":
        selected_date = daily.sort_values(
            ["temperature_mean_C", "temperature_min_C", "irradiance_sum_Wh_m2"],
            ascending=[True, True, True],
        ).iloc[0]["date"]

        return df[df["date"] == selected_date].reset_index(drop=True)

    if profile == "summer_month":
        selected_month = int(
            monthly.sort_values(
                ["temperature_mean_C", "irradiance_sum_Wh_m2"],
                ascending=[False, False],
            ).iloc[0]["month"]
        )

        return df[df["month"] == selected_month].reset_index(drop=True)

    if profile == "winter_month":
        selected_month = int(
            monthly.sort_values(
                ["temperature_mean_C", "irradiance_sum_Wh_m2"],
                ascending=[True, True],
            ).iloc[0]["month"]
        )

        return df[df["month"] == selected_month].reset_index(drop=True)

    # Durchschnittstag:
    # Tag, dessen Tagesmitteltemperatur dem Jahresmittel am nächsten liegt.
    annual_mean = float(df["temperature_C"].mean())
    daily["distance_to_annual_mean"] = (
        daily["temperature_mean_C"] - annual_mean
    ).abs()

    selected_date = daily.sort_values(
        ["distance_to_annual_mean", "irradiance_sum_Wh_m2"],
        ascending=[True, False],
    ).iloc[0]["date"]

    return df[df["date"] == selected_date].reset_index(drop=True)

# Ergänzt Wetterreihen um Zeit- und Strahlungswerte für die PFC.
def weather_store_to_dataframe(weather_data: dict | None) -> pd.DataFrame | None:
    if not weather_data:
        return None

    temperature = weather_data.get("temperature_C")
    irradiance = weather_data.get("irradiance_W_m2")
    datetime_values = weather_data.get("datetime")

    if temperature is None:
        temperature = weather_data.get("temperature")

    if irradiance is None:
        irradiance = weather_data.get("global_irradiance_W_m2")

    if temperature is None:
        return None

    n = len(temperature)

    if irradiance is None:
        irradiance = [0.0] * n

    if datetime_values is not None:
        dt_index = pd.to_datetime(datetime_values, errors="coerce")

        if pd.isna(dt_index).any():
            dt_index = pd.date_range("2015-01-01 00:00", periods=n, freq="h")
    else:
        dt_index = pd.date_range("2015-01-01 00:00", periods=n, freq="h")

    df = pd.DataFrame(
        {
            "datetime": dt_index,
            "temperature_C": np.asarray(temperature, dtype=float),
            "irradiance_W_m2": np.asarray(irradiance, dtype=float),
        }
    )

    df["irradiance_W_m2"] = df["irradiance_W_m2"].fillna(0.0).clip(lower=0.0)

    df["date"] = df["datetime"].dt.date
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour
    df["day_of_year"] = df["datetime"].dt.dayofyear

    pv_peak_kw = 76.0
    df["pv_dc_kw"] = pv_peak_kw * (df["irradiance_W_m2"] / 1000.0).clip(lower=0.0, upper=1.15)

    return df

# Wählt aus gespeicherten Wetterdaten das angeforderte Profil.
def build_profile_weather_data(
    weather_data: dict | None,
    profile: str,
) -> pd.DataFrame | None:
    df = weather_store_to_dataframe(weather_data)

    if df is None or df.empty:
        return None

    selected = select_profile_dataframe(df, profile)

    if selected.empty:
        return None

    return selected.reset_index(drop=True)

# Liest stündliche Bedarfsreihen aus dem Ergebnis-Store.
def demand_store_to_dataframe(demand_data: dict | None) -> pd.DataFrame | None:
    if not demand_data:
        return None

    hourly = demand_data.get("hourly")

    if not hourly:
        return None

    df = pd.DataFrame(hourly)

    if df.empty:
        return None

    return df

# Bestimmt die Schrittweite eines Tages- oder Monatsprofils.
def profile_tick_step(profile: str) -> int:
    if profile in {"summer_month", "winter_month"}:
        return 24

    return 1

