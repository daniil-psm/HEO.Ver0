"""Move scenario data to common/ and keep only one result per objective.

Dry-run by default. --apply validates all selected artifacts before removing any
historical run directory. Safe to rerun after a completed migration.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dg_backend"))

from dotenv import dotenv_values
from dg_adapter.execution.dg_model_preparation import PreparedDistrict
from dg_adapter.execution.profile_fingerprint import (
    PREPARED_SCENARIO_SCHEMA_VERSION, build_profile_fingerprint,
)
from dg_adapter.shared.comparison_contract import COMPARISON_SCHEMA_VERSION
from dg_adapter.input.config_service import DG_SCENARIOS_DIR
from dg_adapter.shared.dg_paths import dg_input_dir, dg_profiles_dir, dg_results_dir, objective_dir, seed_control_dir
from dg_adapter.execution.profile_service import load_profile_options
from dg_adapter.execution.run_template import render_scenario_run

OBJECTIVES = ("economic", "ecological")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.migration-tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def old_candidates(scenario: Path) -> list[dict]:
    records = []
    runs = scenario / "results" / "comparisons" / "runs"
    for manifest_path in runs.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("scenario_name") != scenario.name:
            continue
        profile_hash = manifest.get("profile_hash")
        if not isinstance(profile_hash, str) or len(profile_hash) != 64:
            continue
        for objective in OBJECTIVES:
            variant = (manifest.get("variants") or {}).get(objective) or {}
            if variant.get("status") != "completed":
                continue
            directory = manifest_path.parent / objective
            bundle = directory / "optimization_results" / "optimization_results.json"
            if not bundle.is_file():
                continue
            try:
                payload = json.loads(bundle.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("schema_version") != 1 or "results" not in payload:
                continue
            if payload.get("objective") not in (None, objective):
                continue
            records.append({
                "objective": objective, "profile_hash": profile_hash,
                "run_id": str(manifest.get("run_id") or manifest_path.parent.name),
                "completed_at": str(variant.get("completed_at") or manifest.get("completed_at") or ""),
                "directory": directory, "manifest": manifest, "variant": variant,
            })
    return records


def select_current(records: list[dict]) -> tuple[str | None, dict[str, dict]]:
    if not records:
        return None, {}
    newest = max(records, key=lambda row: (row["completed_at"], row["run_id"]))
    selected_hash = newest["profile_hash"]
    return selected_hash, {
        objective: max(
            (row for row in records if row["profile_hash"] == selected_hash and row["objective"] == objective),
            key=lambda row: (row["completed_at"], row["run_id"]),
        )
        for objective in OBJECTIVES
        if any(row["profile_hash"] == selected_hash and row["objective"] == objective for row in records)
    }


def can_mark_current(scenario: Path, selection: dict[str, dict], old_common: Path) -> bool:
    if not selection or not (old_common / "prepared_scenario.p").is_file():
        return False
    try:
        common_manifest = json.loads((old_common / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if (common_manifest.get("status") != "ready"
            or common_manifest.get("profile_hash") != next(iter(selection.values()))["profile_hash"]):
        return False
    config = scenario / ".env.CONFIG"
    buildings = scenario / f"{scenario.name}.csv"
    current_config = {k: v for k, v in dotenv_values(config).items() if k != "OPTIMIZATION_FOCUS"}
    for record in selection.values():
        effective = record["directory"] / "effective.env"
        if not effective.is_file():
            return False
        old_config = {k: v for k, v in dotenv_values(effective).items() if k != "OPTIMIZATION_FOCUS"}
        if old_config != current_config:
            return False
        try:
            completed = datetime.fromisoformat(record["completed_at"]).timestamp()
        except ValueError:
            return False
        if config.stat().st_mtime > completed + 1 or buildings.stat().st_mtime > completed + 1:
            return False
    try:
        with (old_common / "prepared_scenario.p").open("rb") as handle:
            prepared = pickle.load(handle)
        if not isinstance(prepared, PreparedDistrict) or prepared.data.scenario_name != scenario.name:
            return False
    except Exception:
        return False
    return True


def move_file(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.is_file() and target.is_file() and source.read_bytes() == target.read_bytes():
            source.unlink()
            return
        raise FileExistsError(f"Ziel existiert bereits: {target}")
    os.replace(source, target)


def migrate(scenario: Path, apply: bool) -> dict:
    old_config = scenario / ".env.CONFIG"
    new_config = dg_input_dir(scenario) / ".env.CONFIG"
    if not old_config.is_file():
        if new_config.is_file():
            if (scenario / "results" / "comparisons").exists():
                raise RuntimeError(
                    f"Migration von {scenario.name} ist unvollständig: alte Vergleichsdaten sind noch vorhanden. "
                    "Bitte vor erneutem Anwenden prüfen."
                )
            return {"scenario": scenario.name, "status": "already_migrated"}
        return {"scenario": scenario.name, "status": "skipped"}
    old_csv = scenario / f"{scenario.name}.csv"
    if not old_csv.is_file():
        raise FileNotFoundError(old_csv)
    profile_hash, selection = select_current(old_candidates(scenario))
    old_common = (scenario / "results" / "comparisons" / "common" / profile_hash) if profile_hash else None
    if old_common and not (old_common / "demands").is_dir():
        old_common = None
    if old_common and not (old_common / "manifest.json").is_file():
        old_common = None
    current = bool(old_common and can_mark_current(scenario, selection, old_common))
    plan = {
        "scenario": scenario.name,
        "status": "planned" if not apply else "migrated",
        "selected": {key: value["run_id"] for key, value in selection.items()},
        "legacy_hash": profile_hash,
        "current_input_match": current,
    }
    if not apply:
        return plan

    # Validate target collisions before moving any input or deleting history.
    pending_inputs = [
        (old_config, new_config),
        (old_csv, dg_input_dir(scenario) / old_csv.name),
        *[(path, dg_input_dir(scenario) / path.name) for path in scenario.glob(".env.CONFIG.bak")],
        *[(path, dg_input_dir(scenario) / path.name) for path in scenario.glob(f"{scenario.name}.csv.bak")],
        (scenario / ".env.PROFILES", seed_control_dir(scenario) / ".env.PROFILES"),
        *[(scenario / "results" / name, seed_control_dir(scenario) / name)
          for name in ("simulation.log", "progress.json")],
    ]
    for source, target in pending_inputs:
        if source.exists() and target.exists() and source.read_bytes() != target.read_bytes():
            raise FileExistsError(f"Ziel enthält abweichende Daten: {target}")
    for objective in selection:
        target = objective_dir(scenario, objective)
        if target.exists():
            raise FileExistsError(f"Ziel existiert bereits: {target}")
    if old_common:
        for dirname in ("demands", "generation"):
            source = old_common / dirname
            target = dg_profiles_dir(scenario) / dirname
            if source.exists() and target.exists():
                raise FileExistsError(f"Ziel existiert bereits: {target}")
        if current and (seed_control_dir(scenario) / "prepared_scenario.p").exists():
            raise FileExistsError(f"Ziel existiert bereits: {seed_control_dir(scenario) / 'prepared_scenario.p'}")

    input_dir = dg_input_dir(scenario)
    seed_dir = seed_control_dir(scenario)
    profile_dir = dg_profiles_dir(scenario)
    input_dir.mkdir(parents=True, exist_ok=True)
    seed_dir.mkdir(parents=True, exist_ok=True)
    move_file(old_config, new_config)
    move_file(old_csv, input_dir / old_csv.name)
    for backup in scenario.glob(".env.CONFIG.bak"):
        move_file(backup, input_dir / backup.name)
    for backup in scenario.glob(f"{scenario.name}.csv.bak"):
        move_file(backup, input_dir / backup.name)
    old_profile_env = scenario / ".env.PROFILES"
    profile_env = seed_dir / ".env.PROFILES"
    if old_profile_env.exists():
        move_file(old_profile_env, profile_env)
    elif not profile_env.exists():
        profile_env.write_bytes((ROOT / "dg_adapter" / ".env.PROFILES").read_bytes())
    for filename in ("simulation.log", "progress.json"):
        move_file(scenario / "results" / filename, seed_dir / filename)

    new_hash = build_profile_fingerprint(new_config, input_dir / old_csv.name)
    published_hash = new_hash if current else profile_hash
    if old_common and selection:
        profile_dir.mkdir(parents=True, exist_ok=True)
        for dirname in ("demands", "generation"):
            move_file(old_common / dirname, profile_dir / dirname)
        if (old_common / "prepared_scenario.p").is_file() and current:
            move_file(old_common / "prepared_scenario.p", seed_dir / "prepared_scenario.p")
        old_manifest = json.loads((old_common / "manifest.json").read_text(encoding="utf-8"))
        old_manifest.update({
            "schema_version": PREPARED_SCENARIO_SCHEMA_VERSION,
            "status": "ready" if current else "stale",
            "profile_hash": published_hash,
            "source_profile_hash": profile_hash,
            "generation_id": profile_hash,
            "profile_options": load_profile_options(scenario).snapshot(),
            "prepared_scenario": "prepared_scenario.p" if current else None,
        })
        write_json(seed_dir / "manifest.json", old_manifest)

    for objective, record in selection.items():
        target_branch = objective_dir(scenario, objective)
        if target_branch.exists():
            raise FileExistsError(f"Ziel existiert bereits: {target_branch}")
        target_dg = dg_results_dir(scenario, objective)
        target_dg.parent.mkdir(parents=True, exist_ok=True)
        os.replace(record["directory"], target_dg)
        bundle = target_dg / "optimization_results" / "optimization_results.json"
        payload = json.loads(bundle.read_text(encoding="utf-8"))
        payload["profile_hash"] = published_hash
        source = (payload.get("capacities") or {}).get("source_file")
        if source:
            payload["capacities"]["source_file"] = str(target_dg / "optimization_results" / Path(source).name)
        write_json(bundle, payload)
        heo_dir = target_branch / "heo_postprocessing_results"
        write_json(heo_dir / "summary.json", record["variant"].get("summary") or {})
        write_json(target_branch / "manifest.json", {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "status": "completed", "scenario_name": scenario.name,
            "objective": objective,
            "optimization_focus": 0 if objective == "economic" else 1,
            "run_id": record["run_id"],
            "profile_hash": published_hash,
            "common_generation_id": profile_hash,
            "source_profile_hash": profile_hash,
            "common_manifest_relative": "../../common/heo_seed_control/manifest.json",
            "optimization_bundle_relative": "dg_results/optimization_results/optimization_results.json",
            "summary": record["variant"].get("summary") or {},
            "warnings": record["variant"].get("warnings") or [],
            "completed_at": record["completed_at"],
        })

    (scenario / "run.py").write_text(render_scenario_run(scenario.name), encoding="utf-8")
    # Historical retries and obsolete single-run artifacts are not part of the
    # new, one-current-result storage contract.
    results = scenario / "results"
    shutil.rmtree(results / "comparisons", ignore_errors=True)
    for dirname in ("demands", "generation", "optimization_results", "plots"):
        shutil.rmtree(results / dirname, ignore_errors=True)
    for pattern in ("KPIs_*", "Quartiersenergieausweis_*.pdf", "*.p", "simulation.log", "progress.json"):
        for path in results.glob(pattern):
            if path.is_file():
                path.unlink()
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Migrate and remove historical runs")
    parser.add_argument("--scenario", action="append", help="Only this scenario (repeatable)")
    args = parser.parse_args()
    selected = set(args.scenario or [])
    for scenario in sorted(DG_SCENARIOS_DIR.iterdir()):
        if not scenario.is_dir() or (selected and scenario.name not in selected):
            continue
        if not (scenario / ".env.CONFIG").exists() and not (dg_input_dir(scenario) / ".env.CONFIG").exists():
            continue
        print(json.dumps(migrate(scenario, args.apply), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
