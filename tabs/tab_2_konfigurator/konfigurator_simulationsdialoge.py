# Baut Simulationseinstellungen, Fortschritt und Fehlermeldungen.

from __future__ import annotations

from typing import Any

from dash import dcc, html

from dg_adapter.execution.dg_progress_service import format_progress_percent
from dg_adapter.input.parameter_catalog import field_spec, fields_by_keys, fields_for_section
from heo.display.number_format import format_german_number
from heo.display.field_presentation import (
    FieldPresentation,
)
from ui.components.form_grid import (
    automatic_form_grid,
)
from ui.components.form_controls import (
    dependent_choice_controls,
    editable_value,
)
from ui.components.form_overlay import (
    form_value_field,
)
from heo.display.field_values import (
    parameter_choice_options,
)

from .konfigurator_formfelder import (
    field_value,
    field_control,
    parameter_controls,
)

# Baut die Eingabefelder für die Optimierungseinstellungen.
def simulation_settings(
    state: dict[str, Any], config_state: dict[str, Any] | None = None,
) -> html.Div:
    controls: list[Any] = []

    def choice_field(
        label: str, value: Any, controller_id: Any,
        options: list[dict[str, Any]], panels: list[dict[str, Any]],
        *, help_text: str = "", class_name: str = "",
    ) -> html.Div:
        return form_value_field(
            FieldPresentation(
                label=label, value=value, editable=True, kind="full",
                help_text=help_text,
            ),
            dependent_choice_controls(
                controller_id=controller_id,
                options=options,
                value=value,
                panels=panels,
                controller_class_name="konfig-radio konfig-option-choice",
            ),
            class_name=f"konfig-field konfig-activation-field {class_name}".strip(),
        )

    def parameter_panel(
        panel_id: str, when: str, fields: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": panel_id,
            "when": when,
            "class_name": "konfig-dependent-fields",
            "children": automatic_form_grid(
                [field_control(field, state) for field in fields],
                class_name="konfig-field-grid",
                keep_together=True,
            ),
        }

    climate = field_spec("CLIMATE_PERIOD")
    if climate:
        climate = dict(climate)
        climate["label"] = "Klimazeitraum"
        climate["help_text_de"] = (
            "Bei deutschen PLZ wird zwischen den DWD-TRY-Klimazeiträumen gewählt. "
            "Für andere Standorte gilt die ausgewählte EPW-Wetterdatei."
        )
        controls.append(field_control(climate, state))
    controls.extend(parameter_controls(fields_by_keys(["OBSERVATION_TIME"]), state))
    count = (state.get("values") or {}).get(
        "NUM_INTERPOLATION_POINTS",
        (state.get("defaults") or {}).get("NUM_INTERPOLATION_POINTS"),
    )
    support_year_mode = "count" if count not in (None, "", "None", "null") else "years"
    controls.append(choice_field(
        "Stützjahre definieren nach", support_year_mode,
        "konfig-support-year-mode",
        [
            {"label": "Anzahl Stützjahre", "value": "count"},
            {"label": "Konkrete Jahre", "value": "years"},
        ],
        [
            parameter_panel(
                "konfig-support-year-count-panel", "count",
                fields_by_keys(["NUM_INTERPOLATION_POINTS"]),
            ),
            parameter_panel(
                "konfig-support-year-list-panel", "years",
                fields_by_keys(["INTERPOLATION_POINTS"]),
            ),
        ],
        help_text=(
            "Eine Anzahl verteilt die Stützjahre automatisch über die Projektlaufzeit. "
            "Bei konkreten Jahren gilt die eingegebene Liste."
        ),
        class_name="konfig-support-year-mode-field",
    ))
    time_controls = parameter_controls(fields_for_section("time"), state)
    pyomo_fields = fields_for_section("pyomo")
    common_keys = {
        "SOLVER_OPTIONS__TIME_LIMIT", "SOLVER_OPTIONS__MIP_GAP",
        "SOLVER_OPTIONS__THREADS",
    }
    solver = next(field for field in pyomo_fields if field["env_key"] == "SOLVER_NAME")
    solver_name = str(field_value(state, solver) or "highs").lower()
    solver_control = choice_field(
        "Solver", solver_name,
        {"type": "konfig-field", "key": "SOLVER_NAME"},
        parameter_choice_options(solver, solver_name),
        [parameter_panel(
            "konfig-gurobi-options-panel", "gurobi",
            fields_by_keys([
                "SOLVER_OPTIONS__NONCONVEX",
                "SOLVER_OPTIONS__DUAL_REDUCTIONS",
            ]),
        )],
        class_name="konfig-solver-choice-field",
    )
    pyomo_controls = parameter_controls([
        field for field in pyomo_fields if field["env_key"] in common_keys
    ], state)
    seed_settings = config_state or {}
    seed_mode = seed_settings.get("profile_seed_mode", "fixed")
    seed = seed_settings.get("profile_seed", 20261013)
    displayed_seed = format_german_number(
        seed, kind="integer", group_thousands=False,
    )
    seed_value = form_value_field(
        FieldPresentation(
            label="Seed-Wert", value=seed, editable=True, kind="number",
            number_kind="integer",
            help_text="Ganzzahl zwischen 0 und 4294967295.",
        ),
        editable_value(
            displayed_seed,
            dcc.Input(
                id="konfig-profile-seed-value",
                type="text", inputMode="numeric",
                value=displayed_seed, debounce=True,
                className=(
                    "konfig-input konfig-number-input heo-number-input "
                    "heo-number-input--integer heo-number-input--ungrouped"
                ),
            ),
        ),
        class_name="konfig-field konfig-profile-seed-value-field",
    )
    seed_control = choice_field(
        "Seed", seed_mode,
        "konfig-profile-seed-mode",
        [
            {"label": "Zufällig", "value": "random"},
            {"label": "Vorgeben", "value": "fixed"},
        ],
        [{
            "id": "konfig-profile-seed-fixed-panel",
            "when": "fixed",
            "class_name": "konfig-dependent-fields",
            "children": automatic_form_grid(
                [seed_value], class_name="konfig-field-grid", keep_together=True,
            ),
        }],
        help_text=(
            "Zufällig wählt bei jedem Optimierungsstart einen neuen Seed. "
            "Bei vorgeben wird derselbe Seed für weitere Läufe verwendet."
        ),
        class_name="konfig-profile-seed-mode-field",
    )
    controls.extend([solver_control, seed_control])
    first_numeric_cell = len(controls)
    controls.extend(time_controls)
    controls.extend(pyomo_controls)
    grid = automatic_form_grid(controls, class_name="konfig-field-grid konfig-simulation-parameter-grid")
    setattr(grid, "data-form-layout", "rows")
    setattr(grid.children[first_numeric_cell], "data-form-break-before", "true")
    return html.Div(
        className="konfig-simulation-settings", children=grid,
        **{"data-form-layout-owner": "external"},
    )


