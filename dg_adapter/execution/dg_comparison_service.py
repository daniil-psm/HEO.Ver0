# Durchführung der ökonomischen und ökologischen Vergleichsläufe


from __future__ import annotations

import json
import os
import pickle
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


from ..input.config_service import DG_ROOT, DG_SCENARIOS_DIR
from ..shared.scenario_names import validate_scenario_name
from ..output.results_writer import OPTIMIZATION_BUNDLE_FILENAME, save_optimization_results
from ..execution.profile_service import ensure_profile_options_file, load_profile_options, seeded_profiles
from .profile_fingerprint import PREPARED_SCENARIO_SCHEMA_VERSION, build_profile_fingerprint, without_objective
from .calculation_context import calculation_context, same_calculation
from ..shared.comparison_contract import (
    COMPARISON_SCHEMA_VERSION, DEFAULT_OBJECTIVES, DGComparisonError,
    MANIFEST_FILENAME, OBJECTIVE_FOCUS,
)
from .dg_model_preparation import PreparedDistrict, prepare_district, finalize_district
from ..output.kpi_results import (
    _mapping_average,
    _mapping_maximum,
    _mapping_values,
    _number,
    _variant_summary,
)
from ..shared.dg_paths import dg_input_dir, dg_profiles_dir, dg_results_dir, heo_results_dir, objective_dir, results_dir, seed_control_dir


PREPARED_SCENARIO_FILENAME = "prepared_scenario.p"
EFFECTIVE_CONFIG_FILENAME = "effective.env"

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

class DGComparisonRunError(DGComparisonError):
    """Mindestens eine Vergleichsvariante konnte nicht abgeschlossen werden."""

    def __init__(self, message: str, *, manifest_path: Path):
        super().__init__(message)
        self.manifest_path = manifest_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _progress_marker(*parts: Any, description: str | None = None) -> None:
    """Schreibt einen stabil parsebaren und zugleich lesbaren Fortschrittsmarker."""

    marker = " ".join(str(part) for part in parts)
    suffix = f" | {description}" if description else ""
    print(f"[HEO_COMPARISON] {marker}{suffix}", flush=True)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def _atomic_pickle(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def render_effective_config(base_config_text: str, objective: str) -> str:
    """Erzeugt einen vollständigen Config-Snapshot für genau eine Variante."""

    try:
        focus = OBJECTIVE_FOCUS[objective]
    except KeyError as exc:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective!r}") from exc
    base = without_objective(base_config_text)
    return (
        f"{base}\n"
        "# Vom HEO für diesen Vergleichslauf festgeschrieben.\n"
        f"OPTIMIZATION_FOCUS={focus}\n"
    )


def _validated_objectives(objectives: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(objective).strip().lower() for objective in objectives)
    if not normalized:
        raise ValueError("Mindestens ein Optimierungsziel ist erforderlich.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Optimierungsziele dürfen nicht doppelt vorkommen.")
    unknown = [objective for objective in normalized if objective not in OBJECTIVE_FOCUS]
    if unknown:
        raise ValueError("Unbekannte Optimierungsziele: " + ", ".join(unknown))
    return normalized


def _load_pickle(path: Path) -> Any:
    # Ausschließlich lokal vom HEO selbst erzeugte Cachedateien werden geladen.
    with path.open("rb") as handle:
        return pickle.load(handle)


def _common_cache_is_usable(
    common_dir: Path,
    *,
    scenario_name: str,
    profile_hash: str,
) -> bool:
    manifest_path = common_dir / "heo_seed_control" / MANIFEST_FILENAME
    prepared_path = common_dir / "heo_seed_control" / PREPARED_SCENARIO_FILENAME
    if not manifest_path.is_file() or not prepared_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        manifest.get("schema_version") == PREPARED_SCENARIO_SCHEMA_VERSION
        and manifest.get("status") == "ready"
        and manifest.get("scenario_name") == scenario_name
        and manifest.get("profile_hash") == profile_hash
        and (common_dir / "dg_profiles" / "demands").is_dir()
    )


