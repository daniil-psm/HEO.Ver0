# Stellt Projektinformationen als gemeinsame Dash-Komponente für Konfigurator und Ergebnisse dar.

from __future__ import annotations

from typing import Any

from dash import html

from ui.components.form_context import DEFAULT_FORM_CONTEXT, FormRenderContext

from heo.model.annual_series import ANNUAL_KEYS, series_view
from heo.display.project_info_data import (
    ProjectInfoContext, format_project_number, config_changed, selected_key, central_device_items, decentral_device_items, building_items,
)
from heo.display.parameter_catalog import ACTIVATION_FIELD_GROUPS, SECTION_TITLES
from ui.components.form_overlay import (
    OVERLAY_SECTION_CLASS,
    readonly_grouped_parameter_controls,
    form_value_field,
    readonly_parameter_control,
    visible_parameter_unit,
)
from ui.components.form_grid import (
    automatic_form_grid,
    form_cell,
    form_grid,
)
from heo.display.field_presentation import (
    overlay_section,
    parameter_field_presentation,
    parameter_number_kind,
)
from heo.display.parameter_dialog_layout import (
    split_parameter_dialog_fields,
)
from heo.display.number_format import format_german_number
from heo.display.field_values import parameter_unit


# Baut eine Informationskarte mit Titel und Inhaltsbereichen.
def info_card(
    title: str,
    rows: list[tuple[str, str]] | None = None,
    *,
    content: Any | None = None,
    description: str | None = None,
    status: str | None = None,
    status_kind: str = "default",
    badges: list[str] | None = None,
    modifier_class: str = "",
) -> html.Div:
    class_name = "general-info-card"
    if modifier_class:
        class_name += f" {modifier_class}"
    return html.Div(
        className=class_name,
        **{"data-form-section": "true"},
        children=[
            html.Div(
                className="general-info-card-header",
                **{"data-form-header": "true"},
                children=[
                    html.H3(title, className="general-info-card-title"),
                    html.Span(
                        status,
                        className=f"general-info-status general-info-status-{status_kind}",
                    )
                    if status
                    else None,
                ],
            ),
            html.P(description, className="general-info-card-description")
            if description
            else None,
            html.Div(
                className="general-info-badges",
                children=[html.Span(badge) for badge in badges],
            )
            if badges
            else None,
            html.Div(
                className="general-info-table",
                children=[
                    html.Div(
                        className="general-info-row",
                        **{"data-form-entry": "true"},
                        children=[
                            html.Span(label, className="general-info-label"),
                            html.Span(value, className="general-info-value"),
                        ],
                    )
                    for label, value in (rows or [])
                ],
            ) if rows else None,
            content,
        ],
    )


