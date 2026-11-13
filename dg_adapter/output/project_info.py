# Vergleicht den gespeicherten DG-Laufstand mit dem aktuellen HEO-Entwurf.

from __future__ import annotations

from datetime import datetime

from dg_adapter.input.input_mapper import dg_state_to_heo_state
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE, HEO_INPUT_SECTIONS
from dg_adapter.input.site_lookup import lookup_german_site
from heo.display.project_info_data import ProjectInfoContext, build_project_sections
from heo.model.buildings import building_state
from heo.model.site import location_mode_from_state


# Bereitet Entwurf oder Laufstand einschließlich Standort und Quellhinweis vor.
# Die Tab-Aufrufer übergeben den fertigen Kontext anschließend an den Renderer.
def project_info_context(
    weather_data: dict | None,
    dg_config_state: dict | None,
    building_scenario_state: dict | None,
    project_snapshot: dict | None = None,
    *, run_metadata: dict | None = None,
) -> ProjectInfoContext:
    draft_config = dg_config_state
    draft_buildings = building_scenario_state
    if project_snapshot:
        dg_config_state = project_snapshot["config"]
        building_scenario_state = project_snapshot["buildings"]
        weather_data = project_snapshot.get("weather")
    config_state = (
        dg_state_to_heo_state(dg_config_state)
        if dg_config_state is not None
        else DEFAULT_HEO_INPUT_STATE
    )
    values = config_state.get("values", {})
    defaults = config_state.get("defaults", {})
    buildings = building_state(building_scenario_state)["rows"]
    reference_city = None
    if location_mode_from_state(config_state) == "germany":
        try:
            reference_city = lookup_german_site(
                values.get("ZIP", defaults.get("ZIP"))
            )["reference_city"]
        except (ValueError, OSError, KeyError):
            pass
    source_label, source_note = project_source_status(
        draft_config, draft_buildings, project_snapshot, run_metadata, buildings,
    )
    return {
        "source_label": source_label,
        "source_note": source_note,
        "weather_data": weather_data,
        "buildings": buildings,
        "sections": build_project_sections(
            config_state, HEO_INPUT_SECTIONS, reference_city=reference_city,
        ),
    }


# Liefert Status und Beschreibung der angezeigten Projekteingaben.
def project_source_status(
    draft_config: dict | None,
    draft_buildings: dict | None,
    project_snapshot: dict | None,
    run_metadata: dict | None,
    buildings: list[dict],
    *,
    editable: bool = False,
) -> tuple[str, str]:
    metadata = run_metadata or {}
    if project_snapshot:
        source_label = (
            "Laufdaten · Eingaben geprüft"
            if project_snapshot.get("source") == "verified_legacy"
            else "Gespeicherter Laufstand"
        )
        saved_values = dg_state_to_heo_state(project_snapshot["config"]).get("values", {})
        draft_values = dg_state_to_heo_state(draft_config or {}).get("values", {})
        ignored = {"OPTIMIZATION_FOCUS", "OPTIMIZATION_FOCUS_MODE"}
        changed = any(
            value != saved_values.get(key)
            for key, value in draft_values.items() if key not in ignored
        ) or (
            draft_buildings is not None
            and building_state(draft_buildings)["rows"] != buildings
        )
        source_note = "Angezeigt werden die Eingaben des Berechnungslaufs."
        if changed:
            source_note += " Der aktuelle Entwurf weicht davon ab."
    else:
        source_label = "Entwurf · kein Laufstand verfügbar"
        source_note = "Diese Angaben sind nicht als Eingabestand eines Berechnungslaufs gespeichert."
    if editable:
        source_label = "Bearbeitbarer Entwurf"
        source_note = "Änderungen gelten für den Konfigurator. Globale Modellparameter gelten für das gesamte Szenario."
    if metadata.get("started_at"):
        try:
            stamp = datetime.fromisoformat(metadata["started_at"]).astimezone()
            source_note += f" Lauf vom {stamp:%d.%m.%Y, %H:%M %Z}."
        except (ValueError, TypeError):
            pass
    if metadata.get("variants"):
        source_note += " Zielvergleich: ökonomisch und ökologisch."
    elif metadata.get("objective"):
        source_note += " Optimierungsziel: " + {
            "economic": "ökonomisch.", "ecological": "ökologisch."
        }.get(metadata["objective"], str(metadata["objective"]))
    return source_label, source_note
