# Rendert wiederverwendbare Formular- und Gebäudefelder des Konfigurators.

from __future__ import annotations

import json
from typing import Any

from dash import dcc, html

from ui.components.form_context import DEFAULT_FORM_CONTEXT, FormRenderContext

from heo.model.annual_series import ANNUAL_KEYS, series_view
from heo.display.form_content import FormItem, plan_form_content, range_is_enabled
from heo.display.field_presentation import (
    FieldPresentation,
    parameter_field_presentation,
    parameter_number_kind,
    range_parameter_noun,
    range_parameter_label,
)
from ui.components.form_overlay import (
    angle_editor,
    form_value_field,
    unit_badge,
    visible_parameter_unit,
)
from ui.components.form_grid import (
    automatic_form_grid,
)
from ui.components.form_controls import (
    dependent_choice_controls,
    editable_value,
)
from heo.display.field_values import (
    month_day_from_day_of_year,
    parameter_angle_kind,
    NUMERIC_VALUE_TYPES,
    parameter_choice_options,
    parameter_unit,
)
from heo.display.number_format import NumberKind, format_german_number
from heo.display.units import building_unit_key
from heo.display.parameter_dialog_layout import CENTRAL_ANGLE_FIELD_KEYS

RANGE_PAIR_KEY_SEPARATOR = "|"


# Liest einen Feldwert aus dem Konfiguratorzustand mit Katalogvorgabe.
def field_value(state: dict[str, Any], field: dict[str, Any]) -> Any:
    key = field.get("input_key") or field["env_key"]
    values = (state or {}).get("values", {})
    defaults = (state or {}).get("defaults", {})
    return values.get(key, defaults.get(key, field.get("default")))


# Formatiert editierbare Zahlen mit deutscher Gruppierung.
def format_field_number(value: Any, field: dict[str, Any]) -> Any:
    return format_german_number(
        value,
        kind=parameter_number_kind(field),
        scale=float(field.get("display_scale") or 1.0),
        divisor=float(field.get("display_divisor") or 1.0),
    )


