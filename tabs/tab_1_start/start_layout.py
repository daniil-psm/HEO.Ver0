# Baut die statische Startansicht der HEO-Anwendung.

"""Layout des Start-Tabs."""

from dash import html

from ui.components.sidebar import text_sidebar


Dashboard_Home = html.Div(
    className="dashboard-screen home-dashboard",
    children=[
        text_sidebar(
            title="Humanotop Energiesystem-Optimierer",
            class_name="glass-panel home-textbox",
            paragraphs=[
                "Planen und vergleichen Sie Energiesysteme für Ihren Standort.",
                """Charakterisieren Sie im Konfigurator die Rahmenbedingungen
                Ihres Energiesystems, starten Sie die Optimierung und untersuchen
                Sie das optimierte Energiesystem im „Ergebnisse“-Tab.""",
            ],
        ),
        html.Div(className="glass-panel home-main-panel"),
    ],
)
