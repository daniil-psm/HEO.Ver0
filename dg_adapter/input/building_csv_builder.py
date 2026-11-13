# Erzeugt DG-Gebäude-CSV und speichert sie mit den zugehörigen HEO-Gebäudenamen.
from __future__ import annotations
import csv
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable
from .validation import SCENARIO_COLUMNS, validate_building_rows
from .scenario_paths import scenario_building_csv_path, scenario_building_metadata_path

# Rendert validierte Gebäudezeilen als DG-kompatible Semikolon-CSV.
def render_building_csv(rows: Iterable[dict[str, Any]] | None) -> str:

    normalized = validate_building_rows(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=SCENARIO_COLUMNS,
        delimiter=";",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(normalized)
    return stream.getvalue()


# Schreibt die Gebäude-CSV atomar in den szenariospezifischen Ordner.
def save_building_scenario(
    scenario_name: Any,
    rows: Iterable[dict[str, Any]] | None,
) -> dict[str, Any]:

    source_rows = list(rows or [])
    csv_path = scenario_building_csv_path(scenario_name)
    metadata_path = scenario_building_metadata_path(scenario_name)
    content = render_building_csv(source_rows)
    metadata_content = json.dumps(
        {
            "version": 1,
            "buildings": [
                {
                    "id": index,
                    "name": str(row.get("name") or ""),
                }
                for index, row in enumerate(source_rows, start=1)
            ],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    csv_changed = not (
        csv_path.exists() and csv_path.read_text(encoding="utf-8") == content
    )
    metadata_changed = not (
        metadata_path.exists()
        and metadata_path.read_text(encoding="utf-8") == metadata_content
    )
    if not csv_changed and not metadata_changed:
        return {
            "written": False,
            "csv_path": str(csv_path),
            "metadata_path": str(metadata_path),
            "backup_path": None,
            "building_count": len(source_rows),
        }

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    backup_path: Path | None = None
    try:
        if csv_changed:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                prefix=".heo-buildings-", suffix=".tmp",
                dir=csv_path.parent, delete=False,
            ) as temporary_file:
                temporary_file.write(content)
                temporary_path = Path(temporary_file.name)
            if csv_path.exists():
                backup_path = csv_path.with_name(f"{csv_path.name}.bak")
                shutil.copy2(csv_path, backup_path)
            os.replace(temporary_path, csv_path)
            temporary_path = None

        if metadata_changed:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n",
                prefix=".heo-building-names-", suffix=".tmp",
                dir=metadata_path.parent, delete=False,
            ) as temporary_file:
                temporary_file.write(metadata_content)
                temporary_path = Path(temporary_file.name)
            os.replace(temporary_path, metadata_path)
            temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {
        "written": True,
        "csv_path": str(csv_path),
        "metadata_path": str(metadata_path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "building_count": len(source_rows),
    }

