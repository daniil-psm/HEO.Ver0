# Globale, kompakte Entwicklerwerkzeuge am rechten Fensterrand.

from __future__ import annotations

from dash import Input, Output, callback, dcc, html


# Erzeugt einen rein ikonischen Werkzeugknopf mit Browser-Tooltip.
def _tool_button(tool: str, icon_class: str, label: str) -> html.Button:
    return html.Button(
        html.Span("", className=f"dev-tools-icon {icon_class}"),
        type="button",
        className="dev-tools-button",
        title=label,
        disable_n_clicks=True,
        **{
            "aria-label": label,
            "data-dev-tool": tool,
        },
    )


# Rendert den Hover-Tab und die nach oben ausfahrende Glasspanel-Leiste.
def create_dev_tools() -> html.Aside:
    return html.Aside(
        id="dev-tools-dock",
        className="dev-tools-dock",
        **{"aria-label": "Entwicklerwerkzeuge"},
        children=[
            dcc.Store(id="dev-topology-static-store", data=False),
            html.Div(
                id="dev-tools-panel",
                className="dev-tools-panel glass-panel",
                role="toolbar",
                **{
                    "aria-label": "Entwicklerwerkzeuge",
                    "aria-hidden": "true",
                },
                children=[
                    html.Button(
                        html.Span("", className="dev-tools-theme-track"),
                        type="button",
                        role="switch",
                        className="dev-tools-button dev-tools-theme-switch",
                        title="Dark Mode",
                        disable_n_clicks=True,
                        **{
                            "aria-label": "Dark Mode",
                            "aria-checked": "false",
                            "data-dev-tool": "dark-mode",
                        },
                    ),
                    html.Button(
                        html.Span("±", className="dev-tools-icon"),
                        id="dev-topology-static-button",
                        type="button", n_clicks=0,
                        className="dev-tools-button",
                        title="Statische Topologie im Konfigurator anzeigen",
                        **{
                            "aria-label": "Statische Topologie im Konfigurator anzeigen",
                            "aria-pressed": "false",
                        },
                    ),
                    _tool_button(
                        "grid",
                        "dev-tools-icon-grid",
                        "Rasterlinien einblenden",
                    ),
                    _tool_button(
                        "capture-main-panel",
                        "dev-tools-icon-panel",
                        "Main Panel in die Zwischenablage kopieren",
                    ),
                    _tool_button(
                        "capture-dashboard",
                        "dev-tools-icon-camera",
                        "Dashboard in die Zwischenablage kopieren",
                    ),
                    _tool_button(
                        "capture-app",
                        "dev-tools-icon-app",
                        "App-Ansicht in die Zwischenablage kopieren",
                    ),
                ],
            ),
            html.Button(
                html.Span("", className="dev-tools-nav-chevron"),
                id="dev-tools-nav-button",
                type="button",
                className="dev-tools-nav-button",
                title="Entwicklerwerkzeuge öffnen",
                disable_n_clicks=True,
                **{
                    "aria-label": "Entwicklerwerkzeuge öffnen",
                    "aria-controls": "dev-tools-panel",
                    "aria-expanded": "false",
                    "data-dev-tools-toggle": "true",
                },
            ),
        ],
    )


DevTools = create_dev_tools()


# Schaltet ausschließlich die Entwicklervorschau; Projektdaten bleiben unverändert.
@callback(
    Output("dev-topology-static-store", "data"),
    Output("dev-topology-static-button", "title"),
    Output("dev-topology-static-button", "aria-label"),
    Output("dev-topology-static-button", "aria-pressed"),
    Output("dev-topology-static-button", "className"),
    Input("dev-topology-static-button", "n_clicks"),
)
def toggle_static_topology(n_clicks):
    static = bool((n_clicks or 0) % 2)
    label = (
        "Bearbeitbare Topologie im Konfigurator anzeigen"
        if static else "Statische Topologie im Konfigurator anzeigen"
    )
    return static, label, label, str(static).lower(), (
        "dev-tools-button is-active" if static else "dev-tools-button"
    )
