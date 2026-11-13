# Liest und validiert DG-Ergebnisbundles, Varianten und Ergebnisinventare.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..input.config_service import (
    DGConfigError,
    DG_ROOT,
    DG_SCENARIOS_DIR,
    load_dg_config_state,
    scenario_config_path,
)
from ..shared.scenario_names import validate_scenario_name
from ..input.scenario_service import load_building_scenario
from ..shared.comparison_contract import (
    COMPARISON_SCHEMA_VERSION, DEFAULT_OBJECTIVES, DGComparisonError,
    MANIFEST_FILENAME, OBJECTIVE_FOCUS,
)
from ..shared.dg_paths import dg_profiles_dir, dg_results_dir, objective_dir, results_dir
from . import DGResultError, DGResultMissingError
from .demand_profiles import load_demand_results
from ..execution.dg_project_snapshot import build_topology_snapshot
from .component_results import building_thermal_imports_from_solutions, _legacy_network_design
from .kpi_results import _legacy_investment_context, _legacy_total_investment
from .results_writer import (
    OPTIMIZATION_BUNDLE_FILENAME,
    _optimized_capacities,
)

# Liefert den Ergebnisordner eines Szenarios.
def scenario_results_path(scenario_name: Any) -> Path:
    return results_dir(DG_SCENARIOS_DIR / validate_scenario_name(scenario_name))


# Prüft eine Variante und liefert ihren DG-Ergebnisordner.
def comparison_variant_results_path(scenario_name: Any, objective: Any) -> Path:
    name = validate_scenario_name(scenario_name)
    normalized = str(objective or "").strip().lower()
    if normalized not in DEFAULT_OBJECTIVES:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective!r}")
    try:
        manifest = _read_objective_manifest(name, normalized, _scenarios_root=DG_SCENARIOS_DIR)
    except DGComparisonError as exc:
        raise DGResultMissingError(str(exc)) from exc
    # The strict preparation hash describes cache reuse, not readability of
    # results produced by an earlier software version or on another machine.
    return dg_results_dir(DG_SCENARIOS_DIR / name, normalized)


# Rekonstruiert bei älteren Bundles die Gebäudezuordnung.
def _scenario_topology_snapshot(scenario_name: Any) -> dict[str, Any]:
    try:
        buildings = load_building_scenario(scenario_name)
    except (OSError, TypeError, ValueError) as exc:
        raise DGResultError(
            "Die Gebäudezuordnung der Optimierungsergebnisse konnte nicht "
            "geladen werden."
        ) from exc
    return build_topology_snapshot(buildings)


# Ergänzt eine fehlende Gebäudezuordnung im Ergebnisbundle.
def _attach_topology_snapshot(
    optimization: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(optimization.get("topology_snapshot"), dict):
        return optimization
    return {**optimization, "topology_snapshot": snapshot}


# Lädt eine geprüfte Optimierungsvariante samt fehlenden Altdaten.
def load_optimization_results(
    scenario_name: Any,
    objective: Any | None = None,
) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    selected = str(objective).strip().lower() if objective is not None else (
        "economic" if (objective_dir(DG_SCENARIOS_DIR / name, "economic") / "manifest.json").is_file()
        else "ecological"
    )
    if selected not in DEFAULT_OBJECTIVES:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective!r}")
    result_root = comparison_variant_results_path(name, selected)
    try:
        payload = load_comparison_optimization(name, selected, _scenarios_root=DG_SCENARIOS_DIR)
    except DGComparisonError as exc:
        raise DGResultMissingError(str(exc)) from exc
    if not payload.get("capacities", {}).get("devices"):
        payload["capacities"] = _optimized_capacities(result_root)
    saved_buildings = ((payload.get("project_snapshot") or {}).get("buildings"))
    snapshot = (build_topology_snapshot(saved_buildings) if saved_buildings
                else _scenario_topology_snapshot(name))
    return _attach_topology_snapshot(payload, snapshot)


