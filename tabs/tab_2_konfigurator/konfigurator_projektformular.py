# Baut das Projektstart- und Szenarioladeformular des Konfigurators.

from __future__ import annotations

from typing import Any

from dash import dcc, html

from dg_adapter.input.config_service import next_microgrid_name
from dg_adapter.input.parameter_catalog import fields_by_keys
from heo.display.parameter_catalog import SECTION_TITLES
from heo.display.parameter_dialog_layout import PROJECT_FIELDS
from heo.display.field_presentation import (
    FieldPresentation,
)
from ui.components.form_controls import (
    dependent_choice_controls,
    editable_value,
    form_action_field,
    form_heading_field,
)
from ui.components.form_grid import (
    form_cell,
    form_grid,
)
from ui.components.form_overlay import (
    form_value_field,
)

from .konfigurator_formfelder import field_control, field_grid

# Definiert die Standortauswahl über den zentralen Abhängigkeitsblock.
def render_location_card(
    mode: str, values: dict[str, Any], *, id_prefix: str = "konfig",
    weather_filename: str | None = None,
) -> html.Div:
    def location_input(
        label: str,
        component_id: str,
        value: Any,
        *,
        numeric: bool = False,
    ) -> html.Div:
        """Verwendet auch für Standortdaten den zentralen Feldbaustein."""

        input_props: dict[str, Any] = {}
        input_classes = ["konfig-input"]
        if numeric:
            input_classes.append("konfig-number-input")
            input_props.update(inputMode="numeric", pattern="[0-9]*")
        return form_value_field(
            FieldPresentation(
                label=label,
                value=str(value if value is not None else ""),
                editable=True,
                kind="number" if numeric else "text",
            ),
            editable_value(
                value,
                dcc.Input(
                    id=component_id,
                    value=value,
                    type="text",
                    debounce=id_prefix != "konfig",
                    className=" ".join(input_classes),
                    **input_props,
                ),
            ),
            class_name="konfig-field konfig-location-input-field",
        )

    return html.Div(
        className="konfig-location-card",
        children=[
            html.H3("Standort"),
            html.Span("Wettermodus", className="heo-field__label")
            if id_prefix != "konfig" else None,
            dependent_choice_controls(
                controller_id=f"{id_prefix}-location-mode",
                options=[
                    {"label": "Pidula", "value": "pidula"},
                    {"label": "Deutschland", "value": "germany"},
                    {"label": "Sonstiger Standort", "value": "other"},
                ],
                value=mode,
                controller_class_name="konfig-radio konfig-location-radio",
                panels=[
                    {
                        "id": f"{id_prefix}-location-germany",
                        "when": "germany",
                        "class_name": "konfig-dependent-fields konfig-location-dependent",
                        "children": [
                            location_input(
                                "Postleitzahl",
                                f"{id_prefix}-location-zip",
                                values.get("ZIP", "10115"),
                                numeric=True,
                            ),
                            html.Div(id=f"{id_prefix}-site-preview", className="konfig-site-preview"),
                        ],
                    },
                    {
                        "id": f"{id_prefix}-location-other",
                        "when": "other",
                        "class_name": "konfig-dependent-fields konfig-location-dependent",
                        "children": [
                            location_input(
                                "Standortname",
                                f"{id_prefix}-location-name",
                                values.get("LOCATION_NAME", ""),
                            ),
                            dcc.Upload(
                                id=f"{id_prefix}-weather-upload",
                                className="konfig-weather-upload",
                                children=[html.Strong("EPW-Datei hier ablegen"), html.Span(" oder auswählen")],
                                multiple=False,
                                accept=".epw",
                            ),
                            html.Div(
                                f"Geladen: {weather_filename}" if weather_filename else "",
                                id=f"{id_prefix}-weather-upload-name",
                                className="konfig-upload-name",
                            ),
                        ],
                    },
                ],
            ),
        ],
    )


# Erfasst die Projektdaten auf der Startseite des Konfigurators.
def project_form(state: dict[str, Any], *, embedded: bool = False) -> html.Div:
    project_specs = fields_by_keys(list(PROJECT_FIELDS))
    excluded = set()
    if embedded:
        excluded.add("SCENARIO_NAME")
    by_key = {
        str(field.get("input_key") or field["env_key"]): field
        for field in project_specs
    }
    visible_fields = [
        field for field in project_specs
        if (field.get("input_key") or field["env_key"]) not in excluded
    ]
    mode = (state or {}).get("location_mode", "pidula")
    values = (state or {}).get("values", {})
    scenario_name = str(values.get("SCENARIO_NAME") or next_microgrid_name())
    location_card = render_location_card(mode, values)
    if embedded:
        children = [form_grid(
            [
                form_cell(
                    form_heading_field(
                        scenario_name,
                        button_id="konfig-project-name-heading",
                        input_id="konfig-project-name-input",
                        state_id="konfig-project-name-editing",
                    ),
                    row=1, column=1, column_span=2,
                    class_name="konfig-form-heading-cell",
                ),
                form_cell(
                    location_card,
                    row=2, column=1, row_span=3,
                    class_name="konfig-project-location-cell",
                ),
                form_cell(
                    field_control(by_key["DISTRICT_AREA_M2"], state),
                    row=2, column=2,
                ),
                form_cell(
                    field_control(by_key["OBSERVATION_TIME"], state),
                    row=3, column=2,
                    class_name="konfig-project-duration-cell",
                ),
                form_cell(
                    field_control(by_key["INTEREST_RATE"], state),
                    row=4, column=2,
                ),
                form_cell(
                    form_action_field(
                        "Microgrid erstellen",
                        button_id="konfig-project-next",
                        status_id="konfig-project-error",
                    ),
                    row=5, column=1, column_span=2,
                    class_name="konfig-form-action-cell",
                ),
            ],
            columns=2,
            layout_profile="microgrid_start",
            class_name="konfig-project-data-grid",
        )]
    else:
        children = [
            html.Div(
                className="konfig-dialog-heading",
                children=[
                    html.H2(SECTION_TITLES["location"]),
                    html.P("Standort und wirtschaftlicher Rahmen des Projekts."),
                ],
            ),
            location_card,
            field_grid(visible_fields, state),
            form_grid(
                [form_cell(
                    form_action_field(
                        "Weiter",
                        button_id="konfig-project-next",
                        status_id="konfig-project-error",
                        variant="primary",
                    ),
                    row=1, column=1,
                    class_name="konfig-form-action-cell",
                )],
                columns=1,
                class_name="konfig-form-action-grid",
            ),
        ]
    return html.Div(
        className=(
            "konfig-project-form konfig-project-form--landing"
            if embedded else "konfig-project-form"
        ),
        children=children,
    )


# Erzeugt das zentral gerasterte Formular zum Laden eines Szenarios.
def scenario_load_form(scenario_rows: list[Any]) -> html.Div:
    return html.Div(
        className="konfig-load-form",
        children=form_grid(
            [
                form_cell(
                    html.Div(
                        scenario_rows,
                        id="konfig-scenario-list",
                        className="konfig-scenario-list",
                    ),
                    row=1,
                    column=1,
                    class_name="konfig-load-scenarios-cell",
                ),
                form_cell(
                    form_action_field(
                        "Szenario laden",
                        button_id="konfig-load-project",
                        status_id="konfig-load-status",
                    ),
                    row=2,
                    column=1,
                    class_name="konfig-form-action-cell konfig-load-action-cell",
                ),
            ],
            columns=1,
            class_name="konfig-load-form-grid",
            layout_profile="scenario_load",
        ),
    )


