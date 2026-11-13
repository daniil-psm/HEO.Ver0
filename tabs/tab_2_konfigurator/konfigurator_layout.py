# baut Konfigurator-Tab aus Startansicht, Seitenleiste und Dashboard

from __future__ import annotations

from copy import deepcopy

from dash import dcc, html

from dg_adapter.input.config_service import list_dg_scenarios, next_microgrid_name
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from ui.components.dashboard_info import (
    flip_dashboard,
    main_panel_info_overlay,
    main_panel_info_toggle,
)
from ui.components.action_buttons import pill_action_button
from ui.components.sidebar import (
    sidebar, sidebar_nav_button, sidebar_nav_button_class, sidebar_panel,
)
from ui.components.topology_scene import topology_documentation_page

from .konfigurator_projektformular import project_form, scenario_load_form
from .konfigurator_icons import sidebar_icon_content
from .optimierungsablauf import (
    OPTIMIZATION_PROCESS_INFO_ENABLED,
    OPTIMIZATION_PROCESS_INTRODUCTION,
    OPTIMIZATION_PROCESS_SINGLE_INTRODUCTION,
    OPTIMIZATION_PROCESS_TITLE,
    optimization_process_page,
)
from heo.display.field_presentation import (
    FieldPresentation,
)
from ui.components.form_grid import (
    form_cell,
    form_grid,
)
from ui.components.form_overlay import (
    form_value_field,
)
from ui.components.form_controls import (
    scenario_choice_rows,
)


# Stellt die auswählbaren Szenarien als Zeilen des Startbereichs dar.
def _scenario_rows(
    scenarios: list[dict] | None = None,
    *,
    selected: str | None = None,
    editing: str | None = None,
    deleting: str | None = None,
) -> list[html.Div]:
    return scenario_choice_rows(
        scenarios if scenarios is not None else list_dg_scenarios(),
        selected=selected,
        editing=editing,
        deleting=deleting,
    )


# Baut die Hilfeseite des Konfigurators.
def _configurator_info_page() -> html.Div:
    return topology_documentation_page(
        "Konfigurator",
        "Die Übersicht dokumentiert alle eigenständigen Komponenten des District "
        "Generators. Sie ordnet Quellen, Erzeuger, Wandler und Speicher nach ihrem "
        "Hauptoutput und zeigt die zugehörigen Energieflüsse sowie die wesentlichen "
        "Komponentenparameter mit ihren Symbolen.",
    )


# Wählt die Rückseite passend zur sichtbaren Konfiguratoransicht.
def info_document_kind(state, simulation, choice_hidden: bool) -> str:
    simulation = simulation or {}
    running = bool(simulation.get("running")) and simulation.get("origin") == "configurator"
    process_stage = (
        simulation.get("origin") == "configurator"
        and (state or {}).get("stage") in {"progress", "completed", "stopped", "failed"}
    )
    if not OPTIMIZATION_PROCESS_INFO_ENABLED or (choice_hidden and not running and not process_stage):
        return "configurator"
    requested = simulation.get("requested_objectives") if choice_hidden else None
    single_run = (
        len(requested) == 1
        if isinstance(requested, (list, tuple)) and requested
        else (state or {}).get("optimization_focus") in {"economic", "ecological"}
    )
    return "optimization-single" if single_run else "optimization-comparison"


# Stellt die Hilfeseite als eingebettetes HTML-Dokument bereit.
def info_document(kind: str) -> html.Div:
    if kind == "configurator":
        return _configurator_info_page()
    return optimization_process_page(single_run=kind == "optimization-single")


# Bestimmt die Inhaltsklasse für die Konfiguratorhilfe.
def info_content_class_name(kind: str) -> str:
    classes = ["dashboard-info-content", "topology-documentation-content"]
    if kind != "configurator":
        classes.extend(("konfig-process-info-content", f"konfig-process-info-{kind}"))
    return " ".join(classes)