def _prepare_common_scenario(
    *,
    scenario_name: str,
    scenario_dir: Path,
    config_path: Path,
    common_dir: Path,
    profile_hash: str,
    progress_path: Path | None,
    reuse_common: bool,
) -> tuple[Path, bool, int]:
    seed_dir = common_dir / "heo_seed_control"
    profiles_dir = common_dir / "dg_profiles"
    prepared_path = seed_dir / PREPARED_SCENARIO_FILENAME
    profile_options = load_profile_options(scenario_dir)
    profile_snapshot = profile_options.snapshot()
    random_seed = profile_options.seed

    if reuse_common and _common_cache_is_usable(
        common_dir,
        scenario_name=scenario_name,
        profile_hash=profile_hash,
    ):
        try:
            cached = _load_pickle(prepared_path)
            if (
                isinstance(cached, PreparedDistrict)
                and str(getattr(cached.data, "scenario_name", "")) == scenario_name
            ):
                data = cached.data
                expected = {
                    "scenario_file_path": str(dg_input_dir(scenario_dir)),
                    "env_path": config_path.resolve(),
                    "resultPath": str(profiles_dir),
                    "progress_file": str(progress_path) if progress_path is not None else str(seed_dir / "progress.json"),
                    "srcPath": str(DG_ROOT / "districtgenerator"),
                    "filePath": str(DG_ROOT / "districtgenerator" / "data"),
                    "pipe_file_path": str(DG_ROOT / "districtgenerator" / "data" / "pipe"),
                }
                changed = any(getattr(data, key, None) != value for key, value in expected.items())
                for key, value in expected.items():
                    setattr(data, key, value)
                if changed:
                    _atomic_pickle(prepared_path, cached)
                return prepared_path, True, random_seed
        except Exception:
            pass

    if reuse_common:
        for objective in DEFAULT_OBJECTIVES:
            variant_manifest = scenario_dir / "results" / objective / MANIFEST_FILENAME
            try:
                variant = json.loads(variant_manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if variant.get("status") == "completed" and variant.get("profile_hash") == profile_hash:
                raise DGComparisonError(
                    "Die gemeinsame Vorbereitung fehlt oder ist beschädigt. "
                    "Bestehende Fokusergebnisse dürfen nicht mit neu erzeugten Profilen gemischt werden."
                )

    seed_dir.mkdir(parents=True, exist_ok=True)
    if profiles_dir.exists():
        shutil.rmtree(profiles_dir)
    profiles_dir.mkdir(parents=True)
    manifest_path = seed_dir / MANIFEST_FILENAME
    _atomic_write_json(
        manifest_path,
        {
            "schema_version": PREPARED_SCENARIO_SCHEMA_VERSION,
            "status": "preparing",
            "scenario_name": scenario_name,
            "profile_hash": profile_hash,
            "generation_id": _new_run_id(),
            "random_seed": random_seed,
            "profile_options": profile_snapshot,
            "started_at": _utc_now(),
        },
    )

    from districtgenerator.classes.datahandler import Datahandler

    with seeded_profiles(random_seed):
        data = Datahandler(
            scenario_name=scenario_name,
            env_path=str(config_path),
            scenario_file_path=str(dg_input_dir(scenario_dir)),
            resultPath=str(profiles_dir),
        )
        from .dg_project_snapshot import capture_project_snapshot

        data.project_snapshot = capture_project_snapshot(
            data, config_path, dg_input_dir(scenario_dir) / f"{scenario_name}.csv"
        )
        if progress_path is not None:
            data.progress_file = str(progress_path)
        prepared = prepare_district(
            data,
            profile_options=profile_options,
            calcUserProfiles=True,
            saveUserProfiles=True,
            gen_cars=True,
            designEnergyhub=any(
                bool(device.get("feasible"))
                for device in data.central_device_data.values()
                if isinstance(device, dict)
            ),
        )
    if profile_options.snapshot() != profile_snapshot:
        raise RuntimeError("Die Profilquelldateien wurden während der Vorbereitung verändert.")
    _atomic_pickle(prepared_path, prepared)

    demands = sorted(
        str(path.relative_to(profiles_dir)).replace("\\", "/")
        for path in (profiles_dir / "demands").glob("*.csv")
        if path.is_file()
    )
    generation = sorted(
        str(path.relative_to(profiles_dir)).replace("\\", "/")
        for path in (profiles_dir / "generation").glob("*.csv")
        if path.is_file()
    )
    generation_id = json.loads(manifest_path.read_text(encoding="utf-8"))["generation_id"]
    _atomic_write_json(
        manifest_path,
        {
            "schema_version": PREPARED_SCENARIO_SCHEMA_VERSION,
            "status": "ready",
            "scenario_name": scenario_name,
            "profile_hash": profile_hash,
            "generation_id": generation_id,
            "random_seed": random_seed,
            "profile_options": profile_snapshot,
            "prepared_at": _utc_now(),
            "prepared_scenario": PREPARED_SCENARIO_FILENAME,
            "demands": demands,
            "generation": generation,
        },
    )
    return prepared_path, False, random_seed


def _set_variant_paths(data: Any, variant_dir: Path, effective_config_path: Path) -> None:
    variant_dir.mkdir(parents=True, exist_ok=True)
    data.resultPath = str(variant_dir)
    data.progress_file = str(variant_dir / "progress.json")
    data.env_path = effective_config_path.resolve()


def _set_optimization_focus(data: Any, focus: int) -> None:
    data.ecoData["optimization_focus"] = int(focus)
    data.all_sim_ecoData = data.calculate_ecoData_per_cluster()


def _copy_common_generation(common_dir: Path, variant_dir: Path) -> None:
    source = common_dir / "dg_profiles" / "generation"
    target = variant_dir / "generation"
    target.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)


