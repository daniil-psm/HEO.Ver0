# Erzeugt Momentaufnahmen der Energieflüsse aus DG-Ergebnissen oder Vorschauprofilen.

from __future__ import annotations

import numpy as np

from heo.topology.pfc_model import FlowSnapshot, clamp
from .pfc_profiles import (
    get_optimization_snapshot, build_profile_weather_data,
    demand_store_to_dataframe, profile_tick_step,
)

# Baut eine Flussmomentaufnahme aus optimierten DG-Leistungswerten.
def flow_snapshot_from_optimization(snapshot: dict) -> FlowSnapshot:
    grid_import = float(snapshot.get("grid_import_kw", 0.0))
    grid_export = float(snapshot.get("grid_export_kw", 0.0))

    ac_to_dc = float(snapshot.get("ac_to_dc_kw", 0.0))
    dc_to_ac = float(snapshot.get("dc_to_ac_kw", 0.0))

    battery_charge = float(snapshot.get("battery_charge_kw", 0.0))
    battery_discharge = float(snapshot.get("battery_discharge_kw", 0.0))

    thermal_charge = float(snapshot.get("thermal_charge_kw", 0.0))
    thermal_discharge = float(snapshot.get("thermal_discharge_kw", 0.0))

    hp_el_heat = float(snapshot.get("hp_el_heat_kw", 0.0))
    hp_el_cool = float(snapshot.get("hp_el_cool_kw", 0.0))

    hp_heat = float(snapshot.get("hp_heat_kw", 0.0))
    hp_cooling = float(snapshot.get("hp_cooling_kw", 0.0))

    eta_ac_to_dc = 0.97
    eta_dc_to_ac = 0.97

    return FlowSnapshot(
        hour=int(snapshot.get("t", 0)) % 24,

        # Import Richtung: Stromnetz → AC-Bus
        grid_ac=round(grid_import, 1),

        # Export Richtung: AC-Bus → Stromnetz
        ac_bus_to_grid=round(grid_export, 1),

        pv_dc=round(float(snapshot.get("pv_used_kw", 0.0)), 1),

        # AC → DC
        ac_bus_to_converter=round(ac_to_dc, 1),
        converter_to_dc_bus=round(ac_to_dc * eta_ac_to_dc, 1),

        # DC → AC
        dc_bus_to_converter=round(dc_to_ac / eta_dc_to_ac if dc_to_ac > 0 else 0.0, 1),
        converter_to_ac_bus=round(dc_to_ac, 1),

        dc_bus_to_bess=round(battery_charge, 1),
        bess_to_dc_bus=round(battery_discharge, 1),
        bess_soc=round(float(snapshot.get("battery_soc_kwh", 0.0)), 1),

        ac_load=round(float(snapshot.get("ac_load_kw", 0.0)), 1),
        dc_load=round(float(snapshot.get("dc_load_kw", 0.0)), 1),
        heat_load=round(float(snapshot.get("heat_load_kw", 0.0)), 1),
        cooling_load=round(float(snapshot.get("cooling_load_kw", 0.0)), 1),

        # Falls die WP AC-seitig modelliert wird, ist das für die PFC nur ein Verbraucher.
        # Falls deine Grafik noch DC-Bus → WP zeigt, kannst du hier vorerst den el. WP-Bedarf anzeigen.
        dc_bus_to_heatpump=round(hp_el_heat + hp_el_cool, 1),

        heatpump_to_heat_load=round(hp_heat, 1),
        heatpump_to_cooling_load=round(hp_cooling, 1),
        heatpump_to_thermal_storage=round(thermal_charge, 1),

        thermal_storage_to_heat_load=round(thermal_discharge, 1),
        thermal_storage_soc=round(float(snapshot.get("thermal_soc_kwh", 0.0)), 1),
    )

