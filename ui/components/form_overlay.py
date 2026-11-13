# Rendert Parameterfelder, Winkelgrafiken und statische Ergebnis-Einblendungen.
# Feldregeln kommen aus heo/display; Eingaben und Raster aus den UI-Nachbarmodulen.

from __future__ import annotations

from typing import Any, Callable, Iterable, Literal

from dash import dcc, html

from heo.display.number_format import format_german_number
from heo.display.form_content import FormItem, plan_form_content
from heo.display.units import unit_display
from heo.display.field_presentation import (
    FieldPresentation, parameter_field_presentation, range_parameter_label,
)
from heo.display.field_values import (
    month_day_from_day_of_year, numeric_angle, parameter_angle_kind,
    parameter_choice_options, parameter_unit, readonly_parameter_presentation,
)
from ui.components.form_controls import FIELD_BASE_CLASS, editable_value
from ui.components.form_grid import FIELD_CELL_CLASS, automatic_form_grid, form_grid
from ui.components.units import selectable_unit, unit_attributes, unit_editor_inputs


OVERLAY_GRID_CLASS = "topology-overlay-grid"
OVERLAY_CELL_CLASS = "topology-overlay-cell"
OVERLAY_FIELD_CLASS = "topology-overlay-field"
OVERLAY_SECTION_CLASS = "topology-overlay-section"
FORM_FIELD_CLASS = "konfig-parameter-field"
FORM_CONTROL_CLASS = "konfig-parameter-control"


# Rendert einfache und gebrochene Einheiten in allen Formularansichten.
def unit_badge(unit: str) -> html.Span:
    text = str(unit).strip()
    badge = selectable_unit(text)
    if "/" not in text:
        return badge
    numerator, _, denominator = text.partition("/")
    denominator = denominator.strip()
    if denominator.startswith("(") and denominator.endswith(")"):
        denominator = denominator[1:-1].strip()
    badge.children = [
            html.Span(numerator.strip(), className="konfig-unit-numerator"),
            html.Span("", className="konfig-unit-fraction-line"),
            html.Span(denominator, className="konfig-unit-denominator"),
        ]
    badge.className += " konfig-unit-fraction"
    badge.title = text
    return badge


# Liefert den gemeinsamen Einheitenbaustein eines Parameters.
def visible_parameter_unit(field: dict[str, Any], value: Any = None) -> Any:
    unit = parameter_unit(field, value)
    return unit_badge(unit) if unit else None


# Gemeinsame Winkelgrafik für Dialoge und statische Projektformulare.
#
# Begrenzt den Wert auf den zulässigen Winkelbereich und baut je nach Winkelart
# eine Kompass- oder Neigungsgrafik auf. Ergänzt eine editierbare Zahleneingabe
# oder einen statischen Zahlenwert.
def angle_editor(
    *,
    value: Any,
    kind: str,
    component_id: Any | None = None,
    editable: bool = True,
) -> html.Div:
    orientation = kind == "orientation"
    minimum, maximum = ((-180.0, 180.0) if orientation else (0.0, 90.0))
    angle = numeric_angle(value, minimum, maximum)
    pointer_angle = angle + (180.0 if orientation else 0.0)
    if orientation:
        graphical_children = [
            html.Span(className="konfig-compass-rose"),
            html.Span("N", className="konfig-angle-mark konfig-angle-mark--north"),
            html.Span("O", className="konfig-angle-mark konfig-angle-mark--east"),
            html.Span("S", className="konfig-angle-mark konfig-angle-mark--south"),
            html.Span("W", className="konfig-angle-mark konfig-angle-mark--west"),
            html.Span(
                [
                    html.Span(className="konfig-angle-needle-tip konfig-angle-needle-tip--red"),
                    html.Span(className="konfig-angle-needle-tip konfig-angle-needle-tip--blue"),
                ],
                className="konfig-angle-needle",
            ),
            html.Span(className="konfig-angle-center"),
        ]
    else:
        graphical_children = [
            html.Span(className="konfig-inclination-sun"),
            html.Span(className="konfig-inclination-ground"),
            html.Span(className="konfig-inclination-left-post"),
            html.Span(className="konfig-inclination-right-post"),
            html.Span(className="konfig-inclination-module"),
            html.Span(className="konfig-angle-center konfig-inclination-pivot"),
            html.Span("0°", className="konfig-inclination-label konfig-inclination-label--zero"),
            html.Span("90°", className="konfig-inclination-label konfig-inclination-label--ninety"),
        ]
    dial_properties: dict[str, Any] = {
        "className": f"konfig-angle-dial konfig-angle-dial--{kind}",
        "style": {"--konfig-angle": f"{pointer_angle:g}deg"},
        "role": "slider" if editable else "img",
        "aria-label": "Ausrichtung" if orientation else "Neigungswinkel",
        "aria-valuemin": minimum,
        "aria-valuemax": maximum,
        "aria-valuenow": angle,
        "data-angle-kind": kind,
        "data-angle-min": minimum,
        "data-angle-max": maximum,
    }
    if editable:
        dial_properties["tabIndex"] = 0
    if editable:
        number_control: Any = editable_value(
            format_german_number(angle, kind="decimal"),
            dcc.Input(
                id=component_id,
                type="text",
                value=format_german_number(angle, kind="decimal"),
                debounce=True,
                inputMode="decimal",
                className="konfig-input konfig-number-input konfig-angle-input",
            ),
        )
    else:
        number_control = html.Strong(
            format_german_number(angle, kind="decimal"),
            className="konfig-readonly-value heo-field__value",
        )
    return html.Div(
        [
            html.Div(graphical_children, **dial_properties),
            html.Div(
                [number_control, unit_badge("°")],
                className="konfig-angle-number",
            ),
        ],
        className=(
            "konfig-angle-editor"
            if editable else "konfig-angle-editor konfig-angle-editor--readonly"
        ),
    )


