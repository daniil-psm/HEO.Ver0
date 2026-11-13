# Kopfbereich der Anwendung mit Logo und Hauptnavigation.

from __future__ import annotations

from dataclasses import dataclass

from dash import html


# Beschreibt einen Eintrag der globalen Tab-Navigation.
@dataclass(frozen=True)
class TabSpec:
    label: str
    value: str


TAB_SPECS = (
    TabSpec("START", "dashboard-home"),
    TabSpec("KONFIGURATOR", "dashboard-konfigurator"),
    TabSpec("ERGEBNISSE", "dashboard-energiesystem"),
)


# Erzeugt Logo und Navigation der HEO-Anwendung.
def create_header(default_tab: str = "dashboard-home") -> html.Header:
    return html.Header(
        className="app-header",
        children=[
            html.Div(
                className="header-logo-area",
                children=[
                    html.Img(
                        src="/assets/images/Logo grün.png",
                        alt="Humanotop",
                        draggable="false",
                        className="header-logo",
                    ),
                ],
            ),
            html.Div(
                className="header-nav-area",
                children=[
                    html.Div(
                        className="nav-tabs-parent",
                        children=[
                            html.Div(
                                id="dash-tabs",
                                className="nav-tabs",
                                children=[
                                    html.Button(
                                        tab.label,
                                        id={"type": "main-nav-tab", "value": tab.value},
                                        n_clicks=0,
                                        type="button",
                                        disabled=(
                                            tab.value == "dashboard-energiesystem"
                                        ),
                                        className=(
                                            "nav-tab nav-tab-selected"
                                            if tab.value == default_tab
                                            else "nav-tab"
                                        ),
                                    )
                                    for tab in TAB_SPECS
                                ],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )


Header = create_header()
