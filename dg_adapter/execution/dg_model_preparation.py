"""Orchestrate the June DG through its existing methods, without patching it.

This is the call order of generateDistrictComplete at commit df4c03d, split
before central sizing so each objective gets its own design. All physical
calculations remain in the DG. Recheck this sequence when updating the DG.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PreparedDistrict:
    """Adapter-owned cache envelope; the DG object needs no staging attributes."""

    data: Any
    requires_central_design: bool


def prepare_district(data, *, calcUserProfiles=True, saveUserProfiles=True,
                     gen_cars=True, designEnergyhub=False, profile_options=None) -> PreparedDistrict:
    """Run the common part, stopping before objective-dependent central sizing."""
    from districtgenerator.functions import heating_network_simple

    data.generateEnvironment()
    data.initializeBuildings()
    data.generateBuildings()
    if profile_options is None:
        data.generateDemands(calcUserProfiles, saveUserProfiles, gen_cars=gen_cars)
    else:
        from ..execution.profile_service import generate_demands
        generate_demands(data, profile_options, gen_cars=gen_cars)
    data.designDecentralDevices(saveGenerationProfiles=True)

    # Check if district uses central energy supply (heat grid)
    has_heat_grid = any(
        building["buildingFeatures"]["heater"] == "heat_grid"
        for building in data.district)
    requires_central_design = bool(
        has_heat_grid or designEnergyhub
    )

    if requires_central_design:
        # Verify geometry data (district_parameters)

        # --- Check if building positions are available and valid ---
        missing_positions = (
                "position" not in data.scenario.columns
                or data.scenario["position"].isnull().any()
                or any(
            not isinstance(p, tuple) or len(p) != 2 or not all(isinstance(x, (int, float)) for x in p)
            for p in data.scenario["position"]))

        if has_heat_grid:
            if missing_positions:
                print("No district geometry found — running simple heating network design.")
                heating_network_simple.heating_network(data)
            else:
                print("Generating and optimizing heating network...")
                data.generateNetwork(topology_option="node")
                data.prepareClusteringInputs()
                data.optimization_heatingnetwork()

        else:
            ts_length = len(data.district[0]["user"].heat)
            data.heat_grid_data["total_losses_heating_network"] = np.zeros(ts_length)
            data.heat_grid_data["total_losses_cooling_network"] = np.zeros(ts_length)
            data.heat_grid_data["pump_power"] = np.zeros(ts_length)
            data.heat_grid_data["ann_costs"] = 0
            data.heat_grid_data["om_costs"] = 0
    else:
        print("No central heat grid detected and no energy hub designed — skipping heating network design.")
        data.centralDevices = {}
        data.prepareClusteringInputs()

    return PreparedDistrict(data, requires_central_design)


def finalize_district(prepared: PreparedDistrict) -> None:
    """Size central devices for this variant's already selected objective."""
    if not isinstance(prepared, PreparedDistrict):
        raise TypeError("Expected a district prepared by the DG adapter.")
    if prepared.requires_central_design:
        prepared.data.designCentralDevices(saveGenerationProfiles=True)
        prepared.data.finalizeClusterProfiles()
