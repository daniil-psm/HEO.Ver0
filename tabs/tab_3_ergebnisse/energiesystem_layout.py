# Layout des Energiesystem-Tabs

from dataclasses import replace

from dash import dcc, html
from ui.components.form_grid import form_grid

from ui.components.dashboard_info import dashboard_info_page, flip_dashboard
from ui.components.sidebar import (
    SIDEBAR_PANEL_CLASS,
    sidebar,
    sidebar_nav_button,
    sidebar_panel,
)
from .energiesystem_umgebung import ENVIRONMENT_SERIES_OPTIONS, environment_figure
from .energiesystem_bedarfe import (
    DEMAND_SERIES_OPTIONS,
    thermal_energy_figure_from_store,
)
from heo.topology.postprocessing import build_postprocessing_scene
from heo.display.result_views import ENERGY_VIEWS, ENERGY_VIEW_INFO

from dg_adapter.output.pfc_results import build_pfc_frame
from dg_adapter.output.result_series import result_clusters
from .energiesystem_topologie import energy_topology_component
from .energiesystem_vergleich import comparison_figure, objective_heading


_INITIAL_SYSTEM_SCENE = build_postprocessing_scene(None)
_INITIAL_PFC_TOPOLOGY, _INITIAL_PFC_FRAME = build_pfc_frame(
    None, _INITIAL_SYSTEM_SCENE.topology
)
_INITIAL_PFC_TOPOLOGY = replace(
    _INITIAL_PFC_TOPOLOGY,
    message="Powerflow wird vorbereitet …",
)
_INITIAL_PFC_FRAME = replace(
    _INITIAL_PFC_FRAME,
    title="Powerflow wird vorbereitet …",
)


# Erzeugt die Infoseite für das aktuell sichtbare Ergebnisfenster.
def energy_info_page(
    view: str, optimization_data: dict | None = None,
) -> html.Div:
    title, introduction, sections = ENERGY_VIEW_INFO.get(
        view, ENERGY_VIEW_INFO["project"]
    )
    if view == "sankey":
        clusters = result_clusters(optimization_data)
        if clusters:
            introduction = (
                "Das Sankey-Fenster verdichtet die jährlichen Energieflüsse "
                f"des ersten simulierten Ergebnisjahres (Simulationsjahr {clusters[0].year_key})."
            )
    return dashboard_info_page(title, introduction, sections)


# Legt die anfängliche Sichtbarkeit eines Ergebnisbereichs fest.
def _view_style(initial_view: str, view: str, display: str = "block") -> dict[str, str]:
    return {"display": display if initial_view == view else "none"}


