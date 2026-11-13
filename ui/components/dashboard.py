# Rendert die Dashboard-Hülle mit Ladeanzeige und Platzhalter für den aktiven Tab.

from __future__ import annotations

from dash import dcc, html

# Erzeugt den Inhaltsbereich, den der Tab-Callback befüllt.
def create_dashboard() -> html.Main:
    return html.Main(
        className="dashboard-area",
        children=[
            dcc.Loading(
                id="dashboard-loading",
                type="circle",
                color="var(--schriftfarbe_weiss)",
                parent_className="dashboard-loading",
                delay_hide=300,
                target_components={
                    "tab-content": "children",
                    "energy-comparison-store": "data",
                    "energy-comparison-graph": "figure",
                    "energy-project-content": "children",
                    "energy-environment-graph": "figure",
                    "energy-demand-graph": "figure",
                    "energy-certificate-document-store": "data",
                    "energy-certificate-page-image": "src",
                },
                children=html.Div(id="tab-content", className="tab-content"),
            ),
        ],
    )


Dashboard = create_dashboard()