# Lädt zusammengehörige Varianten, Profile und Projektstand.
def load_complete_comparison_results(
    scenario_name: Any,
    *,
    objectives: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    selected = objectives or DEFAULT_OBJECTIVES
    if not selected or len(set(selected)) != len(selected) or any(
        item not in DEFAULT_OBJECTIVES for item in selected
    ):
        raise ValueError("Ungültiger Optimierungsfokus.")
    try:
        manifest = load_comparison_manifest(
            name, require_complete=objectives is None, _scenarios_root=DG_SCENARIOS_DIR,
        )
    except DGComparisonError as exc:
        raise DGResultMissingError(str(exc)) from exc
    if len(selected) > 1 and not manifest["comparison_complete"]:
        raise DGResultMissingError("Die gespeicherten Optimierungen gehören nicht zum selben Vergleichslauf.")
    variants = {}
    for selected_objective in selected:
        comparison_variant_results_path(name, selected_objective)
        variants[selected_objective] = load_optimization_results(name, selected_objective)
        if variants[selected_objective].get("profile_hash") != manifest["variants"][selected_objective].get("profile_hash"):
            raise DGResultError("Optimierungsbundle und Ergebnismannifest gehören nicht zusammen.")
    primary = "economic" if "economic" in variants else "ecological"
    project_snapshot = variants[primary].get("project_snapshot")
    if not project_snapshot:
        try:
            _, config_state = load_dg_config_state(scenario_config_path(name))
            project_snapshot = {
                "schema_version": 1,
                "source": "verified_legacy",
                "config": config_state,
                "buildings": load_building_scenario(name),
                "weather": {"filename": str(config_state["values"].get("WEATHER_FILE") or "")},
            }
        except (DGConfigError, OSError, ValueError):
            project_snapshot = None
    saved_buildings = ((project_snapshot or {}).get("buildings") or {}).get("rows")
    demands = load_demand_results(
        name, validate_timestamps=False, building_rows=saved_buildings,
    )
    selected_manifest = {
        **manifest,
        "requested_objectives": list(selected),
        "variants": {objective: manifest["variants"][objective] for objective in selected},
        "comparison_complete": len(selected) == len(DEFAULT_OBJECTIVES) and manifest["comparison_complete"],
        "run_id": manifest["variants"][primary].get("run_id"),
    }
    comparison = {
        "status": "ready",
        "scenario_name": name,
        "profile_hash": manifest.get("profile_hash"),
        "manifest": selected_manifest,
        "project_snapshot": project_snapshot,
        "variants": variants,
    }
    return {
        "scenario_name": name,
        "run_id": selected_manifest.get("run_id"),
        "profile_hash": manifest.get("profile_hash"),
        "demands": demands,
        "optimization": variants[primary],
        "comparison": comparison,
        "inventory": manifest,
    }


# Wählt die zusammengehörigen gespeicherten Varianten eines Szenarios.
def load_complete_scenario_results(
    scenario_name: Any,
    *,
    objectives: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    if objectives is not None:
        return load_complete_comparison_results(name, objectives=objectives)
    available = []
    for objective in DEFAULT_OBJECTIVES:
        try:
            comparison_variant_results_path(name, objective)
        except DGResultError:
            continue
        available.append(objective)
    if not available:
        raise DGResultMissingError("Für dieses Szenario sind keine aktuellen Optimierungsergebnisse vorhanden.")
    grouped = load_comparison_manifest(name, _scenarios_root=DG_SCENARIOS_DIR)
    if len(available) > 1 and grouped["comparison_complete"]:
        try:
            return load_complete_comparison_results(name, objectives=tuple(available))
        except DGResultError:
            pass
    for objective in sorted(
        available,
        key=lambda item: grouped["variants"][item].get("completed_at") or "",
        reverse=True,
    ):
        try:
            return load_complete_comparison_results(name, objectives=(objective,))
        except DGResultError:
            continue
    raise DGResultMissingError("Keines der gespeicherten Optimierungsergebnisse ist vollständig lesbar.")


# Listet die vorhandenen Ergebnisdateien eines Szenarios.
def result_inventory(scenario_name: Any) -> dict[str, list[str]]:
    name = validate_scenario_name(scenario_name)
    scenario_dir = DG_SCENARIOS_DIR / name
    root = scenario_results_path(name)
    profiles = dg_profiles_dir(scenario_dir)
    # Listet passende Dateien relativ zum Szenarioordner.
    def files(base: Path, pattern: str) -> list[str]:
        return sorted(str(path.relative_to(scenario_dir)) for path in base.glob(pattern) if path.is_file())
    dg_roots = [dg_results_dir(scenario_dir, objective) for objective in DEFAULT_OBJECTIVES]
    # Fasst die Dateien beider Optimierungsvarianten zusammen.
    def dg_files(pattern: str) -> list[str]:
        return sorted(path for folder in dg_roots for path in files(folder, pattern))
    return {
        "demands": files(profiles, "demands/*.csv"),
        "generation": files(profiles, "generation/*.csv") + dg_files("generation/*.csv"),
        "optimization_models": dg_files("optimization_results/*.lp"),
        "optimization_solutions": dg_files("optimization_results/solution_file_*.txt"),
        "optimization_data": dg_files(f"optimization_results/{OPTIMIZATION_BUNDLE_FILENAME}"),
        "optimization_diagnostics": dg_files("optimization_results/errorfile_*.txt") + dg_files("optimization_results/iis_*.ilp"),
        "kpis": dg_files("KPIs_*"),
        "certificates": dg_files("Quartiersenergieausweis_*.pdf"),
        "plots": dg_files("plots/*"),
        "state": files(root, "progress.json"),
    }


# Prüft die zum Optimierungsziel gehörenden Manifeste und Ergebnisbundles.
def _read_objective_manifest(scenario_name: Any, objective: str, *, _scenarios_root=None) -> dict[str, Any]:
    root = _scenarios_root if _scenarios_root is not None else DG_SCENARIOS_DIR
    name = validate_scenario_name(scenario_name)
    if objective not in OBJECTIVE_FOCUS:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective!r}")
    path = objective_dir(root / name, objective) / MANIFEST_FILENAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DGComparisonError(f"Ergebnismannifest fehlt oder ist ungültig: {path}") from exc
    if (manifest.get("schema_version") != COMPARISON_SCHEMA_VERSION
            or manifest.get("status") != "completed"
            or manifest.get("scenario_name") != name
            or manifest.get("objective") != objective):
        raise DGComparisonError(f"Ergebnismannifest ist unvollständig: {path}")
    bundle = dg_results_dir(root / name, objective) / "optimization_results" / OPTIMIZATION_BUNDLE_FILENAME
    if not bundle.is_file():
        raise DGComparisonError(f"Optimierungsbundle fehlt: {bundle}")
    return manifest

# Fasst aktuelle Variantenmanifeste zu einem Vergleich zusammen.
def load_comparison_manifest(
    scenario_name: Any,
    *,
    run_id: str | None = None,
    require_complete: bool = False,
    _scenarios_root=None,
) -> dict[str, Any]:
    """Assemble current focus manifests; historical run IDs are not retained."""

    name = validate_scenario_name(scenario_name)
    variants = {}
    for objective in DEFAULT_OBJECTIVES:
        try:
            variant = _read_objective_manifest(name, objective, _scenarios_root=_scenarios_root)
        except DGComparisonError:
            continue
        if run_id is None or variant.get("run_id") == run_id:
            variants[objective] = variant
    if not variants:
        raise DGComparisonError(f"Für {name!r} sind keine abgeschlossenen Optimierungen vorhanden.")
    hashes = {variant.get("profile_hash") for variant in variants.values()}
    generation_ids = {variant.get("common_generation_id") for variant in variants.values()}
    contexts = {(item.get("calculation_context") or {}).get("input_sha256") for item in variants.values()}
    software = {(item.get("calculation_context") or {}).get("software_sha256") for item in variants.values()}
    complete = (len(variants) == len(DEFAULT_OBJECTIVES) and len(hashes) == 1
                and len(generation_ids) == 1 and len(contexts) == 1
                and None not in contexts and len(software) == 1 and None not in software)
    if require_complete and not complete:
        raise DGComparisonError("Für den Vergleich fehlen zwei abgeschlossene Fokusse mit identischen gemeinsamen Eingaben.")
    latest = max(variants.values(), key=lambda item: str(item.get("completed_at") or ""))
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "status": "completed",
        "comparison_complete": complete,
        "run_id": latest.get("run_id"),
        "scenario_name": name,
        "requested_objectives": list(variants),
        "profile_hash": next(iter(hashes)) if len(hashes) == 1 else None,
        "variants": variants,
    }

