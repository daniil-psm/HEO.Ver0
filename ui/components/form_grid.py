# Ordnet Dash-Formularfelder in gemeinsamen Rasterzellen und Formularrastern an.

from __future__ import annotations

from typing import Any, Iterable

from dash import html

from heo.display.form_content import LayoutProfile

FIELD_GRID_CLASS = "heo-field-grid"
FIELD_CELL_CLASS = "heo-field-cell"


# Kapselt Inhalt in einer Rasterzelle und übernimmt dessen Feldspannen.
def form_cell(
    child: Any,
    *,
    row: int | None = None,
    column: int | None = None,
    row_span: int | None = None,
    column_span: int | None = None,
    class_name: str = "",
    full_width: bool = False,
) -> html.Div:
    child_props = (
        child.to_plotly_json().get("props", {})
        if hasattr(child, "to_plotly_json") else {}
    )
    resolved_row_span = int(
        row_span
        if row_span is not None
        else child_props.get("data-field-row-span") or 1
    )
    resolved_column_span = int(
        column_span
        if column_span is not None
        else child_props.get("data-field-column-span") or 1
    )

    classes = ["konfig-form-cell", FIELD_CELL_CLASS]
    if resolved_row_span > 1:
        classes.append("konfig-form-cell--row-span")
    if resolved_column_span > 1:
        classes.append("konfig-form-cell--column-span")
    if class_name:
        classes.append(class_name)
    style: dict[str, str] = {}
    if row is not None:
        style["gridRow"] = f"{row} / span {max(1, resolved_row_span)}"
    if column is not None:
        style["gridColumn"] = f"{column} / span {max(1, resolved_column_span)}"
    return html.Div(
        child,
        className=" ".join(classes),
        style=style or None,
        **{
            "hidden": bool(child_props.get("hidden", False)),
            "data-form-row": row,
            "data-form-column": column,
            "data-form-row-span": resolved_row_span,
            "data-form-column-span": resolved_column_span,
            "data-form-full-width": "true" if full_width else "false",
        },
    )



# Erzeugt das gemeinsame Raster für Formulare und Einblendungen.
def form_grid(
    cells: Iterable[Any], *, columns: int | str = "auto", class_name: str = "",
    layout_profile: LayoutProfile = "automatic",
    component_id: str | None = None,
) -> html.Div:
    classes = ["konfig-form-grid", FIELD_GRID_CLASS]
    classes.append("konfig-form-grid--auto" if columns == "auto" else "konfig-form-grid--placed")
    if class_name:
        classes.append(class_name)
    style = {"--konfig-form-columns": str(columns)} if columns != "auto" else None
    return html.Div(
        list(cells), className=" ".join(classes), style=style,
        **{
            "data-form-layout-profile": layout_profile,
            "data-form-planner": "automatic" if columns == "auto" and layout_profile == "automatic" else "fixed",
            **({"id": component_id} if component_id else {}),
        },
    )



# Übernimmt die Feldmetadaten für eine dynamische Parameterliste.
def automatic_form_grid(
    children: Iterable[Any], *, class_name: str = "", keep_together: bool = False,
) -> html.Div:
    cells = [form_cell(child) for child in children]
    grid = form_grid(cells, columns="auto", class_name=class_name)
    # Zusammengehörige Zusatzfelder bilden eine Zeile, solange sie gemeinsam
    # in den Dialog passen. Die tatsächlichen Breiten bestimmt der Browser.
    setattr(grid, "data-form-layout", "group" if keep_together else "tiles")
    return grid

