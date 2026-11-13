# Rendert gemeinsame Eingaben, Auswahlen und Aktionen für Formulare.

from __future__ import annotations

from typing import Any, Iterable

from dash import dcc, html

from heo.display.field_values import dependent_panel_hidden
from ui.components.action_buttons import action_button

FIELD_BASE_CLASS = "heo-field"


# Rendert eine Auswahl und alle davon abhängigen Formularbereiche.
def dependent_choice_controls(
    *,
    controller_id: Any,
    options: list[dict[str, Any]],
    value: Any,
    panels: Iterable[dict[str, Any]],
    controller_class_name: str = "konfig-radio",
) -> html.Div:
    dependent_panels = []
    for panel in panels:
        required_value = panel.get("when")
        dependent_panels.append(
            html.Div(
                panel.get("children"),
                id=panel.get("id"),
                className=panel.get("class_name", "konfig-dependent-fields"),
                hidden=dependent_panel_hidden(value, required_value),
                **{"data-conditional-panel": "true"},
            )
        )
    return html.Div(
        className=(
            "konfig-dependent-choice-controls "
            "konfig-conditional-field-scope"
        ),
        children=[
            dcc.RadioItems(
                id=controller_id,
                options=options,
                value=value,
                inline=False,
                className=controller_class_name,
            ),
            *dependent_panels,
        ],
    )



# Gemeinsame Struktur für klickbare Werte und Überschriften.
#
# Die Varianten unterscheiden sich nur durch ihre CSS-Klassen und optional
# durch eine dcc.Store-ID für tab-spezifische Callback-Zustände.
def editable_control(
    value: Any,
    input_component: Any,
    *,
    button_id: Any | None = None,
    state_id: Any | None = None,
    class_name: str = "",
    control_class: str = "konfig-editable-value",
    display_class: str = "konfig-editable-value-display",
    input_class: str = "konfig-editable-value-input",
    display_style: dict[str, Any] | None = None,
    direct_input: bool = True,
    title: str = "Wert bearbeiten",
) -> html.Div:
    classes = [control_class, "konfig-editable-control"]
    if direct_input:
        classes.append("konfig-editable-control--direct")
    if class_name:
        classes.append(class_name)
    input_classes = str(getattr(input_component, "className", "") or "").split()
    if input_class not in input_classes:
        input_classes.append(input_class)
    if "konfig-editable-control-input" not in input_classes:
        input_classes.append("konfig-editable-control-input")
    if f"{FIELD_BASE_CLASS}__input" not in input_classes:
        input_classes.append(f"{FIELD_BASE_CLASS}__input")
    input_component.className = " ".join(input_classes)
    button_properties = {
        "n_clicks": 0,
        "type": "button",
        "className": display_class,
        "title": title,
    }
    button_properties["className"] = " ".join((
        str(button_properties["className"]),
        f"{FIELD_BASE_CLASS}__value",
    ))
    if display_style is not None:
        button_properties["style"] = display_style
    elif direct_input:
        button_properties["style"] = {"display": "none"}
    if button_id is not None:
        button_properties["id"] = button_id
    children = [
        html.Button(str(value if value is not None else ""), **button_properties),
        input_component,
    ]
    if state_id is not None:
        children.append(dcc.Store(id=state_id, data=False))
    return html.Div(children, className=" ".join(classes))



# Bearbeitbare Überschrift als formatierter editable_control.
def editable_heading(
    value: str,
    *,
    button_id: Any,
    input_id: Any,
    state_id: Any,
    class_name: str = "",
    debounce: bool = False,
) -> html.Div:
    return editable_control(
        value,
        dcc.Input(
            id=input_id,
            value=value,
            type="text",
            debounce=debounce,
            className="konfig-input",
        ),
        button_id=button_id,
        state_id=state_id,
        class_name=class_name,
        control_class="konfig-editable-heading",
        display_class="konfig-editable-heading-button",
        input_class="konfig-editable-heading-input",
        display_style={"display": "none"},
        title="Namen ändern",
    )



# Wert-Variante des gemeinsamen editable_control.
def editable_value(
    value: Any,
    input_component: Any,
    *,
    class_name: str = "",
    title: str = "Wert bearbeiten",
    direct_input: bool = True,
) -> html.Div:
    return editable_control(
        value,
        input_component,
        class_name=class_name,
        title=title,
        direct_input=direct_input,
    )



