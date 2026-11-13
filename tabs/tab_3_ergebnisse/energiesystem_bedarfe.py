"""Bedarfsdiagramme des Ergebnisse-Tabs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from heo.display.chart_axes import (
    month_tick_data_from_daily, nice_axis_step, demand_axis_ticks,
)
from heo.display.chart_series import (
    DEMAND_SERIES, DEMAND_SERIES_OPTIONS,
)
from heo.display.chart_theme import AXIS_COLOR, FONT_COLOR, PAPER_BG, PLOT_BG

from dg_adapter.output.demand_data import demand_store_to_dataframe


# Erzeugt ein leeres Diagramm für fehlende oder noch nicht geladene Daten.
def empty_figure(message: str = "Noch keine Daten vorhanden.") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 18, "color": FONT_COLOR},
    )
    fig.update_layout(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": FONT_COLOR, "family": "Segoe UI, Arial, sans-serif"},
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    return fig






# Zeigt thermische und elektrische Tagesbedarfe im General-Diagrammstil.
def thermal_energy_figure_from_store(
    demand_data: dict | None,
    selected_series: list[str] | None = None,
) -> go.Figure:
    demand = demand_store_to_dataframe(demand_data, level="daily")
    if demand is None or demand.empty:
        from dg_adapter.output.demand_data import demand_status_message

        return empty_figure(demand_status_message(demand_data))

    if selected_series is None:
        selected_series = list(DEMAND_SERIES)
    selected_series = [
        key for key in selected_series
        if key in DEMAND_SERIES and DEMAND_SERIES[key]["column"] in demand
    ]

    fig = go.Figure()
    plotted_values = []
    date_labels = demand["date_label"].astype(str).tolist()
    for key in selected_series:
        profile = DEMAND_SERIES[key]
        values = np.asarray(demand[profile["column"]], dtype=float)
        if not np.isfinite(values).all():
            continue
        plotted_values.append(values)
        fig.add_trace(
            go.Scatter(
                x=demand["day_index"],
                y=values,
                mode="lines",
                name=profile["label"],
                line={"color": profile["color"], "width": 2.7},
                customdata=date_labels,
                hovertemplate=(
                    "<b>%{customdata}</b><br><br>"
                    f"<span style='color:{profile['color']}; font-weight:700;'>"
                    f"{profile['label']}</span>: "
                    "%{y:.1f} kWh/Tag"
                    "<extra></extra>"
                ),
            )
        )

    month_centers, month_labels, month_boundaries = month_tick_data_from_daily(demand)
    shapes = [
        {
            "type": "line",
            "xref": "x",
            "yref": "paper",
            "x0": boundary,
            "x1": boundary,
            "y0": 0,
            "y1": 1,
            "line": {"color": "rgba(255,255,255,0.12)", "width": 1},
        }
        for boundary in month_boundaries
    ]

    if plotted_values:
        combined_values = np.concatenate(plotted_values)
        vmin = float(combined_values.min())
        vmax = float(combined_values.max())
        vavg = float(combined_values.mean())
        step = nice_axis_step(vmin, vmax)
        tickvals, ticktext = demand_axis_ticks(vmin, vavg, vmax, step)
        span = vmax - vmin
        padding = max(span * 0.055, step * 0.12)
        axis_range = [max(0.0, vmin - padding), vmax + padding]
        yaxis = {
            "visible": True,
            "title": {
                "text": "Täglicher Bedarf [kWh/Tag]",
                "font": {"color": AXIS_COLOR, "size": 18},
                "standoff": 12,
            },
            "tickmode": "array",
            "tickvals": tickvals,
            "ticktext": ticktext,
            "range": axis_range,
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "color": AXIS_COLOR,
            "linecolor": AXIS_COLOR,
            "tickfont": {"color": AXIS_COLOR, "size": 15},
            "automargin": True,
        }
    else:
        yaxis = {"visible": False}

    fig.update_layout(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        margin={"l": 112, "r": 42, "t": 8, "b": 54},
        showlegend=False,
        shapes=shapes,
        hovermode="closest",
        hoverdistance=60,
        spikedistance=60,
        font={
            "color": FONT_COLOR,
            "family": "Segoe UI, Arial, sans-serif",
            "size": 17,
        },
        hoverlabel={
            "bgcolor": "rgba(18, 34, 28, 0.94)",
            "bordercolor": "rgba(230,235,230,0.36)",
            "font": {
                "color": "rgba(255,255,255,0.96)",
                "size": 17,
                "family": "Segoe UI, Arial, sans-serif",
            },
            "align": "left",
        },
        xaxis={
            "tickmode": "array",
            "tickvals": month_centers,
            "ticktext": month_labels,
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "color": AXIS_COLOR,
            "linecolor": AXIS_COLOR,
            "tickfont": {"color": AXIS_COLOR, "size": 16},
            "title": None,
            "range": [1, int(demand["day_index"].max())],
        },
        yaxis=yaxis,
    )

    if not fig.data:
        fig.add_annotation(
            text="Mindestens einen Bedarf in der Legende auswählen.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 18, "color": FONT_COLOR},
        )

    return fig
