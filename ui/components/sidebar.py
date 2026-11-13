# Wiederverwendbare Seitenleisten für Text und tab-interne Auswahl

from __future__ import annotations

from collections.abc import Iterable, Sequence

from dash import html


SIDEBAR_COLUMN_CLASS = "app-sidebar-column"
SIDEBAR_PANEL_CLASS = "app-sidebar-panel"
SIDEBAR_NAV_BUTTON_CLASS = "app-sidebar-nav-button"
SIDEBAR_NAV_BUTTON_ACTIVE_CLASS = "app-sidebar-nav-button-active"


# Liefert die zentrale CSS-Klasse für einen Navigationsbutton
def sidebar_nav_button_class(
    *,
    active: bool = False,
    modifier_class: str | None = None,
) -> str:
    classes = [SIDEBAR_NAV_BUTTON_CLASS]
    if active:
        classes.append(SIDEBAR_NAV_BUTTON_ACTIVE_CLASS)
    if modifier_class:
        classes.append(modifier_class)
    return " ".join(classes)


# Erzeugt den zentralen, vertikal gestapelten und scrollbaren Panel-Container
def sidebar(
    children: Iterable[object],
    *,
    column_class: str = SIDEBAR_COLUMN_CLASS,
    component_id: str | None = None,
) -> html.Aside:
    properties = {
        "className": column_class,
        "children": list(children),
    }
    if component_id is not None:
        properties["id"] = component_id

    return html.Aside(**properties)


# Gruppiert Bedienelemente innerhalb einer Seitenleiste
def sidebar_panel(
    children: Iterable[object],
    *,
    panel_class: str = SIDEBAR_PANEL_CLASS,
    component_id: str | None = None,
    style: dict | None = None,
) -> html.Div:
    properties = {
        "className": panel_class,
        "children": list(children),
    }
    if component_id is not None:
        properties["id"] = component_id
    if style is not None:
        properties["style"] = style

    return html.Div(**properties)


# Erzeugt einen einheitlichen Auswahlbutton für eine Seitenleiste
def sidebar_button(
    label: str,
    component_id: str | dict,
    class_name: str,
) -> html.Button:
    return html.Button(
        label,
        id=component_id,
        n_clicks=0,
        className=class_name,
    )


# Erzeugt einen Auswahlbutton im gemeinsamen Sidebar-Design
def sidebar_nav_button(
    label: str,
    component_id: str | dict,
    *,
    active: bool = False,
    modifier_class: str | None = None,
    disabled: bool = False,
) -> html.Button:
    button = sidebar_button(
        label,
        component_id,
        sidebar_nav_button_class(
            active=active,
            modifier_class=modifier_class,
        ),
    )
    button.disabled = disabled
    return button


# Kurzform für eine Seitenleiste mit genau einem Auswahlpanel
def selection_sidebar(
    buttons: Sequence[object],
    *,
    column_class: str = SIDEBAR_COLUMN_CLASS,
    panel_class: str = SIDEBAR_PANEL_CLASS,
) -> html.Aside:
    return sidebar(
        [sidebar_panel(buttons, panel_class=panel_class)],
        column_class=column_class,
    )


# Erzeugt eine Textbox wie auf dem Startbildschirm
def text_sidebar(
    *,
    title: str,
    paragraphs: Sequence[str],
    class_name: str,
    logo_src: str | None = None,
    logo_alt: str = "Humanotop",
) -> html.Aside:
    children: list[object] = []
    if logo_src:
        children.append(
            html.Img(
                src=logo_src,
                alt=logo_alt,
                draggable="false",
                className="header-logo",
            )
        )

    children.append(html.H2(title, className="dashboard-title"))

    for index, paragraph in enumerate(paragraphs):
        if index:
            children.append(html.Br())
        children.append(html.P(paragraph, className="dashboard-text"))

    return html.Aside(className=class_name, children=children)
