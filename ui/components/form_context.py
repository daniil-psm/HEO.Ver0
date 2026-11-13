# Übergibt stabile Formular-IDs und den Öffnungszustand an gemeinsame Renderer.

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from dash import html


# Beschreibt den Namensraum einer Formularansicht ohne globale Renderzustände.
@dataclass(frozen=True)
class FormRenderContext:
    prefix: str = ""
    scope: str = ""
    editable_types: frozenset[str] = frozenset()
    open_sections: Mapping[str, bool] = field(default_factory=dict)

    # Leitet einen Unterbereich aus einem fachlichen Schlüssel ab.
    def child(self, key: str) -> FormRenderContext:
        return replace(self, scope=f"{self.scope}/{key}" if self.scope else key)

    # Vergibt die endgültige ID bereits beim Erzeugen des Bedienelements.
    def control_id(self, original: Any) -> Any:
        if not self.prefix or original is None:
            return original
        editable = isinstance(original, dict) and original.get("type") in self.editable_types
        return {
            "type": f"{self.prefix}-control" if editable else f"{self.prefix}-decoration",
            "scope": self.scope,
            "control": json.dumps(original, sort_keys=True),
        }

    # Erzeugt einen Detailbereich; geschlossene interaktive Bereiche bleiben leer.
    def details(
        self, title: str, content: Any, *, key: str,
        default_open: bool = False, class_name: str = "",
        component_id: Any = None,
    ) -> html.Details:
        if not self.prefix:
            props = {"id": component_id} if component_id is not None else {}
            return html.Details(
                [html.Summary(title), content], open=default_open,
                className=class_name, **props,
            )
        section_key = self.child(key).scope
        opened = bool(self.open_sections.get(section_key, default_open))
        summary = html.Summary(title, id={
            "type": f"{self.prefix}-summary", "key": section_key,
            "default_open": opened,
        })
        return html.Details(
            [summary, content] if opened else [summary],
            id={"type": f"{self.prefix}-details", "key": section_key},
            open=opened, className=class_name,
        )


# Ohne expliziten Kontext bleiben bestehende Dialog-IDs und native Details erhalten.
DEFAULT_FORM_CONTEXT = FormRenderContext()
