"""Zentrale HEO-Texte und Schlüssel der Ergebnisansichten."""

from __future__ import annotations

ENERGY_VIEWS = (
    "project",
    "environment",
    "demands",
    "system",
    "sankey",
    "pfc",
    "certificate",
)

ENERGY_VIEW_INFO = {
    "project": (
        "Projektinfos",
        "Diese Ansicht fasst die verwendete Datengrundlage des berechneten Szenarios zusammen.",
        [
            ("Projekt", "Zeigt zentrale Szenariodaten und die gewählten Randbedingungen der Optimierung."),
            ("Standort und Wetter", "Dokumentiert den Standort sowie die für die Berechnung verwendeten Wetterdaten."),
            ("Gebäude", "Listet die konfigurierte Gebäudestruktur und ihre wesentlichen Eigenschaften auf."),
        ],
    ),
    "environment": (
        "Umgebung",
        "Hier werden die zeitabhängigen Umgebungsbedingungen des Szenarios dargestellt.",
        [
            ("Zeitreihen", "Das Diagramm zeigt unter anderem Außentemperatur und solare Einstrahlung über das Jahr."),
            ("Auswahl", "Über die Auswahl oberhalb des Diagramms lassen sich bis zu zwei Reihen gleichzeitig vergleichen."),
            ("Einordnung", "Die Daten bilden eine wesentliche Grundlage für Erzeugung und thermische Bedarfe."),
        ],
    ),
    "demands": (
        "Bedarfe",
        "Diese Ansicht visualisiert die aus dem Gebäudemodell abgeleiteten Energiebedarfe.",
        [
            ("Profile", "Die Verläufe zeigen Wärme-, Kälte- und weitere verfügbare Bedarfsreihen über den Berechnungszeitraum."),
            ("Vergleich", "Die Schalter oberhalb des Diagramms blenden einzelne Reihen für einen übersichtlichen Vergleich ein oder aus."),
            ("Datengrundlage", "Angezeigt werden die zum aktuell gewählten und berechneten Szenario gehörenden Ergebnisdaten."),
        ],
    ),
    "system": (
        "Energiesystem",
        "Diese Ansicht zeigt den gewählten Optimierungsfokus oder vergleicht beide Energiesysteme.",
        [
            ("Optimierungsfokus", "Wählen Sie in der Seitenleiste Ökonomisch, Ökologisch oder Vergleich. Ein einzelner Fokus zeigt nur dessen berechnetes System."),
            ("Zielvergleich", "Im Vergleich stellt das Diagramm die jährlichen Kosten und CO₂-Emissionen beider Optimierungsvarianten gegenüber."),
            ("Systemvarianten", "Die Topologien zeigen die jeweils ausgelegten Anlagen. Ein Klick auf ein Systemelement öffnet dessen Ergebnisdetails und – sofern verfügbar – eine Jahresdauerlinie."),
            ("Kennzahlen", "Zeitlicher Autarkiegrad, elektrischer Bedarfsdeckungsgrad sowie Netzbezug und Netzeinspeisung ergänzen die Ansicht."),
        ],
    ),
    "sankey": (
        "Sankey",
        "Das Sankey-Fenster verdichtet die jährlichen Energieflüsse des ersten simulierten Ergebnisjahres.",
        [
            ("Flussbreite", "Breitere Verbindungen stehen für größere jährliche Energiemengen. Bei Speichern zeigt die Gesamtbreite die eingespeicherte Energie: oben die ausgespeicherte Energie, unten die Verluste. Der Verlustanteil ist im Light Mode dunkler und im Dark Mode heller eingefärbt."),
            ("Energieträger", "Farben und Netzebenen trennen elektrische, thermische und weitere Energiepfade."),
            ("Details", "Elemente und Flüsse können für zusätzliche Ergebniswerte ausgewählt werden."),
        ],
    ),
    "pfc": (
        "Powerflow Card",
        "Die Powerflow Card zeigt den zeitlichen Betrieb der berechneten Ergebnis-Topology.",
        [
            ("Momentaufnahme", "Animierte Flüsse und Leistungswerte zeigen Erzeugung, Umwandlung, Speicherung und Verbrauch im jeweiligen Zeitschritt."),
            ("Clusterwahl", "Im Steuerkopf oberhalb der Topologie kann zwischen den berechneten Repräsentativclustern gewechselt werden."),
            ("Zeitnavigation", "Der Zeitbalken folgt der Wiedergabe. Eine manuelle Auswahl springt direkt zum gewünschten Zeitpunkt und pausiert die Darstellung."),
        ],
    ),
    "certificate": (
        "Quartiersenergieausweis",
        "Diese Ansicht zeigt den vom District Generator erzeugten Quartiersenergieausweis des aktuell gewählten Szenarios.",
        [
            ("Dokument", "Der vollständige Energieausweis wird als PDF direkt im Dashboard eingebettet."),
            ("Optimierungsfokus", "Ökonomisch und ökologisch zeigen jeweils einen Energieausweis. Vergleich zeigt beide Ausweise nebeneinander."),
            ("Ergebnisordner", "Beim Öffnen der Ansicht wird gleichzeitig der zugehörige Variantenordner im Windows-Explorer geöffnet."),
        ],
    ),
}

