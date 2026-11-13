# Erzeugt, prüft und speichert die szenariospezifischen Startskripte für den District Generator.

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..input.config_service import DG_SCENARIOS_DIR
from ..shared.scenario_names import validate_scenario_name
from . import run_template


# Ermittelt den Pfad der Startdatei eines validierten HEO-/DG-Szenarios.
def scenario_run_path(scenario_name: Any) -> Path:
    name = validate_scenario_name(scenario_name)
    return DG_SCENARIOS_DIR / name / run_template.RUN_FILENAME


# Speichert die Startdatei atomar und sichert einen abweichenden Vorgänger.
def save_scenario_run(scenario_name: Any) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    run_path = scenario_run_path(name)
    content = run_template.render_scenario_run(name)
    unchanged = run_path.is_file() and run_path.read_text(encoding="utf-8") == content
    if unchanged:
        return {
            "written": False,
            "scenario_name": name,
            "run_path": str(run_path),
            "backup_path": None,
        }

    run_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    backup_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".heo-run-",
            suffix=".tmp",
            dir=run_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        if run_path.exists():
            backup_path = run_path.with_name(f"{run_path.name}.bak")
            shutil.copy2(run_path, backup_path)

        os.replace(temporary_path, run_path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {
        "written": True,
        "scenario_name": name,
        "run_path": str(run_path),
        "backup_path": str(backup_path) if backup_path is not None else None,
    }
