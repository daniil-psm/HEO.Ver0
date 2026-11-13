# Gemeinsamer Datenvertrag für DG-Vergleichsläufe und ihre Ergebnisleser.

COMPARISON_SCHEMA_VERSION = 2
MANIFEST_FILENAME = "manifest.json"
OBJECTIVE_FOCUS = {"economic": 0, "ecological": 1}
DEFAULT_OBJECTIVES = tuple(OBJECTIVE_FOCUS)


# Kennzeichnet ungültige oder fehlende Vergleichsergebnisse.
class DGComparisonError(RuntimeError):
    """Basisklasse für Fehler eines Vergleichslaufs."""