# Wählt DG-Ergebnisse oder Wetter- und Bedarfsprofile für den aktuellen Zeitschritt.
def flow_snapshot(
    tick: int,
    profile: str,
    weather_data: dict | None = None,
    demand_data: dict | None = None,
    optimization_data: dict | None = None,
) -> FlowSnapshot:
    optimized = get_optimization_snapshot(
        optimization_data=optimization_data,
        tick=tick,
    )

    if optimized is not None:
        return flow_snapshot_from_optimization(optimized)

    selected_weather = build_profile_weather_data(
        weather_data=weather_data,
        profile=profile,
    )

    demand_df = demand_store_to_dataframe(demand_data)

    if selected_weather is None or selected_weather.empty:
        return flow_snapshot_fallback(tick, profile)

    if demand_df is None or demand_df.empty:
        return flow_snapshot_fallback(tick, profile)

    step_size = profile_tick_step(profile)
    weather_row_index = (int(tick or 0) * step_size) % len(selected_weather)

    weather_row = selected_weather.iloc[weather_row_index]

    selected_day_index = int(weather_row["day_of_year"])
    selected_hour = int(weather_row["hour"])

    demand_match = demand_df[
        (demand_df["day_of_year"].astype(int) == selected_day_index)
        & (demand_df["hour"].astype(int) == selected_hour)
    ]

    if demand_match.empty:
        demand_row = demand_df.iloc[weather_row_index % len(demand_df)]
    else:
        demand_row = demand_match.iloc[0]

    hour = int(weather_row["hour"])

    pv_dc = float(weather_row["pv_dc_kw"])

    ac_load = float(demand_row.get("ac_load_kw", 0.0))
    dc_load = float(demand_row.get("dc_load_kw", 0.0))
    heat_load = float(demand_row.get("heat_load_kw", 0.0))
    cooling_load = float(demand_row.get("cooling_load_kw", 0.0))

    cop_heat = 3.2
    eer_cooling = 3.0

    thermal_storage_to_heat_load = 0.22 * heat_load
    heatpump_to_heat_load = max(0.0, heat_load - thermal_storage_to_heat_load)
    heatpump_to_cooling_load = cooling_load
    heatpump_to_thermal_storage = 0.16 * heat_load

    dc_bus_to_heatpump = (
        heatpump_to_heat_load / cop_heat
        + heatpump_to_cooling_load / eer_cooling
        + heatpump_to_thermal_storage / cop_heat
    )

    dc_demand = dc_load + dc_bus_to_heatpump
    dc_surplus = max(0.0, pv_dc - dc_demand)
    dc_deficit = max(0.0, dc_demand - pv_dc)

    dc_bus_to_bess = min(20.0, dc_surplus)
    bess_to_dc_bus = 0.0 if dc_bus_to_bess > 0.05 else min(16.0, dc_deficit * 0.55)

    converter_to_dc_bus = max(0.0, dc_deficit - bess_to_dc_bus)
    ac_bus_to_converter = converter_to_dc_bus / 0.94 if converter_to_dc_bus > 0 else 0.0

    grid_ac = ac_load + ac_bus_to_converter

    bess_soc = 55.0 + 28.0 * np.sin((weather_row_index / max(1, len(selected_weather))) * 2 * np.pi)
    thermal_storage_soc = 52.0 + 20.0 * np.sin((weather_row_index / max(1, len(selected_weather))) * 2 * np.pi + 0.8)

    return FlowSnapshot(
        hour=hour,

        grid_ac=round(grid_ac, 1),
        ac_bus_to_grid=0.0,
        pv_dc=round(pv_dc, 1),

        ac_bus_to_converter=round(ac_bus_to_converter, 1),
        converter_to_dc_bus=round(converter_to_dc_bus, 1),

        dc_bus_to_converter=0.0,
        converter_to_ac_bus=0.0,

        dc_bus_to_bess=round(dc_bus_to_bess, 1),
        bess_to_dc_bus=round(bess_to_dc_bus, 1),
        bess_soc=round(clamp(bess_soc, 0, 100), 1),

        ac_load=round(ac_load, 1),
        dc_load=round(dc_load, 1),
        heat_load=round(heat_load, 1),
        cooling_load=round(cooling_load, 1),

        dc_bus_to_heatpump=round(dc_bus_to_heatpump, 1),
        heatpump_to_heat_load=round(heatpump_to_heat_load, 1),
        heatpump_to_cooling_load=round(heatpump_to_cooling_load, 1),
        heatpump_to_thermal_storage=round(heatpump_to_thermal_storage, 1),

        thermal_storage_to_heat_load=round(thermal_storage_to_heat_load, 1),
        thermal_storage_soc=round(clamp(thermal_storage_soc, 0, 100), 1),
    )

