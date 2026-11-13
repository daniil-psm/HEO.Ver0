# Gemeinsame Aktionsbuttons und Symbole der Humanotop-Oberfläche.

from __future__ import annotations

from typing import Any, Literal

from dash import html


ActionKind = Literal["close", "copy", "duplicate", "trash", "check"]

ACTION_SYMBOLS: dict[ActionKind, str] = {
    "close": "×",
    "copy": "⧉",
    "duplicate": "⧉",
}

ACTION_LABELS: dict[ActionKind, str] = {
    "close": "Schließen",
    "copy": "Kopieren",
    "duplicate": "Duplizieren",
    "trash": "Entfernen",
    "check": "Übernehmen",
}


# Erzeugt einen semantisch und visuell einheitlichen Aktionsbutton.
def action_button(
    action: ActionKind,
    component_id: Any,
    *,
    title: str | None = None,
    class_name: str = "",
    style: dict[str, Any] | None = None,
    n_clicks: int = 0,
    **attributes: Any,
) -> html.Button:
    label = title or ACTION_LABELS[action]
    classes = " ".join(filter(None, (
        "heo-action-button",
        f"heo-action-button--{action}",
        class_name,
    )))
    return html.Button(
        (
            html.Span(className="heo-action-icon", **{"aria-hidden": "true"})
            if action in ("close", "trash", "check") else ACTION_SYMBOLS[action]
        ),
        id=component_id,
        n_clicks=n_clicks,
        type="button",
        className=classes,
        style=style,
        title=label,
        **{"aria-label": label},
        **attributes,
    )


# Gemeinsamer beschrifteter Aktionsbutton in Pillenform.
def pill_action_button(
    label: str,
    component_id: Any,
    *,
    tone: Literal["danger"] = "danger",
    class_name: str = "",
    hidden: bool = False,
) -> html.Button:
    return html.Button(
        label,
        id=component_id,
        type="button",
        hidden=hidden,
        className=" ".join(filter(None, (
            "heo-pill-action-button",
            f"heo-pill-action-button--{tone}",
            class_name,
        ))),
    )