# Startseite, auf der der Nutzer zwischen dem Laden eines bestehenden Projekts und dem Erstellen eines neuen Projekts wählen kann
def _landing() -> html.Div:
    new_project = deepcopy(DEFAULT_HEO_INPUT_STATE)
    new_project.setdefault("values", {})["SCENARIO_NAME"] = next_microgrid_name()
    scenarios = list_dg_scenarios()
    selected = str(scenarios[0]["name"]) if scenarios else None
    return html.Div(
        id="konfig-landing",
        className="konfig-landing",
        children=[
            dcc.Store(id="konfig-scenario-select", data=selected),
            dcc.Store(id="konfig-scenario-edit", data=None),
            dcc.Store(id="konfig-scenario-delete-pending", data=None),
            html.Section(
                className="glass-panel konfig-landing-panel konfig-load-panel",
                children=[
                    html.Div(
                        className="konfig-landing-idle",
                        children=[
                            html.Span("↻", className="konfig-landing-symbol"),
                            html.Span("Microgrid laden", className="konfig-landing-label"),
                        ],
                    ),
                    html.Div(
                        className="konfig-landing-hover-content",
                        children=scenario_load_form(
                            _scenario_rows(scenarios, selected=selected)
                        ),
                    ),
                    html.Div(
                        id="konfig-scenario-delete-options",
                        className="konfig-scenario-delete-options",
                        hidden=True,
                        role="group",
                        **{"aria-label": "Löschoptionen für das Szenario"},
                        children=[
                            pill_action_button("Ergebnisse löschen", "konfig-delete-results"),
                            pill_action_button("Gesamtes Szenario löschen", "konfig-delete-entire"),
                        ],
                    ),
                    html.Button(
                        id="konfig-delete-dismiss",
                        n_clicks=0,
                        type="button",
                        style={"display": "none"},
                    ),
                ],
            ),
            html.Section(
                className="glass-panel konfig-landing-panel konfig-new-panel",
                children=[
                    html.Div(
                        className="konfig-landing-idle",
                        children=[
                            html.Span("+", className="konfig-landing-symbol"),
                            html.Span("Microgrid erstellen", className="konfig-landing-label"),
                        ],
                    ),
                    html.Div(
                        className="konfig-landing-hover-content konfig-new-hover-content",
                        children=project_form(new_project, embedded=True),
                    ),
                ],
            ),
        ],
    )


# Eine Seitenleiste für alle Konfiguratoraktionen
def _icon_button(
    icon: str,
    label: str,
    component_id: str,
    *,
    active: bool = False,
    modifier_class: str | None = None,
) -> html.Button:
    button = sidebar_nav_button(
        label, component_id, active=active, modifier_class=modifier_class,
    )
    button.children = sidebar_icon_content(icon, label)
    return button


# Baut die Navigation und Aktionen des Konfigurators.
def _sidebar(
    *,
    simulate_content: list[html.Span] | None = None,
    simulate_hidden: bool = False,
    parameters_active: bool = False,
) -> html.Aside:
    load_button = _icon_button(
        "folder-input", "Konfiguration laden/erstellen", "konfig-sidebar-load",
    )
    load_button.children[1].children = [
        "Konfiguration ",
        html.Span("laden/erstellen", style={"whiteSpace": "nowrap"}),
    ]
    simulate_button = _icon_button(
        "play", "Optimierung starten", "konfig-sidebar-simulate",
        modifier_class="konfig-simulate-button",
    )
    if simulate_content is not None:
        simulate_button.children = simulate_content
    simulate_button.hidden = simulate_hidden
    simulate_control = simulate_button
    if OPTIMIZATION_PROCESS_INFO_ENABLED:
        simulate_control = html.Div(
            className="konfig-simulate-control",
            children=[
                simulate_button,
                main_panel_info_toggle(
                    "Optimierungsablauf anzeigen",
                    overlay_id="konfig-process-overlay",
                    class_name="konfig-simulate-info-button",
                ),
            ],
        )
    return sidebar(
        [
            sidebar_panel(
                [
                    load_button,
                    _icon_button("circle-plus", "Alle auswählen", "konfig-sidebar-select-all"),
                    _icon_button("circle-minus", "Alle abwählen", "konfig-sidebar-deselect-all"),
                    _icon_button("circle-check", "Konfiguration prüfen", "konfig-sidebar-validate"),
                    main_panel_info_toggle(
                        "Alle Parameter",
                        overlay_id="konfig-parameters-overlay",
                        component_id="konfig-sidebar-parameters",
                        class_name=sidebar_nav_button_class(active=parameters_active),
                        children=sidebar_icon_content("info", "Alle Parameter"),
                        expanded=parameters_active,
                    ),
                    _icon_button("save", "Konfiguration speichern", "konfig-sidebar-save"),
                    simulate_control,
                    html.Div(
                        id="konfig-validation-panel",
                        className="konfig-validation-panel",
                        hidden=True,
                        children=html.Div(
                            id="konfig-validation-result",
                            **{"aria-live": "polite"},
                        ),
                    ),
                    html.Div(
                        id="konfig-action-status",
                        className="konfig-sidebar-status",
                        **{"aria-live": "polite"},
                    ),
                ],
                component_id="konfig-actions-panel",
                panel_class="app-sidebar-panel konfig-sidebar-panel",
            ),
        ],
        column_class="app-sidebar-column konfig-sidebar",
        component_id="konfig-sidebar",
    )


