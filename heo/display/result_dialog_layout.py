"""Zentrale Zuordnung der Ergebnisgrößen zu den Dialogbereichen.

Die Schlüssel sind die fachlichen Feldbezeichnungen der Ergebniszeilen. Neue
Größen erscheinen zunächst unter „Weitere Größen“, bis sie hier dem
Hauptbereich zugeordnet werden.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Literal


ResultDialogView = Literal["main", "more"]


RESULT_DIALOG_FIELDS: dict[str, ResultDialogView] = {
    # Betriebsmaxima stehen auch dann unter „Weitere Größen“, wenn ihr Name
    # einen Auslegungsbegriff wie Nennleistung enthält.
    "Max. * im Betrieb": "more",
    # Optimierte Dimensionen, Anschlusswerte und Investitionen aller Anlagen.
    "*Nennleistung*": "main",
    "*Speicherkapazität*": "main",
    "Kapazität*": "main",
    "*Anschlussleistung*": "main",
    "Thermische Antriebsleistung*": "main",
    "Speichervolumen*": "main",
    "Installierte Modulfläche*": "main",
    "Kollektorfläche*": "main",
    "Investition*": "main",
    "Auslegungs-COP": "main",
    "Länge Verteilnetz": "main",
    "Nennweite Verteilnetz": "main",
    "Länge Hausanschlüsse": "main",
    "Nennweite Hausanschlüsse": "main",
    # Statische Angaben von Gebäuden, Netz- und Verteilknoten.
    "Gebäudefläche": "main",
    # Betriebswerte der Energiesystem-Ansicht fallen auf „more“ zurück.
    # Diese Energiemengen erscheinen nur in der Sankey-Ansicht.
    "Eingespeicherte Energie": "main",
    "Ausgespeicherte Energie": "main",
    "Verlustenergie": "main",
    "Information": "main",
    "Kopplung Wechsel-/Gleichstrom": "main",
    "Bidirektionaler Betrieb": "main",
    "Wechselstromverteilung": "main",
    "Gleichstromverteilung": "main",
    "Systemkomponente": "main",
    "Keine * Ergebnisdaten verfügbar": "main",
    # Betriebs- und Kostenwerte aus der Auswertung.
    "COP bei Betriebsspitze": "more",
    "Annualisierte Kosten*": "more",
}


def result_dialog_view(label: str) -> ResultDialogView:
    """Liefert den Dialogbereich einer Ergebnisgröße."""

    if label in RESULT_DIALOG_FIELDS:
        return RESULT_DIALOG_FIELDS[label]
    for pattern, view in RESULT_DIALOG_FIELDS.items():
        if "*" in pattern and fnmatchcase(label, pattern):
            return view
    return "more"