# Statische Variante der Radioauswahl aus den Parameterdialogen.
def readonly_choice_control(
    options: Iterable[tuple[str, Any]], selected: Any,
    *, presentation: Literal["radio", "text"] = "radio",
) -> html.Div:
    choices = list(options)
    visible = next(
        ((label, value) for label, value in choices if value == selected),
        (str(selected), selected),
    )
    if presentation == "text":
        return html.Div(
            [html.Div(
                html.Strong(visible[0], className=f"{FIELD_BASE_CLASS}__value"),
                className="konfig-readonly-choice-option is-selected",
            )],
            className="konfig-radio konfig-readonly-choice",
        )
    if presentation != "radio":
        raise ValueError(f"Unbekannte Auswahldarstellung: {presentation}")
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "",
                        className=(
                            "konfig-readonly-radio is-selected"
                            if value == selected else "konfig-readonly-radio"
                        ),
                    ),
                    html.Span(label),
                ],
                className=(
                    "konfig-readonly-choice-option is-selected"
                    if value == selected else "konfig-readonly-choice-option"
                ),
            )
            for label, value in [visible]
        ],
        className="konfig-radio konfig-readonly-choice",
    )


# Rendert ein Katalogfeld mit exakt denselben Typregeln wie ein Dialog.
def readonly_parameter_control(
    field: dict[str, Any], value: Any,
    *, choice_presentation: Literal["radio", "text"] = "radio",
) -> html.Div:
    presentation = readonly_parameter_presentation(field, value)
    angle_kind = parameter_angle_kind(field)
    if angle_kind:
        presentation = parameter_field_presentation(
            field,
            label=presentation.label,
            value=value,
            kind="full",
            editable=False,
            column_span=2,
            help_text=presentation.help_text,
        )
        return form_value_field(
            presentation,
            angle_editor(value=value, kind=angle_kind, editable=False),
            class_name="konfig-field konfig-angle-field konfig-wide-field",
            use_control_when_readonly=True,
        )

    value_type = str(field.get("value_type") or "str")
    labels = field.get("option_labels_de") or {}
    control = None
    if isinstance(value, (list, dict)):
        control = None
    elif value_type == "bool":
        control = readonly_choice_control(
            (("Ja", True), ("Nein", False)), bool(value),
            presentation=choice_presentation,
        )
    elif field.get("options") or labels:
        options = parameter_choice_options(field, value)
        control = readonly_choice_control(
            ((item["label"], item["value"]) for item in options), value,
            presentation=choice_presentation,
        )
    return form_value_field(
        presentation,
        control,
        unit_component=visible_parameter_unit(field, value),
        use_control_when_readonly=control is not None,
    )


