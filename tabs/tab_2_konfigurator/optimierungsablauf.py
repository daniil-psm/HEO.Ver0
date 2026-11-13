"""Dokumentation des Optimierungsansatzes und der Modellbildung im DG."""

from __future__ import annotations

from dash import html

from ui.components.dashboard_info import main_panel_info_header


# False stellt die Konfigurator-Rückseite ohne Optimierungsdokumentation her.
OPTIMIZATION_PROCESS_INFO_ENABLED = True

OPTIMIZATION_PROCESS_TITLE = "Optimierungsablauf im DG"
OPTIMIZATION_PROCESS_INTRODUCTION = (
    "Der District Generator (DG) nutzt eine sequenzielle Auslegungs- und "
    "Betriebsoptimierung für die zentrale Energieversorgung. Diese Dokumentation "
    "erläutert den Optimierungsansatz, die mathematischen Grundlagen und die "
    "Modellierung im DG – von Gebäude-, Standort- und Nutzungsdaten über "
    "Bedarfsprofile bis zu technischen, ökonomischen und ökologischen "
    "Modellgleichungen."
)
# Beide Einstiegspunkte zeigen dieselben fachlichen Grundlagen.
OPTIMIZATION_PROCESS_SINGLE_INTRODUCTION = OPTIMIZATION_PROCESS_INTRODUCTION

_DOCUMENTATION_ASSETS = "/assets/images"


# Bindet die Originalabbildung ohne Verlinkung ein.
def _documentation_figure(
    filename: str, *, alt: str,
) -> html.Figure:
    return html.Figure(
        className="konfig-process-figure",
        children=html.Img(
            src=f"{_DOCUMENTATION_ASSETS}/{filename}",
            alt=alt,
            className="konfig-process-image",
        ),
    )


# Zeigt die drei fachlichen Abschnitte der Optimierungsdokumentation.
def optimization_process_page(
    *, instance: str = "back", include_header: bool = True,
    single_run: bool = False,
) -> html.Div:
    return html.Div(
        className="dashboard-info-copy topology-documentation konfig-process-documentation",
        lang="de",
        children=[
            *([main_panel_info_header(
                OPTIMIZATION_PROCESS_TITLE,
                OPTIMIZATION_PROCESS_SINGLE_INTRODUCTION
                if single_run else OPTIMIZATION_PROCESS_INTRODUCTION,
            )] if include_header else []),
            html.Div(
                className="konfig-process-sections",
                children=[
                    html.Section(
                        className="konfig-process-section",
                        **{"aria-labelledby": f"konfig-process-model-{instance}"},
                        children=[
                            html.H3(
                                "Optimierungsmodell Energiesystem",
                                id=f"konfig-process-model-{instance}",
                            ),
                            _documentation_figure(
                                "Optimierung1.png",
                                alt=(
                                    "Vergleich monolithischer und sequenzieller Optimierung: "
                                    "gemeinsame Auslegungs- und Betriebsoptimierung sowie "
                                    "getrennte Auslegungs- und Betriebsoptimierung "
                                    "beim District Generator."
                                ),
                            ),
                        ],
                    ),
                    html.Section(
                        className="konfig-process-section",
                        **{"aria-labelledby": f"konfig-process-math-{instance}"},
                        children=[
                            html.H3(
                                "Mathematische Grundlagen",
                                id=f"konfig-process-math-{instance}",
                            ),
                            _documentation_figure(
                                "Optimierung2.png",
                                alt=(
                                    "Tabelle der Optimierungsbausteine: Zielfunktion, "
                                    "Eingangsparameter, Entscheidungsvariablen, "
                                    "Randbedingungen und Bewertungsgrößen mit "
                                    "Beispielen und der Anzahl je Komponente, "
                                    "Profil und Zeitschritt."
                                ),
                            ),
                        ],
                    ),
                    html.Section(
                        className="konfig-process-section",
                        **{"aria-labelledby": f"konfig-process-dg-{instance}"},
                        children=[
                            html.H3(
                                "Modellierung im DG",
                                id=f"konfig-process-dg-{instance}",
                            ),
                            _documentation_figure(
                                "Optimierung3.png",
                                alt=(
                                    "Optimierungsablauf im District Generator: "
                                    "Quartiersmodell und Profilgenerierung, "
                                    "dezentrale Anlagen und Netze, Clustering, "
                                    "Auslegungsoptimierung als LP und "
                                    "Betriebsoptimierung als MILP."
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
