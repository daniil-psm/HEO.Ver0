"""Wählt verfügbare HEO-Ergebnisvarianten und liest den Szenarionamen aus dem Entwurf."""

from __future__ import annotations

def configured_scenario_name(config_state: dict | None) -> str:
    """Liest den bereinigten Szenarionamen aus dem aktuellen Konfigurationszustand."""

    return str(
        ((config_state or {}).get("values") or {}).get("SCENARIO_NAME") or ""
    ).strip()

def comparison_is_available(comparison: dict | None) -> bool:
    """Prüft, ob ein fertiges Vergleichsbündel mit wirtschaftlicher und ökologischer Variante vorliegt."""

    comparison = comparison or {}
    variants = comparison.get("variants") or {}
    manifest = comparison.get("manifest") or {}
    return (
        comparison.get("status") == "ready"
        and all(key in variants for key in ("economic", "ecological"))
        and manifest.get("comparison_complete") is not False
    )

def system_objective(
    objective: str | None, variants: dict, *, comparison_available: bool = True
) -> str:
    """Wählt nur Fokusse mit geladenem Ergebnis für die Systemansicht."""

    available = tuple(key for key in ("economic", "ecological") if key in variants)
    if not available:
        return "comparison"
    if objective == "comparison" and len(available) == 2 and comparison_available:
        return "comparison"
    if objective in available:
        return objective
    return available[0]