def readonly_grouped_parameter_controls(
    fields: Iterable[dict[str, Any]],
    value_getter: Callable[[dict[str, Any]], Any],
    *,
    activation_groups: dict[str, dict[str, Any]] | None = None,
    control_renderer: Callable[[dict[str, Any], Any], html.Div] | None = None,
    choice_presentation: Literal["radio", "text"] = "radio",
) -> list[html.Div]:
    """Rendert denselben Inhaltsplan wie das editierbare Parameterformular."""
    if control_renderer is None:
        # Reicht die gewünschte Darstellung auch an ungruppierte Felder weiter.
        def control_renderer(field, value):
            return readonly_parameter_control(
                field, value, choice_presentation=choice_presentation,
            )
    plan = plan_form_content(fields, value_getter, activation_groups=activation_groups)

    def render(item: FormItem) -> html.Div:
        """Erzeugt Felder und innere Boxen aus den geplanten Beziehungen."""
        field = item.field
        if item.kind == "field":
            control = control_renderer(field, value_getter(field))
        elif item.kind == "range":
            # Ergebnisdaten enthalten Grenzwerte, aber keinen editierbaren
            # Freigabeschalter. Beide Werte bleiben in derselben inneren Box.
            values = []
            for child in item.children:
                labelled = {**child.field, "label": range_parameter_label(child.field)}
                value = control_renderer(labelled, value_getter(child.field))
                value.hidden = not child.visible
                setattr(value, "data-form-key", child.key)
                values.append(value)
            control = form_value_field(
                parameter_field_presentation(
                    field, label=item.title.removesuffix(" begrenzen"), value="",
                    kind="full", editable=False,
                ),
                automatic_form_grid(values, keep_together=True, class_name="konfig-field-grid"),
                class_name="konfig-field konfig-range-parameter",
                use_control_when_readonly=True,
            )
        else:
            active = item.children_visible
            title = item.title
            if item.kind == "period":
                start, end = (child.field for child in item.children)
                dependent_content: Any = html.Div(
                    [
                        html.Span("von", className="konfig-date-prefix"),
                        html.Strong(
                            month_day_from_day_of_year(value_getter(start)),
                            className="konfig-readonly-date",
                        ),
                        html.Span("bis", className="konfig-date-prefix"),
                        html.Strong(
                            month_day_from_day_of_year(value_getter(end)),
                            className="konfig-readonly-date",
                        ),
                    ],
                    className="konfig-period-dates",
                    hidden=not active,
                )
                control_class = "konfig-field konfig-period-field"
                help_text = f"Zeitraum, in dem die {title.lower()} berücksichtigt wird."
            else:
                dependent_content = automatic_form_grid(
                    [render(child) for child in item.children],
                    class_name="konfig-field-grid konfig-dependent-fields",
                    keep_together=True,
                )
                dependent_content.hidden = not active
                control_class = "konfig-field konfig-activation-field"
                help_text = str(field.get("help_text_de") or "")
            presentation = parameter_field_presentation(
                field,
                label=title,
                value=active,
                kind="full",
                editable=False,
                column_span=2,
                help_text=help_text,
            )
            control = form_value_field(
                presentation,
                html.Div(
                    [
                        readonly_choice_control(
                            (("Ja", True), ("Nein", False)) if choice_presentation == "text"
                            else (("Berücksichtigen", True), ("Nicht berücksichtigen", False)),
                            active, presentation=choice_presentation,
                        ),
                        dependent_content,
                    ],
                    className="konfig-dependent-choice-controls",
                ),
                class_name=control_class,
                use_control_when_readonly=True,
            )
        setattr(control, "data-form-key", item.key)
        setattr(control, "data-form-group-kind", item.kind)
        if not item.visible:
            control.hidden = True
        return control

    return [render(item) for item in plan.items]


