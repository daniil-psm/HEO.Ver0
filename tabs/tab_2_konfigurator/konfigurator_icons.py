"""Einheitliche, dekorative Sidebar-Icons für den Konfigurator."""

from __future__ import annotations

from dash import html


# Hält das Buttonlabel lesbar und blendet das SVG für Screenreader aus.
def sidebar_icon_content(icon: str, label: str) -> list[html.Span]:
    return [
        html.Span(
            className=f"konfig-action-icon konfig-action-icon-{icon}",
            **{"aria-hidden": "true"},
        ),
        html.Span(label),
    ]
