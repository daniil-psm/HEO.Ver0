# Baut die Geräte-, Netz- und Gebäudeparameterdialoge des Konfigurators.

from __future__ import annotations

from typing import Any

from dash import dcc, html

from ui.components.form_context import DEFAULT_FORM_CONTEXT, FormRenderContext

from dg_adapter.input.parameter_catalog import (
    field_spec,
    fields_by_keys,
    fields_for_device,
    fields_for_section,
)
from heo.display.device_labels import (
    building_category_label,
    building_type_label,
    catalog_display_name,
    decentral_device_name,
    ev_charging_label,
)
from heo.display.parameter_dialog_layout import (
    BUILDING_ECO_FIELDS,
    BUILDING_PARAMETER_DIALOG_FIELDS,
    COOLING_PERIOD_FIELDS,
    COOL_NETWORK_FIELDS,
    DECENTRAL_HEAT_PUMP_PARAMETER_DIALOG_FIELDS,
    HEATING_PERIOD_FIELDS,
    HEAT_NETWORK_FIELDS,
    POWER_SHARED_FIELDS,
    RESOURCE_ECO_FIELDS,
    SHARED_NETWORK_FIELDS,
    building_parameter_visible,
    parameter_dialog_view,
    split_parameter_dialog_fields,
)
from heo.display.project_info_data import DECENTRAL_ECO_FIELDS
from heo.model.building_types import EV_CHARGING_TYPES
from heo.model.buildings import CATEGORY_BUILDING_TYPES, building_category
from heo.model.devices import decentral_device_components
from heo.topology.definitions import CENTRAL_DEVICES, COLORS, EXTERNAL_SOURCE_CARRIERS
from ui.components.action_buttons import action_button
from ui.components.form_overlay import (
    OVERLAY_SECTION_CLASS,
    form_value_field,
)
from heo.display.field_presentation import (
    FieldPresentation,
    overlay_section,
)
from ui.components.form_grid import (
    automatic_form_grid,
)
from ui.components.form_controls import (
    editable_heading,
)

from .konfigurator_formfelder import (
    building_angle_input,
    building_binary_choice,
    building_dropdown,
    building_input,
    field_grid,
    parameter_controls,
)

# Teilt lokale Eingabefelder in Haupt- und Zusatzparameter auf.
def _split_local_controls(controls: list[tuple[str, Any]]) -> tuple[list[Any], list[Any]]:
    main = [control for key, control in controls if parameter_dialog_view(key) == "main"]
    more = [control for key, control in controls if parameter_dialog_view(key) == "more"]
    return main, more


# Liefert szenarioweite Katalogfelder für einen kontextspezifischen Dialogbereich.
def _shared_fields_for_dialog(
    layout: dict[str, str], view: str,
) -> list[dict[str, Any]]:
    return fields_by_keys([
        key for key, configured_view in layout.items()
        if configured_view == view
    ])