# Baut die Seitenanzeige des ökonomischen Energieausweises.
def _economic_certificate_pane() -> html.Div:
    return html.Div(
        className="energy-certificate-pane energy-certificate-pane--economic",
        children=[
            html.H3("Ökonomisch", className="energy-certificate-pane-title"),
            html.Div(
                id="energy-certificate-toolbar",
                className="energy-certificate-toolbar",
                style={"display": "none"},
                children=[
                    html.Div(
                        className="energy-certificate-pagination",
                        children=[
                            html.Button(
                                html.Span(
                                    className="energy-certificate-arrow-icon energy-certificate-arrow-icon-left",
                                    **{"aria-hidden": "true"},
                                ),
                                id="energy-certificate-previous",
                                n_clicks=0,
                                className="energy-certificate-tool-button energy-certificate-arrow energy-certificate-previous",
                                title="Vorherige Seite (Pfeiltaste links)",
                                **{"aria-label": "Vorherige Seite"},
                            ),
                            html.Span(
                                "Seite 1 / 1",
                                id="energy-certificate-page-label",
                                className="energy-certificate-page-label",
                            ),
                            html.Button(
                                html.Span(
                                    className="energy-certificate-arrow-icon energy-certificate-arrow-icon-right",
                                    **{"aria-hidden": "true"},
                                ),
                                id="energy-certificate-next",
                                n_clicks=0,
                                className="energy-certificate-tool-button energy-certificate-arrow energy-certificate-next",
                                title="Nächste Seite (Pfeiltaste rechts)",
                                **{"aria-label": "Nächste Seite"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="energy-certificate-copy-slot",
                        children=[
                            html.Button(
                                [
                                    html.Span(
                                        className="energy-certificate-copy-icon",
                                        **{"aria-hidden": "true"},
                                    ),
                                    html.Span(
                                        "Seite als Bild kopieren",
                                        className="energy-certificate-copy-label",
                                    ),
                                ],
                                id="energy-certificate-copy",
                                n_clicks=0,
                                className="energy-certificate-tool-button energy-certificate-copy-button",
                                title="Aktuelle Seite in die Zwischenablage kopieren",
                                **{"aria-label": "Aktuelle Seite als Bild kopieren"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                "Quartiersenergieausweis wird geladen …",
                id="energy-certificate-message",
                className="energy-certificate-message",
            ),
            html.Div(
                id="energy-certificate-page-stage",
                className="energy-certificate-page-stage",
                **{"data-page-src": "", "data-page-label": "Seite 1 / 1"},
                children=[
                    html.Img(
                        id="energy-certificate-page-image",
                        className="energy-certificate-page-image",
                        alt="Aktuelle Seite des Quartiersenergieausweises",
                        draggable="false",
                    ),
                    html.Div(
                        "Seite wird geladen …",
                        className="energy-certificate-page-loading",
                        role="status",
                    ),
                    html.Div(
                        "Seite konnte nicht geladen werden.",
                        className="energy-certificate-page-error",
                        role="alert",
                    ),
                ],
            ),
        ],
    )


# Baut die Seitenanzeige des ökologischen Energieausweises.
def _ecological_certificate_pane() -> html.Div:
    return html.Div(
        className="energy-certificate-pane energy-certificate-pane--ecological",
        children=[
            html.H3("Ökologisch", className="energy-certificate-pane-title"),
            html.Div(
                id="energy-certificate-ecological-toolbar",
                className="energy-certificate-toolbar",
                style={"display": "none"},
                children=[
                    html.Div(
                        className="energy-certificate-pagination",
                        children=[
                            html.Button(
                                html.Span(
                                    className="energy-certificate-arrow-icon energy-certificate-arrow-icon-left",
                                    **{"aria-hidden": "true"},
                                ),
                                id="energy-certificate-ecological-previous",
                                n_clicks=0,
                                className="energy-certificate-tool-button energy-certificate-arrow energy-certificate-previous",
                                title="Vorherige Seite (Pfeiltaste links)",
                                **{"aria-label": "Vorherige ökologische Seite"},
                            ),
                            html.Span(
                                "Seite 1 / 1",
                                id="energy-certificate-ecological-page-label",
                                className="energy-certificate-page-label",
                            ),
                            html.Button(
                                html.Span(
                                    className="energy-certificate-arrow-icon energy-certificate-arrow-icon-right",
                                    **{"aria-hidden": "true"},
                                ),
                                id="energy-certificate-ecological-next",
                                n_clicks=0,
                                className="energy-certificate-tool-button energy-certificate-arrow energy-certificate-next",
                                title="Nächste Seite (Pfeiltaste rechts)",
                                **{"aria-label": "Nächste ökologische Seite"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="energy-certificate-copy-slot",
                        children=html.Button(
                            [
                                html.Span(
                                    className="energy-certificate-copy-icon",
                                    **{"aria-hidden": "true"},
                                ),
                                html.Span(
                                    "Seite als Bild kopieren",
                                    className="energy-certificate-copy-label",
                                ),
                            ],
                            id="energy-certificate-ecological-copy",
                            n_clicks=0,
                            className="energy-certificate-tool-button energy-certificate-copy-button",
                            title="Aktuelle Seite in die Zwischenablage kopieren",
                            **{"aria-label": "Aktuelle ökologische Seite als Bild kopieren"},
                        ),
                    ),
                ],
            ),
            html.Div(
                "Quartiersenergieausweis wird geladen …",
                id="energy-certificate-ecological-message",
                className="energy-certificate-message",
            ),
            html.Div(
                id="energy-certificate-ecological-page-stage",
                className="energy-certificate-page-stage",
                **{"data-page-src": "", "data-page-label": "Seite 1 / 1"},
                children=[
                    html.Img(
                        id="energy-certificate-ecological-page-image",
                        className="energy-certificate-page-image",
                        alt="Aktuelle Seite des ökologischen Quartiersenergieausweises",
                        draggable="false",
                    ),
                    html.Div(
                        "Seite wird geladen …",
                        className="energy-certificate-page-loading",
                        role="status",
                    ),
                    html.Div(
                        "Seite konnte nicht geladen werden.",
                        className="energy-certificate-page-error",
                        role="alert",
                    ),
                ],
            ),
        ],
    )


# Baut den Bereich für Projektinformationen.
def _project_view(initial_view) -> html.Div:
    return html.Div(
        id="energy-project-view",
        className="energy-content-view",
        style=_view_style(initial_view, "project"),
        children=[
            dcc.Store(id="energy-project-central-selection"),
            dcc.Store(id="energy-project-decentral-selection"),
            dcc.Store(id="energy-project-building-selection"),
            html.Div(
                id="energy-project-content",
                className="energy-project-content",
                tabIndex=0,
                role="region",
                **{"aria-label": "Projektinformationen"},
            ),
        ],
    )


# Baut den Bereich für Umgebungsdiagramme.
def _environment_view(initial_view) -> html.Div:
    return html.Div(
        id="energy-environment-view",
        className="general-environment-view energy-content-view",
        style=_view_style(initial_view, "environment", "grid"),
        children=[
            dcc.Checklist(
                id="energy-environment-series",
                className="general-env-series",
                inputClassName="general-env-series-input",
                labelClassName="general-env-series-label",
                options=ENVIRONMENT_SERIES_OPTIONS,
                value=["temperature", "solar"],
            ),
            html.Div(
                className="general-graph-card general-graph-card-flat",
                children=[
                    dcc.Graph(
                        id="energy-environment-graph",
                        figure=environment_figure(None),
                        config={"displayModeBar": False, "responsive": True},
                        className="general-graph",
                    ),
                ],
            ),
        ],
    )


# Baut den Bereich für Bedarfsdiagramme.
def _demand_view(initial_view) -> html.Div:
    return html.Div(
        id="energy-demands-view",
        className="general-environment-view bedarfe-demand-view energy-content-view",
        style=_view_style(initial_view, "demands", "grid"),
        children=[
            dcc.Checklist(
                id="energy-demand-series",
                className="general-env-series bedarfe-demand-series",
                inputClassName="general-env-series-input",
                labelClassName="general-env-series-label",
                options=DEMAND_SERIES_OPTIONS,
                value=[option["value"] for option in DEMAND_SERIES_OPTIONS],
            ),
            html.Div(
                className="general-graph-card general-graph-card-flat",
                children=[
                    dcc.Graph(
                        id="energy-demand-graph",
                        figure=thermal_energy_figure_from_store(None),
                        config={"displayModeBar": False, "responsive": True},
                        className="general-graph bedarfe-demand-graph",
                    ),
                ],
            ),
        ],
    )


# Baut den Bereich für Systemvergleich.
def _system_view(initial_view) -> html.Div:
    return html.Div(
        id="energy-system-view",
        className="energy-comparison-view energy-content-view",
        style=_view_style(initial_view, "system", "grid"),
        children=[
            html.Section(
                id="energy-comparison-chart-column",
                className="energy-comparison-column energy-comparison-chart-column",
                style={"display": "none"},
                children=[
                    html.H2(
                        "Zielvergleich",
                        className="energy-comparison-column-title",
                    ),
                    dcc.Graph(
                        id="energy-comparison-graph",
                        figure=comparison_figure(None),
                        config={"displayModeBar": False, "responsive": True},
                        className="energy-comparison-graph",
                    ),
                    html.Div(
                        "Noch kein vollständiger Vergleichslauf vorhanden.",
                        id="energy-comparison-message",
                        className="energy-comparison-message",
                    ),
                ],
            ),
            html.Section(
                id="energy-economic-column",
                className="energy-comparison-column energy-comparison-variant is-economic",
                style={"display": "none"},
                children=[
                    html.H2(
                        objective_heading("Szenario", "economic"),
                        id="energy-economic-heading",
                        className="energy-comparison-column-title",
                    ),
                    html.Div(
                        id="energy-economic-topology",
                        className="energy-comparison-topology-frame",
                        children=energy_topology_component(
                            view="system",
                            topology=_INITIAL_SYSTEM_SCENE.topology,
                            scene_geometry=_INITIAL_SYSTEM_SCENE.geometry,
                            instance_id="comparison-economic",
                        ),
                    ),
                    form_grid(
                        [], component_id="energy-economic-kpis", class_name="energy-comparison-kpis",
                    ),
                ],
            ),
            html.Section(
                id="energy-ecological-column",
                className="energy-comparison-column energy-comparison-variant is-ecological",
                style={"display": "none"},
                children=[
                    html.H2(
                        objective_heading("Szenario", "ecological"),
                        id="energy-ecological-heading",
                        className="energy-comparison-column-title",
                    ),
                    html.Div(
                        id="energy-ecological-topology",
                        className="energy-comparison-topology-frame",
                        children=energy_topology_component(
                            view="system",
                            topology=_INITIAL_SYSTEM_SCENE.topology,
                            scene_geometry=_INITIAL_SYSTEM_SCENE.geometry,
                            instance_id="comparison-ecological",
                        ),
                    ),
                    form_grid(
                        [], component_id="energy-ecological-kpis", class_name="energy-comparison-kpis",
                    ),
                ],
            ),
        ],
    )


# Baut den Bereich für Energieausweise.
def _certificate_view(initial_view) -> html.Div:
    return html.Div(
        id="energy-certificate-view",
        className="energy-certificate-view energy-content-view",
        style=_view_style(initial_view, "certificate", "flex"),
        children=[
            dcc.Store(id="energy-certificate-document-store"),
            dcc.Store(
                id="energy-certificate-page-store",
                data={"page": 1, "document": None, "previous_clicks": 0, "next_clicks": 0},
            ),
            dcc.Store(id="energy-certificate-folder-status"),
            dcc.Store(id="energy-certificate-ecological-document-store"),
            dcc.Store(
                id="energy-certificate-ecological-page-store",
                data={"page": 1, "document": None, "previous_clicks": 0, "next_clicks": 0},
            ),
            html.Div(
                id="energy-certificate-pages",
                className="energy-certificate-pages",
                children=[
                    _economic_certificate_pane(),
                    _ecological_certificate_pane(),
                ],
            ),
        ],
    )


# Baut den Bereich für Powerflow-Steuerung.
def _powerflow_controls(initial_view) -> html.Div:
    return html.Header(
        id="energy-cluster-panel",
        className="energy-pfc-control-header",
        style=_view_style(initial_view, "pfc", "flex"),
        **{"aria-label": "Steuerung der Powerflow Card"},
        children=[
            html.Div(
                className="energy-pfc-button-row",
                children=[
                    html.Div(
                        id="energy-cluster-options",
                        className="energy-cluster-options",
                        children=html.Div(
                            "Cluster werden geladen …",
                            className="energy-cluster-empty-message heo-field",
                        ),
                    ),
                    html.Button(
                        "⏸  Pause",
                        id="energy-play-button",
                        n_clicks=0,
                        className="energy-play-button konfig-secondary-button",
                    ),
                ],
            ),
            html.Div(
                className="energy-pfc-timeline",
                children=[
                    html.Div(
                        className="energy-pfc-timeline-meta",
                        children=[
                            html.Span(
                                _INITIAL_PFC_FRAME.title,
                                id="energy-pfc-time-label",
                                className="energy-pfc-time-label heo-field__value",
                            ),
                            html.Span(
                                "Zeitschritt 0 / 0",
                                id="energy-pfc-step-label",
                                className="energy-pfc-step-label heo-field__label",
                            ),
                        ],
                    ),
                    dcc.Slider(
                        id="energy-pfc-time-slider",
                        min=0,
                        max=0,
                        step=1,
                        value=0,
                        marks={0: "Beginn"},
                        disabled=True,
                        updatemode="drag",
                        included=True,
                        allow_direct_input=False,
                        className="energy-pfc-time-slider",
                    ),
                ],
            ),
            dcc.Store(id="energy-pfc-step-store", data=0),
        ],
    )


# Baut den Bereich für vorbereitete Topologieansichten.
def _topology_views(initial_view) -> html.Div:
    return html.Div(
        id="energy-svg-frame",
        className="energy-svg-frame energy-topology-stage energy-content-view",
        style=_view_style(initial_view, initial_view if initial_view in {"pfc", "sankey"} else "pfc"),
        children=[
            html.Div(
                id="energy-sankey-frame",
                className="energy-prepared-topology",
                style={"display": "block" if initial_view == "sankey" else "none"},
                children=energy_topology_component(
                    view="sankey",
                    topology=_INITIAL_SYSTEM_SCENE.topology,
                    scene_geometry=_INITIAL_SYSTEM_SCENE.geometry,
                    instance_id="energy-sankey",
                ),
            ),
            html.Div(
                id="energy-pfc-frame",
                className="energy-prepared-topology",
                style={"display": "block" if initial_view == "pfc" else "none"},
                children=energy_topology_component(
                    view="pfc",
                    topology=_INITIAL_PFC_TOPOLOGY,
                    scene_geometry=_INITIAL_SYSTEM_SCENE.geometry,
                    instance_id="energy-pfc",
                    pfc_frame=_INITIAL_PFC_FRAME,
                ),
            ),
        ],
    )


# Baut die Ergebnisnavigation und die Auswahl des Optimierungsfokus.
def _energy_sidebar(initial_view) -> html.Div:
    return sidebar(
        [
            sidebar_panel(
                [
                    sidebar_nav_button(
                        "Projektinfos",
                        "energy-view-project",
                        active=initial_view == "project",
                    ),
                    sidebar_nav_button(
                        "Umgebung",
                        "energy-view-environment",
                        active=initial_view == "environment",
                    ),
                    sidebar_nav_button(
                        "Bedarfe",
                        "energy-view-demands",
                        active=initial_view == "demands",
                    ),
                    sidebar_nav_button(
                        "Energiesystem",
                        "energy-view-system",
                        active=initial_view == "system",
                    ),
                    sidebar_nav_button(
                        "Sankey",
                        "energy-view-sankey",
                        active=initial_view == "sankey",
                    ),
                    sidebar_nav_button(
                        "Powerflow Card",
                        "energy-view-pfc",
                        active=initial_view == "pfc",
                    ),
                    sidebar_nav_button(
                        "DG-Ergebnisse öffnen",
                        "energy-open-dg-results",
                        active=initial_view == "certificate",
                        modifier_class="energy-results-button",
                    ),
                ],
                component_id="energy-view-panel",
                panel_class=f"{SIDEBAR_PANEL_CLASS} konfig-sidebar-panel",
            ),
            sidebar_panel(
                [
                    html.Div(
                        "Optimierungsfokus",
                        className="energy-objective-title",
                    ),
                    sidebar_nav_button(
                        "Ökonomisch",
                        "energy-objective-economic",
                        active=True,
                        disabled=True,
                    ),
                    sidebar_nav_button(
                        "Ökologisch",
                        "energy-objective-ecological",
                        disabled=True,
                    ),
                    sidebar_nav_button(
                        "Vergleich",
                        "energy-objective-comparison",
                        disabled=True,
                    ),
                ],
                component_id="energy-objective-panel",
                panel_class=f"{SIDEBAR_PANEL_CLASS} konfig-sidebar-panel",
                style={
                    "display": "none"
                    if initial_view in {"project", "environment", "demands"}
                    else "flex"
                },
            ),
        ],
        column_class="app-sidebar-column konfig-sidebar",
    )


# Erzeugt den Tab; nach einem Konfigurator-Run kann direkt die Topologie starten.
def create_energy_dashboard(initial_view: str = "project") -> html.Div:
    if initial_view not in ENERGY_VIEWS:
        initial_view = "project"
    # Die Ergebnis-Topologien bleiben beim Ansichtswechsel im DOM erhalten.

    dashboard_front = html.Div(
        className="dashboard-screen energy-system-dashboard",
        children=[
            dcc.Store(id="energy-cluster-store"),
            dcc.Store(id="energy-play-store", data=True),
            dcc.Store(id="energy-comparison-store"),
            dcc.Interval(
                id="energy-ticker",
                interval=1600,
                n_intervals=0,
                disabled=True,
            ),
            _energy_sidebar(initial_view),
            flip_dashboard(
                html.Div(
                    className="glass-panel energy-main-panel",
                    **{"data-heo-capture-target": "main-panel"},
                    children=[
                        _project_view(initial_view),
                        _environment_view(initial_view),
                        _demand_view(initial_view),
                        _system_view(initial_view),
                        _certificate_view(initial_view),
                        _powerflow_controls(initial_view),
                        _topology_views(initial_view),
                    ],
                ),
                name="energy-main",
                info=energy_info_page(initial_view),
                info_content_id="energy-dashboard-info-content",
                info_content_classes=("topology-documentation-content",),
                info_back_classes=("topology-documentation-back",),
            ),
            dcc.Store(id="energy-objective-availability-store"),
            dcc.Store(id="energy-pfc-step-count-store", data=0),
            dcc.Store(id="energy-pfc-mount-store", data=True),
            dcc.Store(id="energy-pfc-prepared-store"),
        ],
    )

    return dashboard_front


Dashboard_Energiesystem = create_energy_dashboard()