# Rendert eine Zahleneingabe mit einer ID aus dem übergebenen Formularbereich.
def _text_input(
    field: dict[str, Any], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    key = field.get("input_key") or field["env_key"]
    displayed = format_field_number(field_value(state, field), field)
    number_kind = parameter_number_kind(field)
    return editable_value(displayed, dcc.Input(
        id=render_context.control_id({"type": "konfig-field", "key": key}),
        type="text",
        value=displayed,
        debounce=True,
        inputMode="numeric" if number_kind == "integer" else "decimal",
        className=(
            "konfig-input konfig-number-input heo-number-input "
            f"heo-number-input--{number_kind}"
        ),
    ))


# Verbindet den Winkelparameter mit dem gemeinsamen Winkelfeld.
def _angle_field_control(
    field: dict[str, Any], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    key = field.get("input_key") or field["env_key"]
    kind = parameter_angle_kind(field) or "inclination"
    value = field_value(state, field)
    return form_value_field(
        parameter_field_presentation(
            field,
            label=str(field.get("label") or key),
            value=value,
            kind="full",
            column_span=2,
            help_text=str(field.get("help_text_de") or ""),
        ),
        angle_editor(
            component_id=render_context.control_id({"type": "konfig-field", "key": key}),
            value=value,
            kind=kind,
        ),
        class_name="konfig-field konfig-angle-field konfig-wide-field",
    )


# Fasst Aktivierung und Datumsfelder einer Saison zusammen.
def _period_field_control(
    item: FormItem, state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    """Rendert den geplanten Zeitraum mit seinen bestehenden Datums-IDs."""
    enabled = item.field
    start, end = (child.field for child in item.children)
    title = item.title
    enabled_key = enabled.get("input_key") or enabled["env_key"]
    start_key = start.get("input_key") or start["env_key"]
    end_key = end.get("input_key") or end["env_key"]
    period_control = dependent_choice_controls(
        controller_id=render_context.control_id({"type": "konfig-field", "key": enabled_key}),
        options=[
            {"label": "Berücksichtigen", "value": True},
            {"label": "Nicht berücksichtigen", "value": False},
        ],
        value=item.children_visible,
        controller_class_name="konfig-radio konfig-period-choice",
        panels=[
            {
                "id": render_context.control_id({"type": "konfig-dependent-fields", "key": enabled_key}),
                "when": True,
                "class_name": "konfig-period-dates",
                "children": [
                    html.Span("von", className="konfig-date-prefix"),
                    editable_value(
                        month_day_from_day_of_year(field_value(state, start)),
                        dcc.Input(
                                id=render_context.control_id({"type": "konfig-field", "key": start_key}),
                                type="text",
                                value=month_day_from_day_of_year(field_value(state, start)),
                                placeholder="TT.MM.",
                                debounce=True,
                                className="konfig-input konfig-month-day-input",
                            ),
                        class_name="konfig-period-date-editor",
                    ),
                    html.Span("bis", className="konfig-date-prefix"),
                    editable_value(
                        month_day_from_day_of_year(field_value(state, end)),
                        dcc.Input(
                                id=render_context.control_id({"type": "konfig-field", "key": end_key}),
                                type="text",
                                value=month_day_from_day_of_year(field_value(state, end)),
                                placeholder="TT.MM.",
                                debounce=True,
                                className="konfig-input konfig-month-day-input",
                            ),
                        class_name="konfig-period-date-editor",
                    ),
                ],
            }
        ],
    )
    return form_value_field(
        parameter_field_presentation(
            enabled,
            label=title,
            value="",
            kind="full",
            column_span=2,
            help_text=(
                f"Zeitraum, in dem die {title.lower()} berücksichtigt wird."
            ),
        ),
        period_control,
        class_name="konfig-field konfig-period-field",
    )


# Rendert den Aktivierungsschalter und seine abhängigen Parameter.
def _activation_field_control(
    item: FormItem, children: list[Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    """Verbindet den geplanten Schalter mit den bereits gerenderten Kindern."""
    enabled = item.field
    enabled_key = enabled.get("input_key") or enabled["env_key"]
    active = item.children_visible
    return form_value_field(
        parameter_field_presentation(
            enabled,
            label=item.title,
            value=active,
            kind="full",
            help_text=str(enabled.get("help_text_de") or ""),
        ),
        dependent_choice_controls(
                controller_id=render_context.control_id({"type": "konfig-field", "key": enabled_key}),
                options=[
                    {"label": "Berücksichtigen", "value": True},
                    {"label": "Nicht berücksichtigen", "value": False},
                ],
                value=active,
                controller_class_name="konfig-radio konfig-activation-choice",
                panels=[{
                    "id": render_context.control_id({"type": "konfig-dependent-fields", "key": enabled_key}),
                    "when": True,
                    "class_name": "konfig-dependent-fields",
                    "children": automatic_form_grid(
                        children,
                        class_name="konfig-field-grid",
                        keep_together=True,
                    ),
                }],
        ),
        class_name="konfig-field konfig-activation-field",
    )


# Rendert Jahreswerte und Stützjahre mit stabilen Feld-IDs.
def annual_series_control(
    field, state,
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
):
    key = field.get("input_key") or field["env_key"]
    try:
        mode, points, entries = series_view(state, key)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        return html.Div([html.Label(field.get("label", key)), str(exc)], className="konfig-field")
    indices = [-1] if mode == "constant" else points
    drafts = state.get("annual_drafts", {}).get(key)
    controls = []
    for i, (year, value) in enumerate(zip(indices, entries)):
        controls.append(html.Label([
            html.Span("Wert" if year == -1 else f"Jahr {year}"),
            dcc.Input(id=render_context.control_id({"type": "konfig-series-value", "key": key, "year": year}),
                      type="text", inputMode="decimal", debounce=True,
                      value=drafts[i] if drafts and len(drafts) == len(entries) else format_field_number(value, field),
                      className="konfig-input konfig-number-input"),
        ]))
    return form_value_field(
        parameter_field_presentation(
            field, label=field.get("label", key), value=entries, kind="choice",
            unit=parameter_unit(field),
        ),
        html.Div([
            dcc.RadioItems(id=render_context.control_id({"type": "konfig-series-mode", "key": key}),
                           options=[{"label": "konstant", "value": "constant"},
                                    {"label": "für Stützjahre", "value": "support"}],
                           value=mode, inline=True, className="konfig-radio"),
            html.Div(controls, className="konfig-series-values"),
            html.Small("Wert gilt ab dem Stützjahr bis zum nächsten Stützjahr." if mode == "support" else ""),
            html.Div(state.get("annual_errors", {}).get(key, ""), role="status", className="konfig-series-error"),
        ]), unit_component=visible_parameter_unit(field),
    )


# Rendert die Eingabe expliziter Stützjahre.
def support_years_control(
    field: dict[str, Any], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    raw = field_value(state, field)
    displayed = ", ".join(str(year) for year in raw) if isinstance(raw, (list, tuple)) else str(raw or "")
    control = form_value_field(
        parameter_field_presentation(
            field,
            label="Stützjahre",
            value=displayed,
            kind="text",
            help_text=str(field.get("help_text_de") or ""),
        ),
        editable_value(
            displayed,
            dcc.Input(
                id=render_context.control_id({"type": "konfig-field", "key": "INTERPOLATION_POINTS"}),
                type="text",
                value=displayed,
                placeholder="0, 5, 10, 15",
                debounce=True,
                className="konfig-input konfig-support-years-input",
            ),
        ),
        class_name="konfig-field konfig-support-years-field",
    )
    error = state.get("support_year_error")
    if error:
        control.children.append(html.Div(error, role="status", className="konfig-series-error"))
    return control


# Rendert die gewünschte Anzahl von Stützjahren.
def support_year_count_control(
    field: dict[str, Any], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    value = field_value(state, field)
    return form_value_field(
        parameter_field_presentation(
            field,
            label="Anzahl Stützjahre",
            value=value,
            kind="number",
            number_kind="integer",
            help_text=str(field.get("help_text_de") or ""),
        ),
        editable_value(
            "" if value is None else str(value),
            dcc.Input(
                id=render_context.control_id({"type": "konfig-field", "key": "NUM_INTERPOLATION_POINTS"}),
                type="text",
                inputMode="numeric",
                value="" if value is None else str(value),
                placeholder="optional",
                debounce=True,
                className="konfig-input konfig-number-input heo-number-input--integer",
            ),
        ),
        unit_component=visible_parameter_unit(field),
    )


# Wählt den passenden Editor für einen Katalogparameter.
def field_control(
    field: dict[str, Any], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    key = field.get("input_key") or field["env_key"]
    if key == "INTERPOLATION_POINTS":
        return support_years_control(field, state, render_context=render_context)
    if key == "NUM_INTERPOLATION_POINTS":
        return support_year_count_control(field, state, render_context=render_context)
    if key in ANNUAL_KEYS:
        return annual_series_control(field, state, render_context=render_context)
    if key in CENTRAL_ANGLE_FIELD_KEYS:
        return _angle_field_control(field, state, render_context=render_context)
    value = field_value(state, field)
    value_type = str(field.get("value_type") or "str")
    if value_type in {"list", "dict"} and not isinstance(value, str) and not (
        value_type == "list" and isinstance(value, list) and len(value) == 1
    ):
        value = json.dumps(value, ensure_ascii=False)
    options = field.get("options") or []
    label = field.get("label") or key.replace("__", " · ").replace("_", " ").title()

    control_size = "text"
    if key == "OPTIMIZATION_FOCUS_MODE":
        control: Any = dcc.RadioItems(
            id=render_context.control_id({"type": "konfig-field", "key": key}),
            options=parameter_choice_options(field, value),
            value=value or "economic",
            inline=False,
            className="konfig-radio",
        )
        control_size = "choice"
    elif value_type == "bool":
        if key.endswith("FEASIBLE"):
            control = dcc.Checklist(
                id=render_context.control_id({"type": "konfig-field", "key": key}),
                options=[{"label": "Berücksichtigen", "value": "enabled"}],
                value=["enabled"] if bool(value) else [],
                className="konfig-check konfig-single-choice",
            )
        else:
            control = dcc.RadioItems(
                id=render_context.control_id({"type": "konfig-field", "key": key}),
                options=[
                    {"label": "Ja", "value": True},
                    {"label": "Nein", "value": False},
                ],
                value=bool(value),
                inline=False,
                className="konfig-radio konfig-binary-choice",
            )
        control_size = "choice"
    elif options:
        control = dcc.RadioItems(
            id=render_context.control_id({"type": "konfig-field", "key": key}),
            options=parameter_choice_options(field, value),
            value=value,
            inline=False,
            className="konfig-radio konfig-option-choice",
        )
        control_size = "choice"
    elif value_type in NUMERIC_VALUE_TYPES or (
        value_type == "list" and isinstance(value, list) and len(value) == 1
    ):
        control = _text_input(field, state, render_context=render_context)
        control_size = "number"
    else:
        control = editable_value(value, dcc.Input(
            id=render_context.control_id({"type": "konfig-field", "key": key}),
            type="text",
            value=value,
            debounce=True,
            className="konfig-input",
        ), direct_input=key != "SCENARIO_NAME")

    return form_value_field(
        parameter_field_presentation(
            field,
            label=label,
            value=value,
            kind=control_size,
            number_kind=parameter_number_kind(field) if control_size == "number" else None,
            unit=parameter_unit(field, field_value(state, field)),
            help_text=str(field.get("help_text_de") or ""),
        ),
        control,
        unit_component=visible_parameter_unit(field, field_value(state, field)),
    )


# Rendert ein zusammengehöriges Minimum-Maximum-Paar.
def _range_parameter_control(
    item: FormItem, state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    """Rendert das geplante Grenzwertpaar mit dem gespeicherten Freigabezustand."""
    minimum, maximum = (child.field for child in item.children)
    minimum_key = str(minimum.get("input_key") or minimum["env_key"])
    maximum_key = str(maximum.get("input_key") or maximum["env_key"])
    pair_key = RANGE_PAIR_KEY_SEPARATOR.join((minimum_key, maximum_key))
    enabled = item.children_visible
    dependent_fields = []
    for child in item.children:
        field = child.field
        dependent = dict(field)
        dependent["label"] = range_parameter_label(field)
        control = field_control(dependent, state, render_context=render_context)
        control.hidden = not child.visible
        setattr(control, "data-form-key", child.key)
        dependent_fields.append(control)
    return form_value_field(
        parameter_field_presentation(
            minimum,
            label=item.title,
            value=enabled,
            kind="full",
            help_text=(
                f"Legt fest, ob Mindest- und Maximalwert für "
                f"{range_parameter_noun(minimum).lower()} vorgegeben werden."
            ),
        ),
        dependent_choice_controls(
                controller_id=render_context.control_id({"type": "konfig-range-toggle", "key": pair_key}),
                options=[
                    {"label": "Ja", "value": True},
                    {"label": "Nein", "value": False},
                ],
                value=enabled,
                controller_class_name="konfig-radio konfig-activation-choice",
                panels=[{
                    "id": render_context.control_id({"type": "konfig-range-dependent", "key": pair_key}),
                    "when": True,
                    "class_name": "konfig-dependent-fields",
                    "children": automatic_form_grid(
                        dependent_fields,
                        class_name="konfig-field-grid konfig-range-value-grid",
                        keep_together=True,
                    ),
                }],
        ),
        class_name=(
            "konfig-field konfig-activation-field konfig-range-parameter"
        ),
    )


# Gruppiert zusammengehörige Parameter zu gemeinsamen Bedienelementen.
def parameter_controls(
    fields: list[dict[str, Any]], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> list[Any]:
    """Rendert den gemeinsamen Inhaltsplan mit unveränderten Callback-IDs."""
    plan = plan_form_content(
        fields, lambda field: field_value(state, field),
        range_enabled=lambda minimum, maximum: range_is_enabled(minimum, maximum, state or {}),
    )

    def render(item: FormItem) -> Any:
        """Wählt den vorhandenen Control-Baustein anhand des geplanten Inhalts."""
        if item.kind == "period":
            control = _period_field_control(
                item, state, render_context=render_context,
            )
        elif item.kind == "activation":
            control = _activation_field_control(
                item, [render(child) for child in item.children],
                render_context=render_context,
            )
        elif item.kind == "range":
            control = _range_parameter_control(
                item, state, render_context=render_context,
            )
        else:
            control = field_control(item.field, state, render_context=render_context)
        setattr(control, "data-form-key", item.key)
        setattr(control, "data-form-group-kind", item.kind)
        if not item.visible:
            control.hidden = True
        return control

    return [render(item) for item in plan.items]


# Ordnet Parameterfelder im gemeinsamen Formularraster an.
def field_grid(
    fields: list[dict[str, Any]], state: dict[str, Any],
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    return automatic_form_grid(parameter_controls(fields, state, render_context=render_context), class_name="konfig-field-grid")


# Rendert einen Gebäudewert im übergebenen Formularbereich.
def building_input(
    uid: int, field: str, label: str, value: Any, input_type: str,
    unit: str = "", *, number_kind: NumberKind = "decimal",
    group_thousands: bool = True,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    unit_component = unit_badge(unit) if unit else None
    displayed = (
        format_german_number(
            value, kind=number_kind, group_thousands=group_thousands,
        )
        if input_type == "number" else value
    )
    input_component = dcc.Input(
        id=render_context.control_id({"type": "konfig-building-field", "uid": uid, "field": field}),
        # Browser-Spinner erzeugen bei Zahlfeldern zusätzliche +-Buttons und
        # weichen von den zentralen editierbaren Formularfeldern ab.
        type="text" if input_type == "number" else input_type,
        inputMode=(
            "numeric" if input_type == "number" and number_kind == "integer"
            else "decimal" if input_type == "number" else None
        ),
        value=displayed,
        debounce=True,
        className=(
            "konfig-input konfig-number-input heo-number-input "
            f"heo-number-input--{number_kind}"
            + ("" if group_thousands else " heo-number-input--ungrouped")
            if input_type == "number" else "konfig-input"
        ),
    )
    return form_value_field(
        FieldPresentation(
            label=label,
            value=str(displayed if displayed is not None else ""),
            unit=unit,
            parameter_key=building_unit_key(uid, field),
            numeric_value=float(value) if input_type == "number" and isinstance(value, (int, float)) else None,
            editable=True,
            kind="number" if input_type == "number" else "text",
            number_kind=number_kind if input_type == "number" else None,
        ),
        editable_value(displayed, input_component),
        unit_component=unit_component,
    )


# Rendert ein Winkelfeld für ein bestimmtes Gebäude.
def building_angle_input(
    uid: int, field: str, label: str, value: Any, *, kind: str,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    return form_value_field(
        FieldPresentation(
            label=label,
            value=str(value if value is not None else ""),
            editable=True,
            kind="full",
            column_span=2,
        ),
        angle_editor(
                component_id=render_context.control_id({
                    "type": "konfig-building-field", "uid": uid, "field": field,
                }),
                value=value,
                kind=kind,
        ),
        class_name="konfig-field konfig-angle-field konfig-wide-field",
    )


# Rendert die Auswahlmöglichkeiten eines Gebäudefelds.
def building_dropdown(
    uid: int,
    field: str,
    label: str,
    options: list[dict[str, Any]],
    value: Any,
    *,
    category: str | None = None,
    column_span: int = 1,
    class_name: str = "",
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    field_key = f"{field}@{category}" if category else field
    component_id = {
        "type": "konfig-building-field", "uid": uid, "field": field_key,
    }
    return form_value_field(
        FieldPresentation(
            label=label, value=str(value), editable=True, kind="choice",
            column_span=column_span,
        ),
        dcc.RadioItems(
                id=render_context.control_id(component_id),
                options=options,
                value=value,
                inline=False,
                className="konfig-radio konfig-option-choice",
        ),
        class_name=" ".join(filter(None, ("konfig-field", class_name))),
    )


# Rendert eine binäre Gebäudeauswahl.
def building_binary_choice(
    uid: int, field: str, label: str, enabled: bool,
    *, render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    return form_value_field(
        FieldPresentation(
            label=label, value=str(enabled), editable=True, kind="choice",
        ),
        dcc.RadioItems(
                id=render_context.control_id({"type": "konfig-building-field", "uid": uid, "field": field}),
                options=[
                    {"label": "Berücksichtigen", "value": 1},
                    {"label": "Nicht berücksichtigen", "value": 0},
                ],
                value=1 if enabled else 0,
                inline=False,
                className="konfig-radio konfig-option-choice",
        ),
    )