# Formatiert die Laufzeit für die Fortschrittsanzeige.
def _format_elapsed_time(value: Any) -> str:
    try:
        total_seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return "—"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


# Stellt die Optimierungsschritte als Protokolltabelle dar.
def _simulation_log_table(
    simulation: dict[str, Any], *, additional_message: str | None = None,
) -> html.Div:
    raw_entries = simulation.get("log_entries")
    entries = list(raw_entries) if isinstance(raw_entries, list) else []
    if not entries:
        log_text = str(simulation.get("log") or "").rstrip()
        entries = [{"text": "Start der Optimierung", "elapsed_seconds": 0}]
        entries.extend(
            {"text": line, "elapsed_seconds": None}
            for line in log_text.splitlines()
        )
    if additional_message and additional_message not in "\n".join(
        str(entry.get("text") or "") for entry in entries if isinstance(entry, dict)
    ):
        entries.append({
            "text": additional_message,
            "elapsed_seconds": simulation.get("elapsed_seconds"),
        })

    requested = simulation.get("requested_objectives")
    single_run = len(requested) == 1 if isinstance(requested, (list, tuple)) else any(
        isinstance(entry, dict)
        and "[HEO_COMPARISON] VARIANT 1/1 " in str(entry.get("text") or "")
        for entry in entries
    )

    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        elapsed = _format_elapsed_time(entry.get("elapsed_seconds"))
        message = str(entry.get("text") or "")
        if single_run and message.startswith("[HEO_COMPARISON] COMPARISON COMPLETED"):
            message = "Optimierung abgeschlossen"
        elif single_run and message.startswith("[HEO_COMPARISON] ") and " | " in message:
            message = message.partition(" | ")[2]
            message = message.replace(
                "Gemeinsame Quartiersvorbereitung", "Quartiersvorbereitung"
            )
        rows.append(
            html.Div(
                className="konfig-log-row",
                children=[
                    html.Pre(message, className="konfig-log-message"),
                    html.Time(elapsed, className="konfig-log-time"),
                ],
            )
        )

    return html.Div(
        id="konfig-progress-log-table",
        className="konfig-log-table",
        children=[
            html.Div(
                className="konfig-log-row konfig-log-header",
                children=[
                    html.Span("Log"),
                    html.Span("Zeit ab Start"),
                ],
            ),
            *rows,
        ],
    )


