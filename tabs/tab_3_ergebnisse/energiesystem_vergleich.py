"""Vergleichsdarstellung der ökonomischen und ökologischen Optimierung."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from dash import html
from ui.components.units import readonly_unit_value
from ui.components.form_grid import form_grid

from heo.display.comparison import (
    OBJECTIVE_PRESENTATION, numeric_value, comparison_summary, objective_heading, formatted_kpi, report_items, summary_items,
)


# Stellt eine Vergleichskennzahl als Karte dar.
def _kpi_card(
    label: str, value: Any, unit: str = "", decimals: int = 1,
    *, description: str, parameter_key: str = "",
) -> html.Div:
    formatted = formatted_kpi(value, unit, decimals) if numeric_value(value) is not None else str(value or "–")
    content = (
        readonly_unit_value(parameter_key or f"kpi:{label}", float(numeric_value(value)), unit)
        if unit and numeric_value(value) is not None else formatted
    )
    return html.Div(
        className="energy-comparison-kpi heo-field-cell",
        tabIndex=0,
        **{
            "data-kpi-description": description, "aria-label": f"{label}: {formatted}",
            "data-form-item": "field", "data-form-key": parameter_key or f"kpi:{label}",
        },
        children=[
            html.Span(label, className="energy-comparison-kpi-label", **{"data-form-label": "true"}),
            html.Strong(content, className="energy-comparison-kpi-value", **{
                "data-form-control": "true",
                **({"data-form-value": "true"} if isinstance(content, str) else {}),
            }),
        ],
    )


# Rendert die im HEO-Katalog vorbereiteten Berichtszeilen als Dash-Karten.
def _report_cards(report: dict[str, Any]) -> tuple[list[html.Div], list[Any]]:
    main_items, grouped_items = report_items(report)
    main_cards = [_kpi_card(**{key: item[key] for key in ("label", "value", "unit", "decimals", "description", "parameter_key")}) for item in main_items]
    sections: list[Any] = []
    for heading, is_device, items in grouped_items:
        cards = [_kpi_card(**{key: item[key] for key in ("label", "value", "unit", "decimals", "description", "parameter_key")}) for item in items]
        if is_device:
            sections.append(html.Details(open=True, className="energy-comparison-kpi-section", children=[
                html.Summary(f"{heading} · {len(cards)} Werte"),
                form_grid(cards, class_name="energy-comparison-detail-grid"),
            ]))
        else:
            sections.append(html.Div(className="energy-comparison-kpi-section", children=[
                html.H3(heading), form_grid(cards, class_name="energy-comparison-detail-grid"),
            ]))
    return main_cards, sections


# Zeigt Haupt-KPIs und ausklappbare Zusatzwerte des DG-Ergebnislaufs.
def variant_kpi_cards(bundle: dict[str, Any] | None) -> list[html.Div]:
    main_items, more_items = summary_items(bundle)
    cards = [_kpi_card(**item) for item in main_items]
    other_summary = [_kpi_card(**item) for item in more_items]
    report = (bundle or {}).get("kpi_report") or {}
    report_main, report_more = _report_cards(report)
    cards.extend(report_main)
    if other_summary or report_more:
        cards.append(html.Details(
            className="energy-comparison-kpi-details heo-field-cell",
            **{"data-form-section": "true", "data-form-full-width": "true"},
            children=[
                html.Summary("Weitere Kennzahlen", **{"data-form-header": "true"}),
                html.Div(
                    className="energy-comparison-kpi-detail-content",
                    children=[
                        form_grid(other_summary, class_name="energy-comparison-detail-grid")
                        if other_summary else None,
                        *report_more,
                    ],
                ),
            ],
        ))
    return cards


# Trägt Jahreskosten über jährlichen Emissionen für beide Ziele auf.
def comparison_figure(comparison: dict[str, Any] | None) -> go.Figure:
    comparison = comparison or {}
    variants = comparison.get("variants") or {}
    scenario_name = str(comparison.get("scenario_name") or "Szenario")
    figure = go.Figure()

    for objective in ("economic", "ecological"):
        bundle = variants.get(objective)
        summary = comparison_summary(bundle)
        emissions = numeric_value(summary.get("average_co2_emissions_t_per_a"))
        costs = numeric_value(summary.get("annualized_total_cost_eur_per_a"))
        if emissions is None or costs is None:
            continue
        presentation = OBJECTIVE_PRESENTATION[objective]
        figure.add_trace(
            go.Scatter(
                x=[emissions],
                y=[costs],
                mode="markers+text",
                name=presentation["short_label"],
                text=[presentation["short_label"]],
                textposition="top center",
                marker={
                    "size": 17,
                    "color": presentation["color"],
                    "line": {"width": 2, "color": "rgba(255,255,255,.88)"},
                },
                customdata=[[scenario_name]],
                hovertemplate=(
                    "<b>%{customdata[0]} – "
                    + presentation["short_label"]
                    + "</b><br>Emissionen: %{x:,.2f} t/a"
                    "<br>Kosten: %{y:,.0f} €/a<extra></extra>"
                ),
            )
        )

    if not figure.data:
        figure.add_annotation(
            text=str(
                comparison.get("message")
                or "Noch kein vollständiger Vergleichslauf vorhanden."
            ),
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            align="center",
            font={"size": 15, "color": "rgba(255,255,255,.72)"},
        )

    figure.update_layout(
        title={
            "text": "Kosten und Emissionen",
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 18, "color": "rgba(160,240,225,.95)"},
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "rgba(255,255,255,.88)", "family": "Segoe UI, Arial, sans-serif"},
        margin={"l": 70, "r": 22, "t": 58, "b": 62},
        showlegend=False,
        hovermode="closest",
        xaxis={
            "title": "Jährliche Emissionen [t CO₂/a]",
            "gridcolor": "rgba(255,255,255,.13)",
            "zerolinecolor": "rgba(255,255,255,.2)",
            "color": "rgba(155,230,220,.85)",
            "rangemode": "tozero",
        },
        yaxis={
            "title": "Jährliche Kosten [€/a]",
            "gridcolor": "rgba(255,255,255,.13)",
            "zerolinecolor": "rgba(255,255,255,.2)",
            "color": "rgba(155,230,220,.85)",
            "rangemode": "tozero",
            "tickformat": ",.0f",
        },
    )
    return figure
