# Zentrale, um 180 Grad drehbare Informationsseite für Dashboards.

from __future__ import annotations

from collections.abc import Sequence

from dash import html


InfoSection = tuple[str, str]


# Erzeugt den einheitlichen Inhalt einer Dashboard-Rückseite.
def dashboard_info_page(
    title: str,
    introduction: str,
    sections: Sequence[InfoSection],
) -> html.Div:
    return html.Div(
        className="dashboard-info-copy topology-documentation",
        children=[
            main_panel_info_header(title, introduction),
            html.Div(
                className="dashboard-info-sections",
                children=[
                    html.Section(
                        className="dashboard-info-section",
                        children=[
                            html.H3(section_title),
                            html.P(section_text),
                        ],
                    )
                    for section_title, section_text in sections
                ],
            ),
        ],
    )


# Erzeugt den Öffnen- oder Schließen-Button der Informationsseite
# und setzt die dazugehörigen Attribute für Browsersteuerung und Bedienbarkeit.
def _info_button(*, close: bool) -> html.Button:
    label = "Dashboard anzeigen" if close else "Informationen anzeigen"
    properties = {
        "type": "button",
        "className": (
            "dashboard-info-button dashboard-info-close-button"
            if close
            else "dashboard-info-button"
        ),
        "title": label,
        "aria-label": label,
        "data-dashboard-info-toggle": "close" if close else "open",
    }
    if close:
        properties["tabIndex"] = -1
    else:
        properties["aria-expanded"] = "false"

    return html.Button(
        "×" if close else "i",
        **properties,
    )


# Erzeugt einen Öffner mit eindeutigem Bezug zu seiner Main-Panel-Ansicht.
def main_panel_info_toggle(
    label: str,
    *,
    overlay_id: str,
    class_name: str,
    children: object = "i",
    component_id: str | None = None,
    expanded: bool = False,
) -> html.Button:
    properties = {
        "type": "button",
        "className": class_name,
        "title": label,
        "aria-label": label,
        "aria-controls": overlay_id,
        "aria-expanded": "true" if expanded else "false",
        "data-main-panel-info-toggle": overlay_id,
    }
    if component_id is not None:
        properties.update(id=component_id, n_clicks=0)
    return html.Button(children, **properties)


# Gleiche Titel- und Einleitungszeile für Rückseiten und Einblendungen.
def main_panel_info_header(
    title: str,
    introduction: str,
    *,
    title_id: str | None = None,
) -> html.Header:
    title_properties = {
        "className": "main-panel-info-title",
        "children": title,
    }
    if title_id is not None:
        title_properties["id"] = title_id
    return html.Header(
        className="main-panel-info-header",
        children=[
            html.H2(**title_properties),
            html.P(introduction, className="main-panel-info-introduction"),
        ],
    )


# Eigenständiges Main Panel für Informationen über dem Flip-Panel.
def main_panel_info_overlay(
    *,
    overlay_id: str,
    close_id: str,
    close_label: str,
    title: str,
    introduction: str,
    content: object,
    content_id: str | None = None,
    class_name: str = "",
    hidden: bool = False,
) -> html.Main:
    title_id = f"{overlay_id}-title"
    content_properties = {
        "className": "main-panel-info-body",
        "children": content,
    }
    if content_id is not None:
        content_properties["id"] = content_id
    return html.Main(
        id=overlay_id,
        className=" ".join(filter(None, (
            "glass-panel", "main-panel-surface", "main-panel-info-overlay",
            class_name,
        ))),
        hidden=hidden,
        **{
            "aria-labelledby": title_id,
            "aria-hidden": "true" if hidden else "false",
            "data-heo-capture-target": "main-panel",
        },
        children=[
            html.Button(
                "×",
                id=close_id,
                n_clicks=0,
                type="button",
                className=(
                    "dashboard-info-button dashboard-info-close-button "
                    "main-panel-info-close"
                ),
                title=close_label,
                **{
                    "aria-label": close_label,
                    "data-main-panel-info-close": overlay_id,
                },
            ),
            html.Div(
                className="main-panel-info-scroll",
                children=[
                    main_panel_info_header(
                        title, introduction, title_id=title_id,
                    ),
                    html.Div(**content_properties),
                ],
            ),
        ],
    )


# Legt ein einzelnes Hauptpanel auf zwei Seiten einer Flip-Card.
def flip_dashboard(
    front: object,
    *,
    name: str,
    info: object,
    overlay: object | None = None,
    info_content_id: str | None = None,
    info_content_classes: Sequence[str] = (),
    info_back_classes: Sequence[str] = (),
) -> html.Div:
    info_properties = {
        "className": " ".join(("dashboard-info-content", *info_content_classes)),
        "children": info,
    }
    if info_content_id is not None:
        info_properties["id"] = info_content_id
    back_class_name = " ".join(
        (
            "dashboard-info-face",
            "dashboard-info-back",
            "glass-panel",
            *info_back_classes,
        )
    )

    children = [
        html.Div(
            className="dashboard-info-flip-inner",
            children=[
                html.Div(
                    className="dashboard-info-face dashboard-info-front",
                    **{"aria-hidden": "false"},
                    children=[front],
                ),
                html.Div(
                    className=back_class_name,
                    **{"aria-hidden": "true"},
                    children=[
                        html.Div(
                            html.Div(**info_properties),
                            className="dashboard-info-back-scroll",
                        ),
                    ],
                ),
            ],
        ),
    ]
    overlay_children = [_info_button(close=False), _info_button(close=True)]
    if overlay is not None:
        overlay_children.extend(
            overlay if isinstance(overlay, (list, tuple)) else [overlay]
        )
    children.append(
        html.Div(
            className="dashboard-info-overlay-layer",
            children=overlay_children,
        )
    )

    return html.Div(
        id=f"{name}-dashboard-info-flip",
        className="dashboard-info-flip",
        children=children,
    )
