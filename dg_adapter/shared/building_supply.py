# DG-Prüfung von gespeicherten Versorgungsoptionen und kompatible HEO-Importe.

from heo.model.building_supply import central_connections, cooling_supply, flag

def supply_validation_errors(row):
    """Reject unsupported legacy overrides before running the reference model."""
    errors = []
    expected = cooling_supply(row)
    explicit = str(row.get("cooling_supply") or "").strip().lower()
    if explicit not in {"", "nan", expected}:
        errors.append(
            "Die gespeicherte getrennte Kälteversorgung wird vom Referenz-DG "
            "nicht unterstützt. Kühlung und Heizsystem im Gebäudedialog neu festlegen."
        )
    elif flag(row.get("_cooling_decentral")) and expected == "central":
        errors.append("Dezentrale Kälte bei Wärmenetzanschluss wird vom Referenz-DG nicht unterstützt.")
    if not flag(row.get("electricity_grid"), default=True):
        errors.append("Ein getrennter Gebäude-Stromanschluss wird vom Referenz-DG nicht unterstützt.")
    disabled = row.get("_central_supply_disabled") or {}
    connections = central_connections(row)
    for carrier, label in (("ac", "Strom"), ("heat", "Wärme"), ("dhw", "Warmwasser"), ("cooling", "Kälte")):
        if flag(disabled.get(carrier)) and connections[carrier]:
            errors.append(
                f"Die gespeicherte Trennung der {label}versorgung ist im Referenz-DG "
                "nicht abgebildet. Eine Konfiguration ohne diese Trennung verwenden."
            )
    return errors
