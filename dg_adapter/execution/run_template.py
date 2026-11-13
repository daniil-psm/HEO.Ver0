# Rendert das DG-Startskript eines Szenarios aus der gespeicherten Vorlage.

from __future__ import annotations

from typing import Any
from pathlib import Path

from ..shared.scenario_names import validate_scenario_name

RUN_FILENAME = "run.py"
RUN_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "templates"
    / "dg_scenario_run.py.template"
)
_SCENARIO_NAME_PLACEHOLDER = "__HEO_SCENARIO_NAME__"


# Erzeugt aus der Vorlage ein ausführbares Startskript mit geprüftem Namen.
def render_scenario_run(scenario_name: Any) -> str:
    name = validate_scenario_name(scenario_name)
    template = RUN_TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count(_SCENARIO_NAME_PLACEHOLDER) != 1:
        raise ValueError(
            "Die Vorlage des Szenario-Startskripts enthält nicht genau einen "
            "Platzhalter für den Szenarionamen."
        )
    source = template.replace(_SCENARIO_NAME_PLACEHOLDER, repr(name))
    compile(source, f"{name}/{RUN_FILENAME}", "exec")
    return source
