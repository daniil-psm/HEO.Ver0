"""Umgebungsdiagramme des Ergebnisse-Tabs."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from heo.display.chart_axes import (
    month_tick_data, build_axis_ticks,
)
from heo.display.chart_series import (
    ENVIRONMENT_SERIES, ENVIRONMENT_SERIES_OPTIONS,
)
from heo.display.chart_theme import (
    AXIS_COLOR, FONT_COLOR, PAPER_BG, PLOT_BG,
)


# Erzeugt ein leeres Diagramm für fehlende oder noch nicht geladene Daten.
def empty_figure(message: str = "Noch keine Daten geladen.") -> go.Figure:
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
        margin={"l": 40, "r": 30, "t": 50, "b": 42},
        xaxis={"visible": False},
        yaxis={"visible": False},
        font={"color": FONT_COLOR, "family": "Segoe UI, Arial, sans-serif"},
    )

    return fig




# Baut das Umgebungsdiagramm für die ausgewählten Wetterreihen.
def environment_figure(
    weather: dict | None,
    selected_series: list[str] | None = None,
) -> go.Figure:
    if not weather:
        return empty_figure("Bitte im Eingabe-Tab eine Wetterdatei laden.")

    selected_series = [
        key for key in (selected_series or [])
        if key in ENVIRONMENT_SERIES
    ][:2]
    x = weather.get("daily_day_index", [])
    month = weather.get("daily_month", [])
    day = weather.get("daily_day", [])
    if not x or not month or not day:
        return empty_figure("Die Wetterdatei enthält keine auswertbaren Tageswerte.")

    date_labels = [
        f"{int(d):02d}.{int(m):02d}"
        for d, m in zip(day, month)
    ]
    month_centers, month_labels, month_boundaries = month_tick_data(weather)
    fig = go.Figure()
    axes = []

    for series_key in selected_series:
        profile = ENVIRONMENT_SERIES[series_key]
        values = weather.get(profile["data_key"], [])
        if len(values) != len(x):
            continue

        values_array = np.asarray(values, dtype=float)
        if not np.isfinite(values_array).all():
            continue

        vmin = float(values_array.min())
        vmax = float(values_array.max())
        vavg = float(values_array.mean())
        tickvals, ticktext = build_axis_ticks(
            vmin=vmin,
            vavg=vavg,
            vmax=vmax,
            step=profile["step"],
            special_decimals=profile["special_decimals"],
            regular_decimals=profile["regular_decimals"],
        )
        span = vmax - vmin
        padding = max(span * 0.055, profile["step"] * 0.12)
        plotted_index = len(axes)
        axes.append(
            {
                "profile": profile,
                "tickvals": tickvals,
                "ticktext": ticktext,
                "range": [vmin - padding, vmax + padding],
            }
        )

        fig.add_trace(
            go.Scatter(
                x=x,
                y=values_array,
                mode="lines",
                name=profile["label"],
                yaxis="y2" if plotted_index == 1 else "y",
                line={"color": profile["color"], "width": 2.7},
                customdata=date_labels,
                hovertemplate=(
                    "<b>%{customdata}</b><br><br>"
                    f"<span style='color:{profile['color']}; font-weight:700;'>"
                    f"{profile['label']}</span>: "
                    f"%{{y:.{profile['hover_decimals']}f}} {profile['unit']}"
                    "<extra></extra>"
                ),
            )
        )

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

    def axis_layout(axis_index: int, side: str) -> dict:
        if axis_index >= len(axes):
            return {"visible": False}
        axis = axes[axis_index]
        profile = axis["profile"]
        layout = {
            "visible": True,
            "title": {
                "text": profile["axis_title"],
                "font": {"color": profile["color"], "size": 18},
                "standoff": 12,
            },
            "side": side,
            "tickmode": "array",
            "tickvals": axis["tickvals"],
            "ticktext": axis["ticktext"],
            "range": axis["range"],
            "showgrid": False,
            "zeroline": False,
            "showline": True,
            "color": profile["color"],
            "linecolor": profile["color"],
            "tickfont": {"color": profile["color"], "size": 15},
            "automargin": True,
        }
        if axis_index == 1:
            layout["overlaying"] = "y"
        return layout

    fig.update_layout(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        margin={"l": 112, "r": 132, "t": 8, "b": 54},
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
            "range": [1, max(x)],
        },
        yaxis=axis_layout(0, "left"),
        yaxis2=axis_layout(1, "right"),
    )

    if not fig.data:
        fig.add_annotation(
            text="Bis zu zwei Profile in der Legende auswählen.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 18, "color": FONT_COLOR},
        )

    return fig
