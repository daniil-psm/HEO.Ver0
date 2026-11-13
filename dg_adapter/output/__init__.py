# Gemeinsame Fehlerklassen der DG-HEO-Ergebnisverarbeitung.


# Basisklasse für fehlende, veraltete oder ungültige DG-Ergebnisse.
class DGResultError(RuntimeError):
    pass


# Kennzeichnet fehlende oder unvollständige DG-Ergebnisdateien.
class DGResultMissingError(DGResultError):
    pass


# Kennzeichnet Ergebnisse, die nicht zu den aktuellen Eingaben gehören.
class DGResultStaleError(DGResultError):
    pass