# Erzeugt die bisherige Vorschau-Momentaufnahme ohne Ergebnisdateien.
def flow_snapshot_fallback(tick: int, profile: str) -> FlowSnapshot:
    if profile in {"summer_day", "winter_day", "average_day"}:
        hour = int(tick or 0) % 24
    else:
        hour = int(tick or 0) % 24

    # To-Do: Solarpotenzial aus try
    if profile == "summer_day":
        solar_factor = 1.15
        heat_factor = 0.55
        cooling_factor = 1.25
    elif profile == "winter_day":
        solar_factor = 0.35
        heat_factor = 1.35
        cooling_factor = 0.0
    elif profile == "summer_month":
        solar_factor = 1.05
        heat_factor = 0.65
        cooling_factor = 1.10
    elif profile == "winter_month":
        solar_factor = 0.45
        heat_factor = 1.25
        cooling_factor = 0.05
    else: # Durchschnittstag
        solar_factor = 0.75
        heat_factor = 1.00
        cooling_factor = 0.60

    solar_shape = max(0.0, np.sin((hour - 6) / 12 * np.pi))
    evening_shape = 0.5 + 0.5 * np.sin((hour - 16) / 24 * 2 * np.pi)

    ac_load = 22.0 + 8.0 * evening_shape
    dc_load = 7.0 + 4.0 * solar_shape

    heat_load = heat_factor * max(0.0, 26.0 + 10.0 * np.cos(hour / 24 * 2 * np.pi))
    cooling_load = cooling_factor * max(0.0, 18.0 * np.sin((hour - 9) / 12 * np.pi))

    pv_dc = 76.0 * solar_factor * solar_shape

    cop_heat = 3.2
    eer_cooling = 3.0

    thermal_storage_to_heat_load = 0.22 * heat_load
    heatpump_to_heat_load = max(0.0, heat_load - thermal_storage_to_heat_load)
    heatpump_to_cooling_load = cooling_load
    heatpump_to_thermal_storage = 0.16 * heat_load

    dc_bus_to_heatpump = (
        heatpump_to_heat_load / cop_heat
        + heatpump_to_cooling_load / eer_cooling
        + heatpump_to_thermal_storage / cop_heat
    )

    dc_demand = dc_load + dc_bus_to_heatpump
    dc_surplus = max(0.0, pv_dc - dc_demand)
    dc_deficit = max(0.0, dc_demand - pv_dc)

    dc_bus_to_bess = min(20.0, dc_surplus)
    bess_to_dc_bus = 0.0 if dc_bus_to_bess > 0.05 else min(16.0, dc_deficit * 0.55)

    converter_to_dc_bus = max(0.0, dc_deficit - bess_to_dc_bus)
    ac_bus_to_converter = converter_to_dc_bus / 0.94 if converter_to_dc_bus > 0 else 0.0

    grid_ac = ac_load + ac_bus_to_converter

    bess_soc = 55.0 + 28.0 * np.sin((hour - 4) / 24 * 2 * np.pi)
    thermal_storage_soc = 52.0 + 20.0 * np.sin((hour + 2) / 24 * 2 * np.pi)

    return FlowSnapshot(
        hour=hour,

        grid_ac=round(grid_ac, 1),
        ac_bus_to_grid=0.0,

        pv_dc=round(pv_dc, 1),

        ac_bus_to_converter=round(ac_bus_to_converter, 1),
        converter_to_dc_bus=round(converter_to_dc_bus, 1),

        dc_bus_to_converter=0.0,
        converter_to_ac_bus=0.0,

        dc_bus_to_bess=round(dc_bus_to_bess, 1),
        bess_to_dc_bus=round(bess_to_dc_bus, 1),
        bess_soc=round(clamp(bess_soc, 0, 100), 1),

        ac_load=round(ac_load, 1),
        dc_load=round(dc_load, 1),
        heat_load=round(heat_load, 1),
        cooling_load=round(cooling_load, 1),

        dc_bus_to_heatpump=round(dc_bus_to_heatpump, 1),
        heatpump_to_heat_load=round(heatpump_to_heat_load, 1),
        heatpump_to_cooling_load=round(heatpump_to_cooling_load, 1),
        heatpump_to_thermal_storage=round(heatpump_to_thermal_storage, 1),

        thermal_storage_to_heat_load=round(thermal_storage_to_heat_load, 1),
        thermal_storage_soc=round(clamp(thermal_storage_soc, 0, 100), 1),
    )