# Rendert weitere Dialogparameter mit explizitem Öffnungszustand.
def _advanced_section(
    content: Any,
    *,
    section_key: str,
    open_sections: dict[str, bool] | None = None,
    default_open: bool = False,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Details:
    section = overlay_section("Weitere Parameter", default_open=default_open)
    is_open = bool((open_sections or {}).get(section_key, section.default_open))
    return render_context.details(
        section.title, content, key="more", default_open=is_open,
        component_id={"type": "konfig-advanced-section", "key": section_key},
        class_name=f"konfig-advanced {OVERLAY_SECTION_CLASS}",
    )


# Ergänzt den Dialog bei Bedarf um weitere Parameter.
def _dialog_body_with_optional_advanced(
    main_content: list[Any],
    advanced_content: Any | None,
    *,
    section_key: str,
    open_sections: dict[str, bool] | None = None,
    default_open: bool = False,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> list[Any]:
    body = [item for item in main_content if item is not None]
    if advanced_content is not None:
        body.append(_advanced_section(
            advanced_content,
            section_key=section_key,
            open_sections=open_sections,
            default_open=default_open,
            render_context=render_context,
        ))
    return body


# Teilt Katalogfelder in Haupt- und Zusatzbereich auf.
def _sectioned_field_body(
    fields: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    section_key: str,
    open_sections: dict[str, bool] | None = None,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> list[Any]:
    main, more = split_parameter_dialog_fields(fields)
    return _dialog_body_with_optional_advanced(
        [field_grid(main, state, render_context=render_context)] if main else [],
        field_grid(more, state, render_context=render_context) if more else None,
        section_key=section_key,
        open_sections=open_sections,
        default_open=not main,
        render_context=render_context,
    )


# Baut die gemeinsame Hülle eines Parameterdialogs.
def _dialog_shell(
    title: Any,
    subtitle: str,
    body: list[Any],
    *,
    anchor: str,
    color: str,
    removable: bool = False,
    max_width: int | None = None,
) -> html.Div:
    actions = []
    if removable:
        actions.append(action_button(
            "trash",
            "konfig-dialog-remove-selected",
            class_name="konfig-dialog-trash-button",
            title="Komponente entfernen",
        ))
    actions.append(action_button(
        "close",
        "konfig-close-dialog",
        class_name="konfig-dialog-close-button",
        title="Parameterfenster schließen",
    ))
    return html.Div(
        className="konfig-inspector-shell",
        style={"--konfig-dialog-color": color},
        **{
            "data-konfig-anchor": anchor,
            "data-konfig-color": color,
        },
        children=[
            html.Button(
                "", id="konfig-dialog-dismiss", n_clicks=0,
                className="konfig-dialog-dismiss", tabIndex=-1,
                title="Parameterfenster schließen",
            ),
            html.Div(
                className="konfig-inspector-card glass-panel",
                **{
                    "data-form-layout-owner": "external",
                    **({"data-konfig-max-width": max_width} if max_width else {}),
                },
                children=[
                    html.Div(
                        className="konfig-inspector-header topology-overlay-header",
                        children=[
                            html.H2(title, className="topology-overlay-title")
                            if isinstance(title, str) else title,
                            *actions,
                        ],
                    ),
                    *body,
                ],
            ),
        ],
    )


# Blendet ein mehrfach angebotenes Feld nach seiner ersten Bearbeitung nur am Ursprung ein.
def _owned_fields(
    fields: list[dict[str, Any]], owner: str, field_owners: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        field for field in fields
        if not field_owners.get(str(field.get("input_key") or field["env_key"]))
        or field_owners.get(str(field.get("input_key") or field["env_key"])) == owner
    ]


# Rendert die Parameter für zentrale Geräte innerhalb der übergebenen Dialoghülle.
def _central_parameter_dialog(code, anchor, state, open_sections, render_context, dialog):
    fields = fields_for_device(code)
    if code == "PV":
        albedo = field_spec("ALBEDO")
        if albedo is not None:
            fields = [*fields, albedo]
    basic, advanced = split_parameter_dialog_fields(fields)
    carrier = next(iter(CENTRAL_DEVICES[code].get("inputs", ())), None)
    eco_fields = fields_by_keys(list(RESOURCE_ECO_FIELDS.get(carrier, ())))
    advanced = [*advanced, *eco_fields]
    body = _sectioned_field_body(
        [*basic, *advanced], state,
        section_key=anchor, open_sections=open_sections,
        render_context=render_context,
    )
    return dialog(
        CENTRAL_DEVICES[code]["full_name"], "", body, removable=True,
    )


# Rendert die Parameter für Netzanschlüsse innerhalb der übergebenen Dialoghülle.
def _grid_parameter_dialog(code, anchor, owners, state, open_sections, render_context, dialog):
    owner = "power_grid" if code == "GRID" else "power_bus"
    fields = _owned_fields(
        fields_by_keys(list(POWER_SHARED_FIELDS)), owner, owners,
    )
    return dialog(
        "Stromnetz",
        "",
        _sectioned_field_body(
            fields, state,
            section_key=anchor, open_sections=open_sections,
            render_context=render_context,
        ),
    )


# Rendert die Parameter für Ressourcen innerhalb der übergebenen Dialoghülle.
def _resource_parameter_dialog(code, anchor, state, open_sections, render_context, dialog):
    resource_code = code.split(":", 1)[0]
    carrier = EXTERNAL_SOURCE_CARRIERS.get(resource_code, "gas")
    return dialog(
        catalog_display_name(resource_code), "",
        _sectioned_field_body(
            fields_by_keys(list(RESOURCE_ECO_FIELDS[carrier])), state,
            section_key=anchor, open_sections=open_sections,
            render_context=render_context,
        ),
    )


# Rendert die Parameter für Versorgungsnetze innerhalb der übergebenen Dialoghülle.
def _network_parameter_dialog(code, anchor, owners, state, open_sections, render_context, dialog):
    cooling = code == "COOL_GRID"
    network_label = "Kältenetz" if cooling else "Wärmenetz"
    owner = "cool_network" if cooling else "heat_network"
    period_keys = COOLING_PERIOD_FIELDS if cooling else HEATING_PERIOD_FIELDS
    network_keys = COOL_NETWORK_FIELDS if cooling else HEAT_NETWORK_FIELDS
    period_fields = _owned_fields(fields_by_keys(list(period_keys)), owner, owners)
    shared_fields = _owned_fields(
        fields_by_keys(list(SHARED_NETWORK_FIELDS)), owner, owners,
    )
    fields = [
        *period_fields,
        *fields_by_keys(list(network_keys)),
        *shared_fields,
    ]
    return dialog(
        network_label,
        "",
        _sectioned_field_body(
            fields, state,
            section_key=anchor, open_sections=open_sections,
            render_context=render_context,
        ),
    )


# Rendert die Parameter für Lasten innerhalb der übergebenen Dialoghülle.
def _load_parameter_dialog(anchor, owners, state, open_sections, render_context, dialog):
    calendar = fields_for_section("calendar")
    duplicated_period_keys = set(HEATING_PERIOD_FIELDS + COOLING_PERIOD_FIELDS)
    periods = _owned_fields(
        [
            field for field in calendar
            if str(field.get("input_key") or field["env_key"]) in duplicated_period_keys
        ],
        "load",
        owners,
    )
    other_calendar = [
        field for field in calendar
        if str(field.get("input_key") or field["env_key"]) not in duplicated_period_keys
    ]
    return dialog(
        "Gebäude-Lasten",
        "",
        _sectioned_field_body(
            [
                *periods,
                *other_calendar,
                *fields_for_section("design_building"),
            ],
            state,
            section_key=anchor,
            open_sections=open_sections,
            render_context=render_context,
        ),
        max_width=900,
    )


# Rendert die Parameter für Gebäude innerhalb der übergebenen Dialoghülle.
def _building_parameter_dialog(code, anchor, state, building_state, open_sections, render_context, dialog):
    uid = int(code)
    row = next((item for item in (building_state or {}).get("rows", []) if int(item.get("uid", -1)) == uid), None)
    if row is None:
        return None
    category = building_category(row)
    category_options = [
        {"label": building_category_label(key), "value": key}
        for key in ("residential", "non_residential", "mixed")
    ]
    category_control = form_value_field(
        FieldPresentation(
            label="Nutzungsart", value=category,
            editable=True, kind="choice",
        ),
        dcc.RadioItems(
            id=render_context.control_id({
                "type": "konfig-building-field", "uid": uid,
                "field": "category",
            }),
            options=category_options,
            value=category,
            inline=False,
            className="konfig-radio konfig-building-category-choice",
        ),
        class_name="konfig-field konfig-building-category-control",
    )
    building_options = [
        {"label": building_type_label(value), "value": value}
        for value in CATEGORY_BUILDING_TYPES.get(category, ())
    ]
    area_label = {
        "residential": "Wohnfläche",
        "non_residential": "Nutzfläche",
        "mixed": "Wohn- und Nutzfläche",
    }.get(category, "Wohn-/Nutzfläche")
    conditional_building_controls = [category_control]
    if category is not None:
        conditional_building_controls.append(building_dropdown(
            uid, "building", "Gebäudetyp", building_options,
            row.get("building"),
            class_name="konfig-building-type-field",
            render_context=render_context,
        ))
    if category is not None and building_parameter_visible("retrofit", category):
        conditional_building_controls.append(building_dropdown(
            uid, "retrofit", "Sanierungszustand",
            [{"label": label, "value": value} for value, label in (
                (0, "Bestand"), (1, "Teilsaniert"), (2, "Vollständig saniert"),
            )],
            row.get("retrofit"),
            render_context=render_context,
        ))
    if (
        category is not None
        and building_parameter_visible("construction_type", category)
    ):
        conditional_building_controls.append(building_dropdown(
            uid, "construction_type", "Bauweise",
            [
                {"label": label, "value": value}
                for value, label in ((0, "Leicht"), (1, "Mittel"), (2, "Schwer"))
            ],
            row.get("construction_type"),
            render_context=render_context,
        ))
    category_and_type_control = (
        html.Div(
            automatic_form_grid(
                conditional_building_controls,
                class_name="konfig-conditional-field-grid",
            ),
            className="konfig-field konfig-conditional-field-group",
        )
        if len(conditional_building_controls) > 1
        else category_control
    )
    building_controls = [
        ("category", category_and_type_control),
        ("year", building_input(
            uid, "year", "Baujahr", row.get("year"), "number",
            number_kind="integer",
            group_thousands=False,
            render_context=render_context,
        )),
        ("area", building_input(
            uid, "area", area_label, row.get("area"), "number", "m²",
            render_context=render_context,
        )),
    ]
    building_controls.append((
        "night_setback",
        building_binary_choice(
            uid, "night_setback", "Nachtabsenkung",
            bool(row.get("night_setback")),
            render_context=render_context,
        ),
    ))
    building_controls.append((
        "cooling",
        building_binary_choice(uid, "cooling", "Aktive Gebäudekühlung", bool(row.get("cooling")), render_context=render_context),
    ))
    main_controls, more_controls = _split_local_controls(building_controls)
    building_main_fields = _shared_fields_for_dialog(
        BUILDING_PARAMETER_DIALOG_FIELDS, "main",
    )
    main_content = [automatic_form_grid(
        [*main_controls, *parameter_controls(building_main_fields, state, render_context=render_context)],
        class_name="konfig-building-form",
    )]
    building_more_fields = _shared_fields_for_dialog(
        BUILDING_PARAMETER_DIALOG_FIELDS, "more",
    )
    advanced_content = automatic_form_grid(
        [
            *more_controls,
            *parameter_controls(building_more_fields, state, render_context=render_context),
            *parameter_controls(fields_by_keys(list(BUILDING_ECO_FIELDS)), state, render_context=render_context),
        ],
        class_name="konfig-building-form",
    )
    building_name = str(row.get("name") or f"Gebäude {row.get('id')}")
    body = _dialog_body_with_optional_advanced(
        main_content,
        advanced_content,
        section_key=anchor,
        open_sections=open_sections,
        render_context=render_context,
    )
    return dialog(
        editable_heading(
            building_name,
            button_id=render_context.control_id({"type": "konfig-building-heading", "uid": uid}),
            input_id=render_context.control_id({"type": "konfig-building-name", "uid": uid}),
            state_id=render_context.control_id({"type": "konfig-building-heading-editing", "uid": uid}),
            class_name="konfig-building-heading",
            debounce=True,
        ),
        f"Gebäude {row.get('id')} · Gebäude-CSV und zentrale Anschlüsse",
        body,
    )


# Rendert die Parameter für dezentrale Geräte innerhalb der übergebenen Dialoghülle.
def _decentral_parameter_dialog(code, anchor, state, building_state, open_sections, render_context, dialog):
    parts = code.split(":")
    uid = int(parts[0])
    slot = parts[1]
    device = parts[-1] if parts else ""
    row = next((item for item in (building_state or {}).get("rows", []) if int(item.get("uid", -1)) == uid), {})
    config_codes = decentral_device_components(device)
    prefixes = tuple(f"D_{item}__" for item in config_codes)
    fields = [
        field for field in fields_for_section("decentral")
        if str(field.get("env_key", "")).startswith(prefixes)
    ]
    local_controls: list[tuple[str, Any]] = []
    if slot == "pv":
        local_controls = [
            ("f_PV1", building_input(uid, "f_PV1", "PV-Dachanteil 1", row.get("f_PV1"), "number", "–", render_context=render_context)),
            ("f_PV2", building_input(uid, "f_PV2", "PV-Dachanteil 2", row.get("f_PV2"), "number", "–", render_context=render_context)),
            ("beta_PV", building_angle_input(uid, "beta_PV", "Neigungswinkel β", row.get("beta_PV", 35.0), kind="inclination", render_context=render_context)),
            ("gamma_PV", building_angle_input(uid, "gamma_PV", "Ausrichtung γ", row.get("gamma_PV"), kind="orientation", render_context=render_context)),
        ]
    elif slot == "stc":
        local_controls = [
            ("f_STC", building_input(uid, "f_STC", "Solarthermie-Dachanteil", row.get("f_STC"), "number", "–", render_context=render_context)),
            ("beta_PV", building_angle_input(uid, "beta_PV", "Neigungswinkel β", row.get("beta_PV", 35.0), kind="inclination", render_context=render_context)),
            ("gamma_PV", building_angle_input(uid, "gamma_PV", "Ausrichtung γ", row.get("gamma_PV"), kind="orientation", render_context=render_context)),
        ]
    elif device == "BAT":
        local_controls = [("f_BAT", building_input(uid, "f_BAT", "Batteriefaktor", row.get("f_BAT"), "number", "Wh/WPV", render_context=render_context))]
    elif device == "TES":
        local_controls = [("f_TES", building_input(uid, "f_TES", "Speicherfaktor", row.get("f_TES"), "number", "l/kW", render_context=render_context))]
    elif device == "EV":
        ev_share = float(row.get("EV") or 0.0)
        local_controls = [
            ("EV", building_input(uid, "EV", "E-Auto-Anteil", ev_share * 100, "number", "%", render_context=render_context)),
        ]
        if ev_share > 0:
            local_controls.append(
                ("ev_charging", building_dropdown(uid, "ev_charging", "Ladeverhalten", [{"label": ev_charging_label(v), "value": v} for v in EV_CHARGING_TYPES], row.get("ev_charging"), render_context=render_context)),
            )
        else:
            fields = []
    main_controls, more_controls = _split_local_controls(local_controls)
    heat_pump_fields = (
        _shared_fields_for_dialog(
            DECENTRAL_HEAT_PUMP_PARAMETER_DIALOG_FIELDS, "more",
        )
        if "HP" in config_codes else []
    )
    advanced_fields = [
        *fields,
        *heat_pump_fields,
        *fields_by_keys(list(DECENTRAL_ECO_FIELDS.get(device, ()))),
    ]
    if device == "EV" and ev_share >= 1:
        advanced_fields = [
            field for field in advanced_fields
            if field["env_key"] != "PRICE_GASOLINE_LITER"
        ]
    advanced_content = field_grid(advanced_fields, state, render_context=render_context) if advanced_fields else None
    if more_controls:
        advanced_content = html.Div([
            automatic_form_grid(more_controls, class_name="konfig-building-form"),
            advanced_content,
        ])
    body = _dialog_body_with_optional_advanced(
        [automatic_form_grid(
            main_controls, class_name="konfig-building-form",
        )] if main_controls else [],
        advanced_content,
        section_key=anchor,
        open_sections=open_sections,
        default_open=not main_controls,
        render_context=render_context,
    )
    return dialog(
        decentral_device_name(device), "", body,
        removable=device != "TES_DHW",
    )


# Wählt den passenden Geräte-, Netz- oder Gebäudedialog aus.
def node_dialog(
    selection: dict[str, Any] | None,
    state: dict[str, Any],
    building_state: dict[str, Any] | None,
    field_owners: dict[str, str] | None = None,
    open_sections: dict[str, bool] | None = None,
    *, embedded: bool = False,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> Any:
    if not selection:
        return None
    kind = selection.get("kind")
    code = str(selection.get("code") or "")
    anchor = str(selection.get("anchor") or f"{kind}:{code}")
    color = str(selection.get("color") or COLORS["neutral"])
    owners = field_owners or {}

    # Übergibt Anker und Energieträgerfarbe an die Dialogdarstellung.
    def dialog(
        title: Any, subtitle: str, body: list[Any], *,
        removable: bool = False, max_width: int | None = None,
    ) -> html.Div:
        if embedded:
            return html.Div(body, className="konfig-dialog-section-stack")
        return _dialog_shell(
            title, subtitle, body,
            anchor=anchor, color=color, removable=removable,
            max_width=max_width,
        )

    if kind == "central" and code in CENTRAL_DEVICES:
        return _central_parameter_dialog(code, anchor, state, open_sections, render_context, dialog)

    if kind == "grid":
        return _grid_parameter_dialog(code, anchor, owners, state, open_sections, render_context, dialog)

    if kind == "resource":
        return _resource_parameter_dialog(code, anchor, state, open_sections, render_context, dialog)

    if kind == "network":
        return _network_parameter_dialog(code, anchor, owners, state, open_sections, render_context, dialog)

    if kind == "load":
        return _load_parameter_dialog(anchor, owners, state, open_sections, render_context, dialog)

    if kind == "building":
        return _building_parameter_dialog(code, anchor, state, building_state, open_sections, render_context, dialog)

    if kind == "decentral":
        return _decentral_parameter_dialog(code, anchor, state, building_state, open_sections, render_context, dialog)
    return None