# Baut das Formular für Optimierungsfokus, Einstellungen und Startaktion.
def _optimization_form(state, settings_mode, choice_hidden, settings) -> html.Div:
    return html.Div(
        id="konfig-simulation-choice",
        className="konfig-simulation-choice",
        hidden=choice_hidden,
        role="form",
        **{"aria-label": "Optimierungseinstellungen"},
        children=form_grid([
            form_cell(
                html.H2("Optimierungseinstellungen"),
                row=1, column=1,
                class_name="konfig-optimization-heading-cell",
            ),
            form_cell(
                form_value_field(
                    FieldPresentation(
                        label="Optimierungsfokus",
                        value=str((state or {}).get("optimization_focus", "comparison")),
                        editable=True,
                        kind="choice",
                    ),
                    dcc.RadioItems(
                        id="konfig-optimization-focus",
                        options=[
                            {"label": "Ökonomisch", "value": "economic"},
                            {"label": "Ökologisch", "value": "ecological"},
                            {"label": "Vergleich", "value": "comparison"},
                        ],
                        value=(state or {}).get("optimization_focus", "comparison"),
                        className="konfig-focus-choice",
                    ),
                    class_name="konfig-field konfig-optimization-form-field",
                ),
                row=2, column=1,
            ),
            form_cell(
                form_value_field(
                    FieldPresentation(
                        label="Einstellungen",
                        value=settings_mode,
                        editable=True,
                        kind="choice",
                    ),
                    dcc.RadioItems(
                        id="konfig-simulation-settings-mode",
                        options=[
                            {"label": "Standardeinstellungen", "value": "standard"},
                            {"label": "Benutzerdefinierte Optimierungseinstellungen", "value": "custom"},
                        ],
                        value=settings_mode,
                        className="konfig-focus-choice konfig-settings-choice",
                    ),
                    class_name="konfig-field konfig-optimization-form-field",
                ),
                row=3, column=1,
            ),
            form_cell(
                html.Div(children=settings, id="konfig-simulation-settings-content"),
                row=4, column=1,
                class_name="konfig-optimization-conditional-cell",
            ),
            form_cell(
                html.Button(
                    sidebar_icon_content("play", "Optimierung starten"),
                    id="konfig-simulation-start",
                    n_clicks=0,
                    type="button",
                    className="konfig-choice-start",
                ),
                row=5, column=1,
                class_name="konfig-optimization-action-cell",
            ),
        ], columns=1, class_name="konfig-optimization-form-grid"),
    )