# Lädt ein Variantebundle und ergänzt ältere Ergebnisformate.
def load_comparison_optimization(
    scenario_name: Any,
    objective: str,
    *,
    run_id: str | None = None,
    _scenarios_root=None,
) -> dict[str, Any]:
    """Load the single current bundle for an objective."""

    root = _scenarios_root if _scenarios_root is not None else DG_SCENARIOS_DIR
    name = validate_scenario_name(scenario_name)
    normalized = str(objective).strip().lower()
    variant = _read_objective_manifest(name, normalized, _scenarios_root=_scenarios_root)
    if run_id is not None and variant.get("run_id") != run_id:
        raise DGComparisonError(f"Der Lauf {run_id!r} ist für {normalized!r} nicht mehr aktuell.")
    bundle = dg_results_dir(root / name, normalized) / "optimization_results" / OPTIMIZATION_BUNDLE_FILENAME
    try:
        payload = json.loads(bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DGComparisonError(f"Optimierungsbundle konnte nicht gelesen werden: {bundle}") from exc
    if payload.get("schema_version") != 1 or "results" not in payload:
        raise DGComparisonError(f"Unbekanntes Optimierungsbundle: {bundle}")
    if (payload.get("profile_hash") != variant.get("profile_hash")
            or payload.get("scenario_name", name) != name
            or payload.get("objective", normalized) != normalized):
        raise DGComparisonError("Optimierungsbundle und Ergebnismannifest gehören nicht zusammen.")
    if (variant.get("calculation_context") is not None
            and payload.get("calculation_context") != variant["calculation_context"]):
        raise DGComparisonError("Optimierungsbundle und Berechnungsstand gehören nicht zusammen.")
    from .kpi_results import (
        central_device_investment_from_solution,
        read_dg_kpi_report,
    )

    result_dir = bundle.parent.parent
    if not isinstance(payload.get("network_design"), dict):
        payload["network_design"] = _legacy_network_design(
            name,
            str(payload.get("profile_hash") or ""),
            str(variant.get("common_generation_id") or ""),
            _scenarios_root=root,
            _dg_root=DG_ROOT,
        )
    if not isinstance(payload.get("building_thermal_imports"), dict):
        payload["building_thermal_imports"] = building_thermal_imports_from_solutions(
            bundle.parent, payload
        )
    payload["kpi_report"] = read_dg_kpi_report(result_dir / f"KPIs_{name}.xlsx")
    summary = payload.get("summary")
    if isinstance(summary, dict) and summary.get("investment_cost_eur") is None:
        # Older bundles did not save total CAPEX. EHDO still records the central
        # equipment investment, but not the heat grid or building investments.
        partial = central_device_investment_from_solution(
            bundle.parent / "solution_file_ehdo_model.txt"
        )
        if partial is not None:
            summary["investment_cost_central_devices_eur"] = partial
        equipment_investment = (
            0.0 if partial is None and not payload["kpi_report"].get("Central Devices") else partial
        )
        if equipment_investment is not None:
            reconstructed = _legacy_total_investment(
                name, str(payload.get("profile_hash")), payload["kpi_report"], equipment_investment,
                _context_loader=lambda scenario, profile_hash: _legacy_investment_context(
                    scenario, profile_hash, _scenarios_root=root, _dg_root=DG_ROOT,
                ),
            )
            if reconstructed is not None:
                summary["investment_cost_eur"] = reconstructed
    return payload