# Verbindet einen Auswahlbutton mit dem übergebenen Inhalt und markiert die Auswahl.
def selection_field(
    content: Any,
    *,
    selected: bool,
    selection_id: Any,
    selection_title: str,
    class_name: str = "",
) -> html.Div:
    classes = ["konfig-selection-field", "konfig-scenario-choice"]
    if selected:
        classes.append("is-selected")
    if class_name:
        classes.append(class_name)
    return html.Div(
        [
            html.Button(
                html.Span(
                    "",
                    className=(
                        "konfig-scenario-radio is-selected"
                        if selected else "konfig-scenario-radio"
                    ),
                ),
                id=selection_id,
                n_clicks=0,
                type="button",
                className="konfig-scenario-select-button",
                title=selection_title,
                **{"aria-pressed": "true" if selected else "false"},
            ),
            content,
        ],
        className=" ".join(classes),
    )



# Szenarioauswahl mit Auswahlkreis und editierbarem Namen.
def scenario_choice_rows(
    scenarios: Iterable[dict[str, Any]],
    *,
    selected: str | None = None,
    editing: str | None = None,
    deleting: str | None = None,
) -> list[html.Div]:
    rows: list[html.Div] = []
    for item in scenarios:
        name = str(item["name"])
        display_name = str(item.get("display_name") or name)
        is_selected = name == selected
        delete_open = name == deleting
        choice = selection_field(
            editable_value(
                display_name,
                dcc.Input(
                    id={"type": "konfig-scenario-name-input", "name": name},
                    value=display_name,
                    type="text",
                    debounce=False,
                    className="konfig-scenario-name-input",
                ),
                class_name="konfig-scenario-name-editor",
                title="Szenarionamen bearbeiten",
            ),
            selected=is_selected,
            selection_id={"type": "konfig-scenario-choice", "name": name},
            selection_title=f"Szenario {display_name} auswählen",
        )
        rows.append(html.Div(
            [
                choice,
                action_button(
                    "check",
                    {"type": "konfig-confirm-scenario-name", "name": name},
                    class_name="konfig-scenario-check",
                    title=f"Szenarionamen {display_name} übernehmen",
                ),
                action_button(
                    "duplicate",
                    {"type": "konfig-copy-scenario", "name": name},
                    class_name="konfig-scenario-copy",
                    title=f"Szenario {display_name} duplizieren",
                ),
                html.Div(
                    className="konfig-scenario-delete-control",
                    children=action_button(
                        "trash",
                        {"type": "konfig-delete-scenario", "name": name},
                        class_name="konfig-scenario-delete",
                        title=f"Löschoptionen für Szenario {display_name} anzeigen",
                        hidden=delete_open,
                    ),
                ),
            ],
            className="konfig-scenario-row" + (" is-delete-open" if delete_open else ""),
        ))
    return rows



# Bearbeitbare Überschrift als reguläres zentrales Formularfeld.
def form_heading_field(
    value: str,
    *,
    button_id: Any,
    input_id: Any,
    state_id: Any,
    class_name: str = "",
) -> html.Div:
    classes = ["konfig-form-heading-field"]
    if class_name:
        classes.append(class_name)
    return html.Div(
        editable_heading(
            value,
            button_id=button_id,
            input_id=input_id,
            state_id=state_id,
            class_name="konfig-form-editable-heading",
        ),
        className=" ".join(classes),
    )



# Zentraler, mittig ausgerichteter Aktionsbutton für Formulare.
def form_action_field(
    label: str,
    *,
    button_id: Any,
    status_id: Any | None = None,
    variant: str = "secondary",
    class_name: str = "",
) -> html.Div:
    classes = ["konfig-form-action-field"]
    if class_name:
        classes.append(class_name)
    button_classes = [f"konfig-{variant}-button", "konfig-form-action-button"]
    children = [
        html.Button(label, id=button_id, n_clicks=0, className=" ".join(button_classes))
    ]
    if status_id is not None:
        children.append(html.Div(id=status_id, className="konfig-inline-status"))
    return html.Div(children, className=" ".join(classes))