# Rendert dieselben Projektfelder in der Ergebnisansicht und Parameterübersicht.
def parameter_grid(
    fields: list[dict],
    values: dict,
    defaults: dict,
    weather_data: dict | None,
    *, editor=None,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    if editor is not None:
        return editor(fields, values, defaults, weather_data, render_context=render_context)

    return automatic_form_grid(
        readonly_parameter_controls(fields, values, defaults, weather_data),
        class_name="konfig-field-grid general-parameter-grid",
    )


# Liefert gruppierte Anzeigeelemente unabhängig von ihrer späteren Rasterhülle.
def readonly_parameter_controls(
    fields: list[dict], values: dict, defaults: dict, weather_data: dict | None,
) -> list[Any]:
    # Liest den Anzeigewert und kürzt Wetterdateipfade auf den Dateinamen.
    def field_value(field: dict) -> Any:
        key = field.get("input_key") or field["env_key"]
        value = values.get(key, defaults.get(key, field.get("default")))
        if field["env_key"] == "WEATHER_FILE":
            value = (weather_data or {}).get("filename") or value
            value = str(value).replace("\\", "/").rsplit("/", 1)[-1]
        return value

    # Stellt Jahresreihen mit Stützjahren und übrige Felder als Einzelwerte dar.
    def readonly_control(field: dict, value: Any) -> html.Div:
        key = field.get("input_key") or field["env_key"]
        if key not in ANNUAL_KEYS:
            return readonly_parameter_control(field, value, choice_presentation="text")
        try:
            mode, points, entries = series_view({"values": values, "defaults": defaults}, key)
        except (ValueError, TypeError, ZeroDivisionError):
            return readonly_parameter_control(field, value, choice_presentation="text")
        indices = [-1] if mode == "constant" else points
        controls = [
            html.Label([
                html.Span("Wert" if year == -1 else f"Jahr {year}"),
                html.Strong(
                    format_german_number(entry, kind=parameter_number_kind(field),
                                         scale=float(field.get("display_scale") or 1.0),
                                         divisor=float(field.get("display_divisor") or 1.0)),
                    className="konfig-readonly-value heo-field__value heo-unit-reading",
                    **{"data-unit-base-value": float(entry) * float(field.get("display_scale") or 1.0)
                       / float(field.get("display_divisor") or 1.0)},
                ),
            ])
            for year, entry in zip(indices, entries)
        ]
        return form_value_field(
            parameter_field_presentation(
                field, label=field.get("label", key), value="", kind="choice", editable=False,
                unit=parameter_unit(field),
            ),
            html.Div([
                html.Span("konstant" if mode == "constant" else "für Stützjahre",
                          className="konfig-series-readonly-mode"),
                html.Div(controls, className="konfig-series-values"),
                html.Small("Wert gilt ab dem Stützjahr bis zum nächsten Stützjahr.")
                if mode == "support" else None,
            ]),
            unit_component=visible_parameter_unit(field),
            use_control_when_readonly=True,
        )

    rendered = readonly_grouped_parameter_controls(
        fields,
        field_value,
        activation_groups=ACTIVATION_FIELD_GROUPS,
        control_renderer=readonly_control,
        choice_presentation="text",
    )
    return rendered


# Rendert weitere Projektparameter mit einem stabilen Abschnittsschlüssel.
def _advanced_parameter_section(
    fields: list[dict],
    values: dict,
    defaults: dict,
    weather_data: dict | None,
    *,
    default_open: bool = False,
    editor=None,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Details | None:
    if not fields:
        return None
    section = overlay_section("Weitere Parameter", default_open=default_open)
    return render_context.details(
        section.title,
        parameter_grid(fields, values, defaults, weather_data, editor=editor,
                       render_context=render_context.child("more")),
        key="more", default_open=section.default_open,
        class_name=f"general-config-advanced konfig-advanced {OVERLAY_SECTION_CLASS}",
    )


# Baut eine Konfigurationskarte im fachlichen Namensraum ihres Abschnitts.
def _standard_config_card(
    section: dict,
    values: dict,
    defaults: dict,
    weather_data: dict | None,
    *, editor=None,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    render_context = render_context.child(f"section:{section['key']}")
    main_fields, more_fields = split_parameter_dialog_fields(section["fields"])
    if section["key"] == "pyomo":
        prominent = {"SOLVER_OPTIONS__TIME_LIMIT", "SOLVER_OPTIONS__MIP_GAP"}
        main_fields = main_fields + [f for f in more_fields if f["env_key"] in prominent]
        more_fields = [f for f in more_fields if f["env_key"] not in prominent]
    content = html.Div(
        className="general-config-card-content konfig-dialog-section-stack",
        children=[
            parameter_grid(
                main_fields, values, defaults, weather_data, editor=editor,
                render_context=render_context.child("main"),
            )
            if main_fields else None,
            _advanced_parameter_section(
                more_fields,
                values,
                defaults,
                weather_data,
                default_open=not main_fields,
                editor=editor,
                render_context=render_context,
            ),
        ],
    )
    changed = config_changed(section, values, defaults)
    return info_card(
        SECTION_TITLES.get(section["key"], section["class_name"]),
        content=content,
        description=section.get("description"),
        status="Angepasst" if changed else "DG-Standard",
        status_kind="changed" if changed else "default",
        modifier_class="general-config-card general-config-box",
    )


# Rendert den gewählten Detaildatensatz im geräte- oder gebäudebezogenen Kontext.
def _parameter_detail(
    item: dict, *, editor=None, detail_editor=None, group=None,
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    render_context = render_context.child(f"{group}:{item['key']}")
    main_fields = item.get("main_fields") or []
    more_fields = item.get("more_fields") or []
    values = item.get("values") or {}
    defaults = item.get("defaults") or {}
    weather_data = item.get("weather_data")
    if detail_editor is not None:
        return detail_editor(group, item, render_context=render_context)
    return html.Div(
        className="general-master-detail-panel",
        children=[
            html.Div(
                className="general-master-detail-header",
                children=[
                    html.Div([
                        html.H3(item["title"], className="general-info-card-title"),
                        html.P(
                            item.get("description") or "Konfigurierte Parameter",
                            className="general-info-card-description",
                        ),
                    ]),
                    html.Span(
                        item.get("status") or "Aktiv",
                        className="general-info-status general-info-status-complete",
                    ),
                ],
            ),
            parameter_grid(
                main_fields, values, defaults, weather_data, editor=editor,
                render_context=render_context.child("main"),
            )
            if main_fields else None,
            _advanced_parameter_section(
                more_fields,
                values,
                defaults,
                weather_data,
                default_open=not main_fields,
                editor=editor,
                render_context=render_context,
            ),
        ],
    )


# Verbindet die Auswahl einer Anlage oder eines Gebäudes mit dessen Detailansicht.
def _master_detail_card(
    title: str,
    description: str,
    items: list[dict],
    selected: Any,
    *,
    group: str,
    empty_message: str,
    editor=None, detail_editor=None, selector_type="energy-project-selector",
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    active_key = selected_key(items, selected)
    active_item = next(
        (item for item in items if str(item["key"]) == active_key), None,
    )
    selector = html.Div(
        className="general-master-list",
        role="listbox",
        **{"aria-label": title},
        children=[
            html.Button(
                [
                    html.Span(item["label"], className="general-master-list-label"),
                    html.Span(
                        item.get("subtitle") or "",
                        className="general-master-list-subtitle",
                    ),
                ],
                id={
                    "type": selector_type,
                    "group": group,
                    "key": str(item["key"]),
                },
                n_clicks=0,
                type="button",
                role="option",
                className=(
                    "general-master-list-item is-selected"
                    if str(item["key"]) == active_key
                    else "general-master-list-item"
                ),
                **{
                    "aria-selected": (
                        "true" if str(item["key"]) == active_key else "false"
                    )
                },
            )
            for item in items
        ],
    )
    content = (
        html.Div(
            [selector, _parameter_detail(
                active_item, editor=editor, detail_editor=detail_editor,
                group=group, render_context=render_context,
            )],
            className="general-master-detail-layout",
        )
        if active_item
        else html.Div(empty_message, className="general-master-detail-empty")
    )
    return info_card(
        title,
        content=content,
        description=description,
        status=f"{len(items)} aktiv" if items else "Keine Auswahl",
        status_kind="complete" if items else "warning",
        modifier_class=(
            "general-config-card general-config-box general-master-detail-card"
        ),
    )


# Stellt die Projektdaten eines Gebäudes als Karte dar.
def _building_scenario_card(buildings: list[dict]) -> html.Div:
    total_area = sum(float(row.get("area") or 0) for row in buildings)
    complete = sum(bool(row.get("category") and row.get("building")) for row in buildings)
    return info_card(
        "Gebäude-CSV",
        [
            ("Gebäude", str(len(buildings))),
            ("Vollständig", f"{complete} von {len(buildings)}"),
            ("Gesamtfläche", f"{format_project_number(total_area)} m²"),
        ],
        description="Gebäudeszenario und Grundlage der DG-Gebäude-CSV.",
        status="Eingabestand",
        status_kind="live",
        modifier_class="general-config-box",
    )


# Rendert den vorbereiteten Projektkontext ohne Adapteraufrufe oder Datenbeschaffung.
# Auswahl und Editoren bleiben reine Darstellungsoptionen.
def project_info_view(
    context: ProjectInfoContext,
    *,
    selected_central_device: str | None = None,
    selected_decentral_device: str | None = None,
    selected_building: str | None = None,
    editor=None, detail_editor=None, selector_type="energy-project-selector",
    render_context: FormRenderContext = DEFAULT_FORM_CONTEXT,
) -> html.Div:
    weather_data = context["weather_data"]
    buildings = context["buildings"]
    project_data = context["sections"]
    values = project_data["values"]
    defaults = project_data["defaults"]
    section_by_key = project_data["section_by_key"]
    eco_fields = project_data["eco_fields"]
    display_values = project_data["display_values"]
    display_defaults = project_data["display_defaults"]
    project_section = project_data["project_section"]
    central = project_data["central"]
    simulation_cards = [
        _standard_config_card(
            section, values, defaults, weather_data,
            editor=editor, render_context=render_context,
        )
        for section in project_data["simulation_sections"]
    ]
    building_config_cards = [
        _standard_config_card(
            section, values, defaults, weather_data,
            editor=editor, render_context=render_context,
        )
        for section in project_data["building_sections"]
    ]
    microgrid_cards = [
        _standard_config_card(
            section, values, defaults, weather_data,
            editor=editor, render_context=render_context,
        )
        for section in (
            project_data["microgrid_frame"], project_data["heatgrid"],
            project_data["microgrid_economics"],
        )
    ] + [_building_scenario_card(buildings)]
    central_card = _master_detail_card(
        "Zentrale Anlagen",
        "Nur die im Konfigurator aktivierten zentralen Komponenten.",
        central_device_items(central, values, defaults, weather_data),
        selected_central_device,
        group="central",
        editor=editor, detail_editor=detail_editor, selector_type=selector_type,
        empty_message="Im Konfigurator ist keine zentrale Anlage aktiviert.",
        render_context=render_context,
    )
    decentral_card = _master_detail_card(
        "Dezentrale Anlagen",
        "Aktive Komponenten aller Gebäude; die Auswahl öffnet ihre Parameter.",
        decentral_device_items(
            section_by_key["decentral"], buildings, values, defaults,
            weather_data, eco_fields,
        ),
        selected_decentral_device,
        group="decentral",
        editor=editor, detail_editor=detail_editor, selector_type=selector_type,
        empty_message="In den Gebäuden ist keine dezentrale Anlage aktiviert.",
        render_context=render_context,
    )
    buildings_card = _master_detail_card(
        "Gebäude",
        "Alle hinzugefügten Gebäude; die Auswahl öffnet den vollständigen Datensatz.",
        building_items(buildings),
        selected_building,
        group="building",
        editor=editor, detail_editor=detail_editor, selector_type=selector_type,
        empty_message="Es wurde noch kein Gebäude hinzugefügt.",
        render_context=render_context,
    )
    remaining_cards = [
        _standard_config_card(
            section_by_key[key], values, defaults, weather_data,
            editor=editor, render_context=render_context,
        )
        for key in ("physics", "report")
        if key in section_by_key
    ]
    config_cards = [
        _standard_config_card(
            project_section, display_values, display_defaults, weather_data,
            editor=editor, render_context=render_context,
        ),
        *simulation_cards,
        *building_config_cards,
        decentral_card,
        *microgrid_cards,
        central_card,
        *remaining_cards,
        buildings_card,
    ]
    if editor is None:
        config_cards.append(info_card(
            "Datenstand",
            [("Quelle", context["source_label"])],
            description=context["source_note"],
            modifier_class="general-config-box",
        ))
    return html.Div(
        className="general-project-dashboard general-project-dialog",
        children=form_grid(
            [form_cell(card, full_width="general-master-detail-card" in card.className, class_name=(
                "general-project-wide-cell"
                if "general-master-detail-card" in card.className else ""
            )) for card in config_cards],
            class_name="general-info-grid general-config-dialog-grid",
        ),
    )

