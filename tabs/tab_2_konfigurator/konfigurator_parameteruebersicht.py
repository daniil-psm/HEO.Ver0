# Verbindet die gemeinsame Projektansicht mit den Editoren des Konfigurators.
from __future__ import annotations

from copy import deepcopy
from itertools import groupby
from dash import html

from ui.components.form_context import FormRenderContext

from dg_adapter.input.input_mapper import heo_state_to_dg_state
from dg_adapter.output.project_info import project_info_context
from ui.components.project_info import project_info_view, readonly_parameter_controls
from .konfigurator_projektformular import render_location_card
from .konfigurator_parameterdialoge import node_dialog
from .konfigurator_formfelder import parameter_controls
from ui.components.form_grid import automatic_form_grid

EDITABLE_TYPES = {
    "konfig-field", "konfig-building-field", "konfig-series-mode",
    "konfig-series-value", "konfig-range-toggle",
}
# Standort- und Wetterwerte stammen aus der Projektkonfiguration; direkte
# Eingaben würden beim Export durch deren abgeleitete Werte überschrieben.
MANAGED_FIELDS = {
    "LOCATION_NAME", "USE_GERMAN_ZIP", "ZIP", "WEATHER_FILE", "TIMEZONE",
    "TRYTYPE", "WEATHER_MODE", "TRY_REFERENCE_CITY",
}


# Kombiniert Standortauswahl, Wetterangaben und bearbeitbare Projektfelder.
def _project_editor(fields, state, weather_data, render_context):
    # Standortauswahl und Wetterupload werden einmal mit den übrigen
    # Projektfeldern kombiniert.
    editable = []
    seen = set()
    for field in fields:
        key = field.get("input_key") or field["env_key"]
        if field["env_key"] in MANAGED_FIELDS or key in seen:
            continue
        editable.append(field)
        seen.add(key)
    mode = state.get("location_mode", "pidula")
    filename = (weather_data or {}).get("filename")
    filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1] if mode == "other" and filename else None
    location_values = dict(state.get("values") or {})
    if mode == "other":
        location_values["LOCATION_NAME"] = (
            state.get("custom_location_name") or location_values.get("LOCATION_NAME", "")
        )
    # Ordnet die bearbeitbaren Projektfelder im gemeinsamen Raster an.
    def project_grid(project_fields):
        return automatic_form_grid(
            parameter_controls(project_fields, state, render_context=render_context),
            class_name="konfig-field-grid general-parameter-grid",
        )
    return html.Div([
        project_grid([field for field in editable if field["env_key"] == "SCENARIO_NAME"]),
        render_location_card(
            mode, location_values, id_prefix="all-param-project",
            weather_filename=filename,
        ),
        project_grid([field for field in editable if field["env_key"] != "SCENARIO_NAME"]),
    ], className="general-project-editor")


# Gruppiert bearbeitbare und verwaltete Felder unter Erhalt ihrer Reihenfolge.
def _parameter_editor(fields, state, values, defaults, weather_data, render_context):
    # Leere Sammel-Dictionaries und technische Einheiten sind keine Eingabefelder.
    fields = [field for field in fields if not (
        field.get("value_type") == "dict" and field.get("default") == {}
    ) and field["env_key"] not in {"UNIT_PLACEHOLDER", "UNIT_DASH"}]
    controls = []
    managed_present = False
    for managed, group in groupby(fields, key=lambda field: field["env_key"] in MANAGED_FIELDS):
        grouped_fields = list(group)
        managed_present |= managed
        controls.extend(
            readonly_parameter_controls(grouped_fields, values, defaults, weather_data)
            if managed else parameter_controls(grouped_fields, state, render_context=render_context)
        )
    children = [automatic_form_grid(
        controls, class_name="konfig-field-grid general-parameter-grid",
    )]
    if managed_present:
        children.append(html.Small(
            "Standort- und Wetterangaben werden aus der Projektkonfiguration übernommen."
        ))
    return html.Div(children)


# Baut die Übersicht mit fachlich stabilen Formular- und Abschnittsschlüsseln.
def parameter_overview(heo, buildings, weather, config):
    state = deepcopy(heo)
    values = state.setdefault("values", {})
    if not str(values.get("SCENARIO_NAME") or "").strip():
        source_scenario = str(config.get("source_scenario") or "").strip()
        if source_scenario:
            values["SCENARIO_NAME"] = source_scenario
    state["_range_enabled"] = dict(config.get("range_enabled") or {})
    selections = config.get("parameter_selection") or {}
    context = FormRenderContext(
        prefix="all-param", editable_types=frozenset(EDITABLE_TYPES),
        open_sections=config.get("parameter_details") or {},
    )

    # Nutzt die gemeinsamen Felder und erhält den fachlichen Abschnittskontext.
    def editor(fields, values, defaults, weather_data, *, render_context):
        if any(field["env_key"] == "WEATHER_MODE" for field in fields):
            return _project_editor(fields, state, weather_data, render_context)
        return _parameter_editor(fields, state, values, defaults, weather_data, render_context)

    # Bindet Gebäude- und Gerätedialoge mit ihrem eigenen fachlichen Schlüssel ein.
    def detail_editor(group, item, *, render_context):
        selection = {"kind": group, "code": item["key"]}
        return html.Div([
            html.H3(item["title"], className="general-info-card-title"),
            html.P(item["description"], className="general-info-card-description"),
            node_dialog(selection, state, buildings, embedded=True, render_context=render_context),
        ], className="general-master-detail-panel")

    project_context = project_info_context(
        weather, heo_state_to_dg_state(state, weather_metadata=weather), buildings,
    )
    view = project_info_view(
        project_context,
        selected_central_device=selections.get("central"),
        selected_decentral_device=selections.get("decentral"),
        selected_building=selections.get("building"),
        editor=editor, detail_editor=detail_editor, selector_type="all-param-selector",
        render_context=context,
    )
    return html.Div([
        html.Div(id="all-param-error", role="status"),
        view,
    ], className="konfig-all-parameters")