# Rendert ein Ergebnisfeld mit denselben Größenmetadaten wie ein Eingabefeld.
def readonly_field_component(field: FieldPresentation) -> html.Div:
    displayed, selected = (
        unit_display(field.numeric_value, field.unit or "")
        if field.numeric_value is not None else (field.value, field.unit)
    )
    return html.Div(
        className=f"{OVERLAY_CELL_CLASS} {FIELD_CELL_CLASS}",
        **{
            "data-field-column-span": field.column_span,
            "data-field-row-span": field.row_span,
            "data-form-column-span": field.column_span,
            "data-form-row-span": field.row_span,
        },
        children=html.Div(
            className=(
                f"{OVERLAY_FIELD_CLASS} {FIELD_BASE_CLASS} "
                f"{FIELD_BASE_CLASS}--readonly {FIELD_BASE_CLASS}--{field.kind}"
            ),
            **{
                "data-editable": "false",
                "data-field-kind": field.kind,
                **unit_attributes(field.parameter_key, field.unit, field.numeric_value),
            },
            children=[
                html.Span(
                    field.label,
                    className=(
                        "topology-overlay-field-label "
                        f"{FIELD_BASE_CLASS}__label"
                    ),
                ),
                html.Span(
                    className=(
                        "topology-overlay-field-control "
                        f"{FIELD_BASE_CLASS}__control"
                    ),
                    children=[
                        html.Strong(
                            displayed,
                            className=(
                                "topology-overlay-field-value "
                                f"{FIELD_BASE_CLASS}__value heo-unit-value"
                            ),
                        ),
                        selectable_unit(selected, class_name=(
                            "topology-overlay-field-unit konfig-unit "
                            f"{FIELD_BASE_CLASS}__unit"
                        )) if selected else None,
                    ],
                ),
                html.Small(
                    field.help_text,
                    className=f"{FIELD_BASE_CLASS}__help",
                ) if field.help_text else None,
            ],
        ),
    )


# Rendert eine Folge statischer Ergebnisfelder als Dash-Raster.
def readonly_fields_component(
    fields: Iterable[FieldPresentation],
    *,
    class_name: str = OVERLAY_GRID_CLASS,
) -> html.Div:
    return form_grid(
        [readonly_field_component(field) for field in fields], class_name=class_name,
    )


# Zentraler Label-/Wert-/Einheit-Baustein für editierbare Formulare.
#
# field ist die einzige Quelle für Editierbarkeit, Feldart, Hilfetext und
# Zellspannweite. Overlay-KPIs verwenden dieselbe Beschreibung mit
# editable=False über readonly_field_component.
def form_value_field(
    field: FieldPresentation,
    control: Any | None = None,
    *,
    class_name: str = "konfig-field",
    unit_component: Any | None = None,
    use_control_when_readonly: bool = False,
) -> html.Div:
    unit_data = (
        unit_attributes(field.parameter_key, field.unit, field.numeric_value)
        if field.kind == "number" or (field.kind == "choice" and field.unit) else {}
    )
    displayed, selected = (
        unit_display(field.numeric_value, field.unit or "")
        if field.numeric_value is not None else (field.value, field.unit)
    )
    unit = None
    if field.unit and field.kind in {"number", "choice"}:
        if field.numeric_value is not None:
            unit = unit_badge(selected)
        else:
            unit = unit_component if unit_component is not None else unit_badge(selected)
    if unit is not None:
        unit_classes = str(getattr(unit, "className", "") or "").split()
        if f"{FIELD_BASE_CLASS}__unit" not in unit_classes:
            unit_classes.append(f"{FIELD_BASE_CLASS}__unit")
        unit.className = " ".join(unit_classes)
    rendered_control = control
    if field.editable:
        if rendered_control is None:
            raise ValueError("Editierbare Felder benötigen ein Control.")
        if unit_data:
            rendered_control = unit_editor_inputs(rendered_control, field.unit or "")
    elif rendered_control is None or not use_control_when_readonly:
        rendered_control = html.Strong(
            displayed,
            className=(
                "konfig-readonly-value "
                f"{FIELD_BASE_CLASS}__value heo-unit-value"
            ),
        )
    field_classes = [
        *str(class_name or "").split(),
        FORM_FIELD_CLASS,
        FIELD_BASE_CLASS,
        f"{FIELD_BASE_CLASS}--{'editable' if field.editable else 'readonly'}",
        f"{FIELD_BASE_CLASS}--{field.kind}",
    ]
    control_classes = [
        "konfig-field-control",
        FORM_CONTROL_CLASS,
        f"{FORM_CONTROL_CLASS}--{field.kind}",
        f"{FIELD_BASE_CLASS}__control",
    ]
    return html.Div(
        className=" ".join(dict.fromkeys(field_classes)),
        **{
            "data-editable": "true" if field.editable else "false",
            "data-field-kind": field.kind,
            "data-field-column-span": field.column_span,
            "data-field-row-span": field.row_span,
            "data-number-kind": field.number_kind or "",
            **unit_data,
        },
        children=[
            html.Label(field.label, className=f"{FIELD_BASE_CLASS}__label"),
            html.Div(
                className=" ".join(control_classes),
                children=[rendered_control, unit],
            ),
            html.Small(
                field.help_text,
                className=f"konfig-help {FIELD_BASE_CLASS}__help",
            ),
        ],
    )