def _relative_files(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    )


def _run_variant(
    *,
    prepared_path: Path,
    common_dir: Path,
    variant_dir: Path,
    objective: str,
    base_config_text: str,
    profile_hash: str,
    run_id: str,
) -> dict[str, Any]:
    focus = OBJECTIVE_FOCUS[objective]
    effective_config_path = variant_dir / EFFECTIVE_CONFIG_FILENAME
    _atomic_write_text(
        effective_config_path,
        render_effective_config(base_config_text, objective),
    )
    _copy_common_generation(common_dir, variant_dir)

    prepared = _load_pickle(prepared_path)
    if not isinstance(prepared, PreparedDistrict):
        raise DGComparisonError("Veraltete Modellvorbereitung; Vergleich neu starten.")
    data = prepared.data
    _set_variant_paths(data, variant_dir, effective_config_path)
    _set_optimization_focus(data, focus)

    finalize_district(prepared)
    data.optimizationClusters()
    data.calculateKPIs()
    summary = _variant_summary(data)
    optimization_path = save_optimization_results(
        data,
        objective=objective,
        optimization_focus=focus,
        profile_hash=profile_hash,
        comparison_run_id=run_id,
        summary=summary,
    )
    from ..output.certificates import create_certificate_best_effort

    certificate_warning = create_certificate_best_effort(
        data, objective, _progress_marker=_progress_marker,
    )

    result = {
        "status": "completed",
        "objective": objective,
        "optimization_focus": focus,
        "completed_at": _utc_now(),
        "result_path": str(variant_dir.resolve()),
        "effective_config": str(effective_config_path.resolve()),
        "effective_config_relative": f"dg_results/{EFFECTIVE_CONFIG_FILENAME}",
        "optimization_bundle": str(optimization_path.resolve()),
        "optimization_bundle_relative": (
            f"dg_results/optimization_results/{OPTIMIZATION_BUNDLE_FILENAME}"
        ),
        "summary": summary,
        "files": _relative_files(variant_dir),
    }
    if certificate_warning is not None:
        result["warnings"] = [certificate_warning]
    return result


