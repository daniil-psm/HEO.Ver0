# Liest DG-Bedarfsreihen für Diagramme im Ergebnisse-Tab.

from __future__ import annotations

import pandas as pd


# Wandelt einen erfolgreichen Bedarfs-Store in einen DataFrame um.
def demand_store_to_dataframe(
    demand_data: dict | None,
    level: str = "daily",
) -> pd.DataFrame | None:
    """Überführt einen erfolgreichen DG-Ergebnis-Store in einen DataFrame."""

    if not demand_data or demand_data.get("status") != "ready":
        return None

    data = demand_data.get(level)
    if not data:
        return None

    frame = pd.DataFrame(data)
    return None if frame.empty else frame


# Erklärt den Ladezustand fehlender DG-Bedarfsdaten.
def demand_status_message(demand_data: dict | None) -> str:
    """Liefert den konkreten Ladezustand für leere Diagramme und Infokarten."""

    if not demand_data:
        return (
            "Noch keine DG-Ergebnisse geladen. Bitte das Szenario speichern und "
            "seine run.py ausführen."
        )
    return str(
        demand_data.get("message")
        or "Für das aktive Szenario sind keine DG-Bedarfsprofile vorhanden."
    )