# Rendert Status, Fortschritt und Protokoll des Optimierungslaufs.
def simulation_monitor(simulation: dict[str, Any] | None) -> html.Div:
    simulation = simulation or {}
    completed = simulation.get("status") == "completed"
    try:
        progress = max(0.0, min(100.0, float(simulation.get("progress") or 0)))
    except (TypeError, ValueError):
        progress = 0.0
    progress_label = format_progress_percent(progress)
    elapsed_seconds = simulation.get("elapsed_seconds")
    if elapsed_seconds is None:
        for entry in reversed(simulation.get("log_entries") or []):
            if isinstance(entry, dict) and entry.get("elapsed_seconds") is not None:
                elapsed_seconds = entry["elapsed_seconds"]
                break
    return html.Div(
        className="konfig-simulation-monitor",
        **{
            "data-running": "true" if simulation.get("running") else "false",
            "data-elapsed-seconds": str(elapsed_seconds) if elapsed_seconds is not None else "",
            "data-run-id": ":".join(str(simulation.get(key) or "") for key in (
                "scenario_name", "started_at", "pid",
            )),
        },
        children=[
            html.H2(
                "Optimierung abgeschlossen"
                if completed
                else f"Optimierung · {simulation.get('scenario_name') or 'Szenario'}"
            ),
            html.Span(f"{progress_label} %", className="konfig-progress-value"),
            html.Div(
                className="konfig-progress-track",
                role="progressbar",
                **{
                    "aria-label": "Optimierungsfortschritt",
                    "aria-valuemin": "0",
                    "aria-valuemax": "100",
                    "aria-valuenow": str(progress),
                },
                children=html.Div(
                    className="konfig-progress-fill",
                    style={"width": f"{progress}%"},
                ),
            ),
            html.Div(
                className="konfig-progress-status",
                children=[
                    html.Strong(
                        simulation.get("phase") or "Wird vorbereitet",
                        className="konfig-progress-phase",
                    ),
                    html.Time(
                        f"Dauer: {_format_elapsed_time(elapsed_seconds)}",
                        className="konfig-progress-duration",
                    ),
                ],
            ),
            *(
                [
                    html.Div(
                        className="konfig-completion-actions",
                        children=html.Button(
                            "Energiesystem öffnen",
                            id="konfig-completion-open-results",
                            n_clicks=0,
                            className="app-sidebar-nav-button konfig-completion-button",
                        ),
                    )
                ]
                if completed
                else []
            ),
            html.Details(
                id="konfig-progress-log-details",
                className="konfig-progress-details",
                children=[
                    html.Summary("Detail", id="konfig-progress-log-summary"),
                    _simulation_log_table(simulation),
                ],
            ),
        ],
    )


# Zeigt das Fehlerprotokoll im ausklappbaren Log des Main Panels.
def simulation_failure_notice(simulation: dict[str, Any] | None) -> html.Div:
    simulation = simulation or {}
    error = str(simulation.get("error") or "").strip()
    explicit_error = bool(error)
    if not error:
        log_lines = [
            line.rstrip()
            for line in str(simulation.get("log") or "").splitlines()
            if line.strip()
        ]
        traceback_starts = [
            index
            for index, line in enumerate(log_lines)
            if line.startswith("Traceback (most recent call last):")
        ]
        if traceback_starts:
            error = "\n".join(log_lines[traceback_starts[-1]:][-30:])
        elif log_lines:
            error = "\n".join(log_lines[-12:])
    fallback_message = not error
    if fallback_message:
        returncode = simulation.get("returncode")
        error = (
            f"Der District Generator wurde mit Rückgabecode {returncode} beendet."
            if returncode is not None
            else "Der District Generator konnte die Optimierung nicht abschließen."
        )
    additional_message = error if explicit_error or fallback_message else None

    return html.Div(
        className="konfig-simulation-failed",
        children=html.Div(
            className="konfig-simulation-failed-content",
            children=[
                html.H2("Optimierung fehlgeschlagen"),
                html.Pre(error, className="konfig-simulation-error"),
                html.Details(
                    id="konfig-progress-log-details",
                    className="konfig-progress-details",
                    children=[
                        html.Summary("Detail", id="konfig-progress-log-summary"),
                        _simulation_log_table(simulation, additional_message=additional_message),
                    ],
                ),
            ],
        ),
    )