def _commit_variant(staged: Path, target: Path) -> None:
    """Publish both output directories and their manifest as one directory."""

    backup = target.parent / f".previous-{target.name}-{_new_run_id()}"
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _rebase_optimization_bundle(bundle: Path, context: dict) -> None:
    """Store portable solution references and provenance before publishing."""

    payload = json.loads(bundle.read_text(encoding="utf-8"))
    payload["calculation_context"] = context
    capacities = payload.get("capacities") or {}
    source = capacities.get("source_file")
    if source:
        capacities["source_file"] = f"optimization_results/{Path(source).name}"
    _atomic_write_json(bundle, payload)


def planned_objectives(
    scenario_dir: Path, requested: Iterable[str], *,
    context: dict | None = None, profile_hash: str | None = None,
) -> tuple[str, ...]:
    """Recompute both objectives when any existing focus cannot be extended."""
    selected = _validated_objectives(requested)
    scenario_dir = Path(scenario_dir)
    config_path = dg_input_dir(scenario_dir) / ".env.CONFIG"
    building_path = dg_input_dir(scenario_dir) / f"{scenario_dir.name}.csv"
    context = context or calculation_context(config_path, building_path)
    existing = []
    for objective in DEFAULT_OBJECTIVES:
        path = objective_dir(scenario_dir, objective) / MANIFEST_FILENAME
        if not path.is_file():
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_OBJECTIVES
        if not same_calculation(manifest.get("calculation_context"), context):
            return DEFAULT_OBJECTIVES
        existing.append(manifest)
    if existing and len(selected) == 1:
        profile_hash = profile_hash or build_profile_fingerprint(config_path, building_path)
        if not _common_cache_is_usable(
            scenario_dir / "common", scenario_name=scenario_dir.name,
            profile_hash=profile_hash,
        ) or any(item.get("profile_hash") != profile_hash for item in existing):
            return DEFAULT_OBJECTIVES
        try:
            prepared = _load_pickle(
                seed_control_dir(scenario_dir) / PREPARED_SCENARIO_FILENAME
            )
            if (not isinstance(prepared, PreparedDistrict)
                    or getattr(prepared.data, "scenario_name", None) != scenario_dir.name):
                return DEFAULT_OBJECTIVES
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
            return DEFAULT_OBJECTIVES
    return selected


def results_match_current(scenario_dir: Path, objectives: Iterable[str]) -> bool:
    """The UI may reuse stored results only for exactly these inputs and code."""
    scenario_dir = Path(scenario_dir)
    config_path = dg_input_dir(scenario_dir) / ".env.CONFIG"
    building_path = dg_input_dir(scenario_dir) / f"{scenario_dir.name}.csv"
    current = calculation_context(config_path, building_path)
    for objective in _validated_objectives(objectives):
        path = objective_dir(scenario_dir, objective) / MANIFEST_FILENAME
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not same_calculation(manifest.get("calculation_context"), current):
            return False
    return True


