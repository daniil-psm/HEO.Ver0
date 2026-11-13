# Liest und berechnet Gebäude- sowie Wärmenetzkennwerte aus DG-Ergebnissen.

from __future__ import annotations

from functools import lru_cache
import json
import math
import pickle
from pathlib import Path
import re
from typing import Any

from .result_flows import _cluster_schedule, _sort_key
from ..input.config_service import DG_ROOT, DG_SCENARIOS_DIR
from ..shared.dg_paths import seed_control_dir

MANIFEST_FILENAME = "manifest.json"
PREPARED_SCENARIO_FILENAME = "prepared_scenario.p"

_GRID_IMPORT = re.compile(
    r"^(heat_dom|cool_dom)\[\(['\"]heat_grid['\"],\s*(\d+),\s*(\d+)\)\]\s+(\S+)"
)

# Liest einen endlichen Zahlenwert aus DG-Netzdaten.
def _finite_number(data: dict, key: str) -> float | None:
    value = data.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# Berechnet belegte Leitungs- und Investitionswerte des Netzes.
def network_design_from_grid(grid: dict[str, Any] | None) -> dict[str, Any]:
    """Liefert nur belegte Netzwerte eines DG-Laufs, ohne Schätzwerte."""

    if not isinstance(grid, dict):
        return {}
    distribution_length = _finite_number(grid, "length_dist")
    service_length = _finite_number(grid, "length_serv")
    heat_distribution_dn = _finite_number(grid, "DN_heating_dist")
    heat_service_dn = _finite_number(grid, "DN_heating_serv")
    total = _finite_number(grid, "costs")
    if any(value is None for value in (
        distribution_length, service_length, heat_distribution_dn,
        heat_service_dn, total,
    )):
        return {}
    if min(distribution_length, service_length, heat_distribution_dn, heat_service_dn, total) < 0:
        return {}

    # Berechnet Leitungswerte und Investition für einen Energieträger.
    def network(distribution_dn: float, service_dn: float) -> dict[str, float]:
        investment = (
            (323.579 + 4.267 * distribution_dn) * distribution_length
            + (323.579 + 4.267 * service_dn) * service_length
        )
        return {
            "distribution_length_m": distribution_length,
            "distribution_dn": distribution_dn,
            "service_length_m": service_length,
            "service_dn": service_dn,
            "investment_eur": investment,
        }

    heating = network(heat_distribution_dn, heat_service_dn)
    cooling_distribution_dn = _finite_number(grid, "DN_cooling_dist")
    cooling_service_dn = _finite_number(grid, "DN_cooling_serv")
    cooling = (
        network(cooling_distribution_dn, cooling_service_dn)
        if cooling_distribution_dn is not None and cooling_distribution_dn > 0
        and cooling_service_dn is not None and cooling_service_dn > 0
        else None
    )
    substations = total - heating["investment_eur"] - (
        cooling["investment_eur"] if cooling else 0.0
    )
    if (
        min(heating["investment_eur"], cooling["investment_eur"] if cooling else 0.0, substations) < -0.01
    ):
        return {}
    return {
        "heating": heating,
        **({"cooling": cooling} if cooling else {}),
        "substations_investment_eur": max(0.0, substations),
        "total_investment_eur": total,
    }


# Aggregiert thermische Netzbezüge aus Lösungsdateien.
@lru_cache(maxsize=16)
def _read_thermal_imports(
    result_dir: str,
    schedule: tuple[tuple[str, str, int], ...],
    time_resolution_seconds: float,
    expected_steps: int,
    run_id: str,
) -> dict[str, dict[str, dict[str, float]]]:
    del run_id  # Bestandteil des Cache-Schlüssels für neu berechnete Läufe.
    totals: dict[tuple[str, str], list[float]] = {}
    for year, cluster, weight in schedule:
        path = Path(result_dir) / (
            f"solution_file_opti_central_model_year_{year}_cluster_{cluster}.txt"
        )
        if not path.is_file():
            return {}
        per_cluster: dict[tuple[str, str], dict[int, float]] = {}
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = _GRID_IMPORT.match(line)
                if match is None:
                    continue
                try:
                    power_w = max(0.0, float(match.group(4)))
                except ValueError:
                    continue
                if not math.isfinite(power_w):
                    continue
                time_step = int(match.group(3))
                if not 0 <= time_step < expected_steps:
                    continue
                carrier = "heat" if match.group(1) == "heat_dom" else "cool"
                key = (match.group(2), carrier)
                per_cluster.setdefault(key, {})[time_step] = power_w
        for key, series in per_cluster.items():
            if len(series) != expected_steps:
                continue
            values = totals.setdefault(key, [0.0, 0.0, 0.0])
            values[0] = max(values[0], max(series.values()))
            values[1] += sum(series.values()) * weight
            values[2] += 1

    result: dict[str, dict[str, dict[str, float]]] = {}
    for (building, carrier), (peak_w, weighted_sum_w, seen_clusters) in totals.items():
        if seen_clusters != len(schedule):
            continue
        result.setdefault(building, {})[carrier] = {
            "peak_kw": peak_w / 1000.0,
            "annual_mwh": weighted_sum_w * time_resolution_seconds / 3600.0 / 1_000_000.0,
        }
    return result


# Liefert Wärme- und Kältebezüge je Gebäude und Jahr.
def building_thermal_imports_from_solutions(
    solution_dir: Path, bundle: dict[str, Any],
) -> dict[str, dict[str, dict[str, float]]]:
    """Aggregiert exakte Netzbezüge je Gebäude über die Cluster des ersten Jahres."""

    schedule = _cluster_schedule(bundle)
    time = bundle.get("time") or {}
    try:
        step_seconds = float(time["timeResolution"])
        cluster_seconds = float(time["clusterLength"])
    except (KeyError, TypeError, ValueError):
        return {}
    if not schedule or step_seconds <= 0 or cluster_seconds <= 0:
        return {}
    steps = cluster_seconds / step_seconds
    if not steps.is_integer():
        return {}
    return _read_thermal_imports(
        str(Path(solution_dir).resolve()), schedule, step_seconds, int(steps),
        str(bundle.get("comparison_run_id") or ""),
    )


# Liest lokale DG-Vorbereitungen, wenn älteren Bundles die Netzauslegung fehlt.
def _load_prepared_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


# Rekonstruiert die Netzauslegung für ältere Ergebnisbundles.
@lru_cache(maxsize=8)
def _legacy_network_design(
    scenario_name: str, profile_hash: str, generation_id: str, *,
    _scenarios_root: Path = DG_SCENARIOS_DIR,
    _dg_root: Path = DG_ROOT,
    _pickle_loader=None,
) -> dict[str, Any]:
    """Liest die Netzauslegung älterer Bundles aus der zugehörigen DG-Vorbereitung."""

    seed_dir = seed_control_dir(_scenarios_root / scenario_name)
    manifest_path = seed_dir / MANIFEST_FILENAME
    prepared_path = seed_dir / PREPARED_SCENARIO_FILENAME
    if not manifest_path.is_file() or not prepared_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("status") != "ready"
            or manifest.get("profile_hash") != profile_hash
            or manifest.get("generation_id") != generation_id
        ):
            return {}
        import sys

        if str(_dg_root) not in sys.path:
            sys.path.insert(0, str(_dg_root))
        prepared = (_pickle_loader or _load_prepared_pickle)(prepared_path)
        return network_design_from_grid(getattr(prepared.data, "heat_grid_data", None))
    except (OSError, ValueError, AttributeError, KeyError, TypeError, ImportError, pickle.UnpicklingError):
        return {}