# Baut den Tab bereits mit dem aktuellen Inhalt und dessen Sichtbarkeit.
#
# Erstaufbau und spätere Callback-Updates nutzen dieselbe Renderfunktion.
# Jede Navigation erhält einen eigenen Komponentenbaum.
def create_configurator_dashboard(
    *,
    state=None,
    heo_state=None,
    buildings=None,
    selection=None,
    simulation=None,
    weather=None,
) -> html.Div:
    from .konfigurator_callbacks import render_configurator, topology_render_signature

    (
        landing_style, workbench_style, topology, inspector, settings, monitor,
        choice_hidden, interval_disabled, simulate_content, simulate_hidden,
        parameters_overlay_content,
    ) = render_configurator(
        state, heo_state, buildings, selection, simulation, weather, 0,
    )
    landing = _landing()
    landing.style = landing_style
    info_kind = info_document_kind(state, simulation, choice_hidden)
    process_back = info_kind != "configurator"
    requested_objectives = (simulation or {}).get("requested_objectives")
    single_run = (
        info_kind == "optimization-single"
        if process_back else (
            len(requested_objectives) == 1
            if isinstance(requested_objectives, (list, tuple)) and requested_objectives
            else (state or {}).get("optimization_focus") in {"economic", "ecological"}
        )
    )
    settings_mode = (state or {}).get("simulation_mode")
    if (state or {}).get("stage") == "simulation_settings":
        settings_mode = "custom"
    if settings_mode not in {"standard", "custom"}:
        settings_mode = "standard"

    return html.Div(
        className="dashboard-screen konfig-dashboard",
        children=[
            dcc.Interval(
                id="konfig-simulation-interval", interval=1000,
                n_intervals=0, disabled=interval_disabled,
            ),
            # Empfängt Drag-and-drop-Ereignisse aus dem nativen Browser-Handler.
            # Die Gebäudereihenfolge selbst bleibt ausschließlich im zentralen
            # building-scenario-store.
            dcc.Input(
                id="konfig-building-drag-event", type="text", value="",
                style={"display": "none"},
            ),
            landing,
            html.Div(
                id="konfig-workbench",
                className="konfig-workbench",
                style=workbench_style,
                children=[
                    _sidebar(
                        simulate_content=simulate_content,
                        simulate_hidden=simulate_hidden,
                        parameters_active=(state or {}).get("stage") == "parameters",
                    ),
                    flip_dashboard(
                        html.Main(
                            id="konfig-main-panel",
                            className="glass-panel main-panel-surface konfig-main-panel",
                            **{"data-heo-capture-target": "main-panel"},
                            children=[
                                _optimization_form(state, settings_mode, choice_hidden, settings),
                                html.Div(
                                    children=topology, id="konfig-topology-content",
                                    className="konfig-topology-content",
                                ),
                                html.Div(
                                    children=inspector, id="konfig-inspector",
                                    className="konfig-inspector",
                                ),
                                html.Div(
                                    children=monitor,
                                    id="konfig-simulation-monitor-content",
                                ),
                            ],
                        ),
                        name="konfigurator-main",
                        overlay=[
                            main_panel_info_overlay(
                                overlay_id="konfig-parameters-overlay",
                                close_id="konfig-parameters-close",
                                close_label="Alle Parameter schließen",
                                title="Alle Parameter",
                                introduction=(
                                    "Alle Einstellungen des Microgrids im Überblick. "
                                    "Bearbeitbare Werte können hier direkt angepasst werden."
                                ),
                                content=parameters_overlay_content,
                                content_id="konfig-parameters-overlay-content",
                                class_name="konfig-parameters-overlay",
                            ),
                            *(
                                [main_panel_info_overlay(
                                    overlay_id="konfig-process-overlay",
                                    close_id="konfig-process-close",
                                    close_label="Optimierungsablauf schließen",
                                    title=OPTIMIZATION_PROCESS_TITLE,
                                    introduction=(
                                        OPTIMIZATION_PROCESS_SINGLE_INTRODUCTION
                                        if single_run else OPTIMIZATION_PROCESS_INTRODUCTION
                                    ),
                                    content=optimization_process_page(
                                        instance="overlay", include_header=False,
                                        single_run=single_run,
                                    ),
                                    class_name="konfig-process-overlay",
                                    hidden=True,
                                )]
                                if OPTIMIZATION_PROCESS_INFO_ENABLED else []
                            ),
                        ],
                        info=info_document(info_kind),
                        info_content_id="konfig-info-back-content",
                        info_content_classes=tuple(
                            info_content_class_name(info_kind).split()[1:]
                        ),
                        info_back_classes=(
                            ("topology-documentation-back", "konfig-process-info-back")
                            if process_back
                            else ("topology-documentation-back",)
                        ),
                    ),
                ],
            ),
            dcc.Store(id="konfig-create-result-store"),
            dcc.Store(id="konfig-create-ui-store"),
            dcc.Store(
                id="konfig-topology-render-signature",
                data=topology_render_signature(state, buildings, selection, simulation),
            ),
        ],
    )


Dashboard_Konfigurator = create_configurator_dashboard()