def run_scenario_comparison(
    scenario_name: Any,
    *,
    objectives: Iterable[str] = DEFAULT_OBJECTIVES,
    reuse_common: bool = True,
    run_id: str | None = None,
    scenario_dir: Path | None = None,
) -> dict[str, Any]:
    """Prepare common data once and retain only the current result per focus."""

    name = validate_scenario_name(scenario_name)
    selected_objectives = _validated_objectives(objectives)
    resolved_scenario_dir = (
        Path(scenario_dir).resolve()
        if scenario_dir is not None
        else (DG_SCENARIOS_DIR / name).resolve()
    )
    config_path = dg_input_dir(resolved_scenario_dir) / ".env.CONFIG"
    building_csv_path = dg_input_dir(resolved_scenario_dir) / f"{name}.csv"
    missing = [str(path) for path in (config_path, building_csv_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError("Das Szenario ist unvollständig. Es fehlen: " + ", ".join(missing))

    resolved_run_id = str(run_id or _new_run_id())
    if not _SAFE_RUN_ID.fullmatch(resolved_run_id):
        raise ValueError(f"Ungültige Lauf-ID: {resolved_run_id!r}")
    ensure_profile_options_file(resolved_scenario_dir)
    profile_hash = build_profile_fingerprint(config_path, building_csv_path)
    context = calculation_context(config_path, building_csv_path)
    previous_contexts = []
    for objective in DEFAULT_OBJECTIVES:
        previous_path = objective_dir(resolved_scenario_dir, objective) / MANIFEST_FILENAME
        if previous_path.is_file():
            try:
                previous_contexts.append(json.loads(previous_path.read_text(encoding="utf-8")).get("calculation_context"))
            except (OSError, json.JSONDecodeError):
                previous_contexts.append(None)
    if any(not same_calculation(previous, context) for previous in previous_contexts):
        reuse_common = False
    selected_objectives = planned_objectives(
        resolved_scenario_dir, selected_objectives,
        context=context, profile_hash=profile_hash,
    )
    common_dir = resolved_scenario_dir / "common"
    result_root = results_dir(resolved_scenario_dir)
    result_root.mkdir(parents=True, exist_ok=True)
    work_dir = result_root / f".work-{resolved_run_id}"
    work_dir.mkdir(exist_ok=False)
    failure_path = result_root / "last_failure.json"
    base_config_text = config_path.read_text(encoding="utf-8")
    manifest: dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "status": "running",
        "run_id": resolved_run_id,
        "scenario_name": name,
        "requested_objectives": list(selected_objectives),
        "profile_hash": profile_hash,
        "calculation_context": context,
        "started_at": _utc_now(),
        "variants": {objective: {"status": "pending"} for objective in selected_objectives},
    }
    common_label = (
        "Quartiersvorbereitung" if len(selected_objectives) == 1
        else "Gemeinsame Quartiersvorbereitung"
    )
    _progress_marker("COMMON", "START", description=f"{common_label} startet")
    try:
        # A new comparison replaces old focuses before any partial result can
        # be published. A failed focus must never reveal an old counterpart.
        if len(selected_objectives) == len(DEFAULT_OBJECTIVES):
            for objective in DEFAULT_OBJECTIVES:
                shutil.rmtree(objective_dir(resolved_scenario_dir, objective), ignore_errors=True)
        try:
            prepared_path, cache_reused, random_seed = _prepare_common_scenario(
                scenario_name=name,
                scenario_dir=resolved_scenario_dir,
                config_path=config_path,
                common_dir=common_dir,
                profile_hash=profile_hash,
                progress_path=seed_control_dir(resolved_scenario_dir) / "progress.json",
                reuse_common=reuse_common,
            )
        except Exception as exc:
            manifest.update(status="failed", completed_at=_utc_now(), error={
                "type": type(exc).__name__, "message": str(exc),
            })
            _atomic_write_json(failure_path, manifest)
            _progress_marker("COMMON", "FAILED", description=f"{common_label} fehlgeschlagen")
            raise
        manifest["common"] = {
            "status": "ready",
            "path": str(common_dir.resolve()),
            "prepared_scenario": str(prepared_path.resolve()),
            "cache_reused": cache_reused,
            "random_seed": random_seed,
        }
        common_manifest = json.loads((seed_control_dir(resolved_scenario_dir) / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        common_generation_id = common_manifest.get("generation_id")
        _progress_marker(
            "COMMON", "COMPLETED", "REUSED" if cache_reused else "GENERATED",
            description=f"{common_label} abgeschlossen",
        )
        for index, objective in enumerate(selected_objectives, start=1):
            label = "Ökonomische" if objective == "economic" else "Ökologische"
            _progress_marker("VARIANT", f"{index}/{len(selected_objectives)}", objective,
                             "START", description=f"{label} Optimierung startet")
            stage_branch = work_dir / objective
            stage_dg = stage_branch / "dg_results"
            final_branch = objective_dir(resolved_scenario_dir, objective)
            final_dg = dg_results_dir(resolved_scenario_dir, objective)
            try:
                result = _run_variant(
                    prepared_path=prepared_path,
                    common_dir=common_dir,
                    variant_dir=stage_dg,
                    objective=objective,
                    base_config_text=base_config_text,
                    profile_hash=profile_hash,
                    run_id=resolved_run_id,
                )
                bundle = stage_dg / "optimization_results" / OPTIMIZATION_BUNDLE_FILENAME
                if not bundle.is_file():
                    raise DGComparisonError(f"Optimierungsbundle fehlt: {bundle}")
                _rebase_optimization_bundle(bundle, context)
                heo_dir = stage_branch / "heo_postprocessing_results"
                heo_dir.mkdir(parents=True)
                _atomic_write_json(heo_dir / "summary.json", result["summary"])
                variant_manifest = {
                    "schema_version": COMPARISON_SCHEMA_VERSION,
                    "status": "completed",
                    "scenario_name": name,
                    "objective": objective,
                    "optimization_focus": OBJECTIVE_FOCUS[objective],
                    "run_id": resolved_run_id,
                    "profile_hash": profile_hash,
                    "calculation_context": context,
                    "common_generation_id": common_generation_id,
                    "common_manifest_relative": "../../common/heo_seed_control/manifest.json",
                    "optimization_bundle_relative": "dg_results/optimization_results/optimization_results.json",
                    "summary": result["summary"],
                    "warnings": result.get("warnings", []),
                    "completed_at": _utc_now(),
                }
                _atomic_write_json(stage_branch / MANIFEST_FILENAME, variant_manifest)
                _commit_variant(stage_branch, final_branch)
                manifest["variants"][objective] = {
                    **variant_manifest,
                    "result_path": str(final_dg.resolve()),
                    "optimization_bundle": str((final_dg / "optimization_results" / OPTIMIZATION_BUNDLE_FILENAME).resolve()),
                }
                _progress_marker("VARIANT", f"{index}/{len(selected_objectives)}", objective,
                                 "COMPLETED", description=f"{label} Optimierung abgeschlossen")
            except Exception as exc:
                manifest["variants"][objective] = {
                    "status": "failed", "objective": objective,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
                _progress_marker("VARIANT", f"{index}/{len(selected_objectives)}", objective,
                                 "FAILED", description=f"{label} Optimierung fehlgeschlagen")
        completed = [objective for objective in selected_objectives
                     if manifest["variants"][objective]["status"] == "completed"]
        manifest["status"] = "completed" if len(completed) == len(selected_objectives) else (
            "partial" if completed else "failed"
        )
        manifest["completed_at"] = _utc_now()
        variants_now = []
        for objective in DEFAULT_OBJECTIVES:
            path = objective_dir(resolved_scenario_dir, objective) / MANIFEST_FILENAME
            try:
                variants_now.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                break
        manifest["comparison_complete"] = (
            len(variants_now) == len(DEFAULT_OBJECTIVES)
            and all(
                variant.get("profile_hash") == profile_hash
                and variant.get("common_generation_id") == common_generation_id
                and same_calculation(variant.get("calculation_context"), context)
                for variant in variants_now
            )
        )
        if manifest["status"] == "completed":
            failure_path.unlink(missing_ok=True)
            _progress_marker(
                "COMPARISON", "COMPLETED",
                description=(
                    "Optimierung abgeschlossen" if len(selected_objectives) == 1
                    else "Angeforderte Optimierungen abgeschlossen"
                ),
            )
            return manifest
        _atomic_write_json(failure_path, manifest)
        failed = [f"{objective}: {manifest['variants'][objective]['error']['message']}"
                  for objective in selected_objectives if objective not in completed]
        failure_label = (
            "Optimierung fehlgeschlagen" if len(selected_objectives) == 1
            else "Vergleichslauf unvollständig"
        )
        _progress_marker("COMPARISON", "FAILED", description=failure_label)
        raise DGComparisonRunError(
            failure_label + "; " + "; ".join(failed),
            manifest_path=failure_path,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


