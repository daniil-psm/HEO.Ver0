# Berechnung und Anzeige des Gesamtfortschritts auf Grundlage der definierter Phasenfortschritte

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


_EXPLICIT_PROGRESS_PATTERN = re.compile(
    r"^\[HEO_PROGRESS\]\s*(\d{1,3})\s*\|\s*(.+?)\s*$", re.MULTILINE
)
_BUILDING_PROGRESS_PATTERN = re.compile(
    r"^building\s+(\d+)\s*/\s*(\d+)\s+calculated\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_OPTIMIZATION_START_PATTERN = re.compile(
    r"^Starting optimization for cluster\s+(\d+)\s*/\s*(\d+)\s+"
    r"for year\s+(\d+)\s*/\s*(\d+)\.\.\.\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_COMPARISON_COMMON_START_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+COMMON\s+START(?:\s+\|.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_COMPARISON_COMMON_COMPLETED_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+COMMON\s+COMPLETED(?:\s+\w+)?(?:\s+\|.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_COMPARISON_VARIANT_EVENT_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+VARIANT\s+(\d+)\s*/\s*(\d+)\s+"
    r"(economic|ecological)\s+(START|COMPLETED|FAILED)(?:\s+\|.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_COMPARISON_COMPLETED_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+COMPARISON\s+COMPLETED(?:\s+\|.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_COMPARISON_COMMON_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+Gemeinsame Quartiersvorbereitung\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_COMPARISON_VARIANT_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+Variante\s+(economic|ecological)\s+startet\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_COMPARISON_COMPLETED_PATTERN = re.compile(
    r"^\[HEO_COMPARISON\]\s+Vergleichslauf abgeschlossen\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_COMPARISON_COMMON_WORK = 50.0
_COMPARISON_VARIANT_WORK = 50.0
_COMPARISON_OBJECTIVE_LABELS = {
    "economic": "Ökonomische Optimierung",
    "ecological": "Ökologische Optimierung",
}

# Gesamtfortschritts der Berechnung
@dataclass(frozen=True)
class ProgressSnapshot:
    progress: float # Gewichteter Fortschrittsstand
    phase: str # aktuelle Phase


# Berechnungsphase
@dataclass(frozen=True)
class ProgressPhase:
    key: str # Name der Phase
    weight: float # Gewichtung der Phase im Gesamtfortschritt
    calculation: str # "discrete" oder "dynamic" für diskrete oder dynamische Fortschrittsberechnung


@dataclass(frozen=True)
class _ComparisonVariantEvent:
    start: int
    end: int
    objective: str
    index: int
    total: int
    state: str


# Definition der neun Berechnungsphasen
PHASES = (
    ProgressPhase("initialization", 12.0, "discrete"),
    ProgressPhase("demand_profiles", 30.0, "dynamic"),
    ProgressPhase("district", 5.0, "discrete"),
    ProgressPhase("clustering", 3.0, "discrete"),
    ProgressPhase("central_design", 10.0, "discrete"),
    ProgressPhase("operation", 25.0, "dynamic"),
    ProgressPhase("result_export", 5.0, "discrete"),
    ProgressPhase("kpis", 5.0, "discrete"),
    ProgressPhase("certificate", 5.0, "discrete"),
)
_PHASE_INDEX = {phase.key: index for index, phase in enumerate(PHASES)}


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


# Erzeugt alle Phasenfortschritte f_i für eine aktive Phase i, die sequenziell ausgeführt wird
# f_i = 1 für alle abgeschlossenen Phasen
# f_i = 0 für alle noch nicht begonnenen Phasen
# f_i = [0,1] für die aktive Phase
def phase_fractions(active_phase: str, fraction: float) -> dict[str, float]:
    if active_phase not in _PHASE_INDEX:
        raise ValueError(f"Unbekannte Fortschrittsphase: {active_phase}")
    active_index = _PHASE_INDEX[active_phase]
    active_fraction = max(0.0, min(1.0, float(fraction)))
    return {
        phase.key: (
            1.0
            if index < active_index
            else active_fraction
            if index == active_index
            else 0.0
        )
        for index, phase in enumerate(PHASES)
    }


# Berechnet den Gesamtfortschritt über die gewichtete Summe der Phasenfortschritte
def calculate_weighted_progress(fractions: Mapping[str, float]) -> float:
    contributions = (
        phase.weight
        * max(0.0, min(1.0, float(fractions.get(phase.key, 0.0))))
        for phase in PHASES
    )
    return _clamp(sum(contributions))


def _phase_snapshot(active_phase: str, fraction: float, text: str) -> ProgressSnapshot:
    fractions = phase_fractions(active_phase, fraction)
    return ProgressSnapshot(calculate_weighted_progress(fractions), text)


# Überführt bei diskreten Phasen den expliziten Fortschrittswert in gewichtete f_i-Werte
def _absolute_snapshot(progress: float, text: str) -> ProgressSnapshot:
    remaining = _clamp(progress)
    fractions: dict[str, float] = {}
    for phase in PHASES:
        contribution = min(phase.weight, max(0.0, remaining))
        fractions[phase.key] = contribution / phase.weight
        remaining -= contribution
    return ProgressSnapshot(calculate_weighted_progress(fractions), text)


def _valid_demand_progress(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        completed = int(value["completed"])
        total = int(value["total"])
    except (KeyError, TypeError, ValueError):
        return None
    if total <= 0 or completed < 0:
        return None
    return min(completed, total), total


# Berechnet den Phasenfortschritt der Bedarfsprofilgenerierung
# dynamische Berechnung zwischen 12 % und 42 % Gesamtfortschritt, basierend auf dem Gebäudezähler
def _demand_snapshot(
    log_text: str,
    demand_progress: dict[str, Any] | None,
) -> ProgressSnapshot | None:
    """Berechnet die gebäudeweise Profilgenerierung innerhalb von 12–42 %."""

    counter = _valid_demand_progress(demand_progress)
    matches = list(_BUILDING_PROGRESS_PATTERN.finditer(log_text))
    if matches:
        logged = (int(matches[-1].group(1)), int(matches[-1].group(2)))
        if counter is None or logged[0] / max(logged[1], 1) > counter[0] / counter[1]:
            counter = logged

    if counter is not None:
        completed, total = counter
        return _phase_snapshot(
            "demand_profiles",
            completed / total,
            f"Bedarfsprofile werden berechnet · Gebäude {completed}/{total}",
        )

    if re.search(r"^starting\s+.+$", log_text, re.IGNORECASE | re.MULTILINE):
        return _phase_snapshot("demand_profiles", 0.0, "Bedarfsprofile werden berechnet")
    return None


# Berechnet den Phasenfortschritt der Quartiersmodellierung
# diskrete Berechnung zwischen 42 % und 52 % Gesamtfortschritt
def _district_snapshot(log_text: str) -> ProgressSnapshot | None:

    milestones = (
        ("Finalizing clustering (post-optimization)", "central_design", 0.4, "Clusterprofile werden finalisiert"),
        ("solution_file_ehdo_model.txt", "central_design", 0.3, "Zentrale Anlagenauslegung ist gelöst"),
        ("Design clustering finished", "clustering", 1.0, "Auslegungscluster sind berechnet"),
        ("Preparing initial clustering", "clustering", 0.0, "Clustering wird vorbereitet"),
        ("Cluster design days", "clustering", 0.0, "Auslegungscluster werden berechnet"),
        ("Generating and optimizing heating network", "district", 0.6, "Wärmenetz wird ausgelegt"),
        ("No district geometry found", "district", 0.6, "Vereinfachtes Wärmenetz wird ausgelegt"),
        ("No central heat grid detected", "district", 0.6, "Quartiersmodell wird vorbereitet"),
        ("Finished generating demands", "demand_profiles", 1.0, "Bedarfsprofile sind vollständig"),
    )
    reached: list[tuple[ProgressSnapshot, int]] = []
    for marker, phase_key, fraction, text in milestones:
        position = log_text.rfind(marker)
        if position >= 0:
            reached.append((_phase_snapshot(phase_key, fraction, text), position))
    if not reached:
        return None
    snapshot, _position = max(
        reached,
        key=lambda item: (item[0].progress, item[1]),
    )
    return snapshot


# Berechnet den Phasenfortschritt der Betriebsoptimierung
# dynamische Berechnung zwischen 52 % und 77 % Gesamtfortschritt, basierend auf dem Cluster- und Jahrzähler
def _optimization_snapshot(log_text: str) -> ProgressSnapshot | None:
    starts = list(_OPTIMIZATION_START_PATTERN.finditer(log_text))
    if not starts:
        return None

    current = starts[-1]
    cluster_index = int(current.group(1))
    cluster_total = int(current.group(2))
    year_index = int(current.group(3))
    year_total = int(current.group(4))
    total_runs = max(cluster_total * year_total, 1)
    run_index = min((year_index - 1) * cluster_total + cluster_index, total_runs)
    current_output = log_text[current.end() :]

    if re.search(r"^Model solved to optimality\b", current_output, re.MULTILINE):
        partial = 1.0
        state = "abgeschlossen"
    elif re.search(
        r"solution_file_opti_central_model_year_.+?_cluster_.+?\.txt",
        current_output,
        re.IGNORECASE,
    ):
        partial = 0.9
        state = "Ergebnisse werden extrahiert"
    elif re.search(r"^Pyomo model built successfully\b", current_output, re.MULTILINE):
        partial = 0.2
        state = "Solver läuft"
    else:
        partial = 0.05
        state = "Pyomo-Modell wird aufgebaut"

    completed_equivalents = (run_index - 1) + partial
    return _phase_snapshot(
        "operation",
        completed_equivalents / total_runs,
        (
            f"Betriebsoptimierung {run_index}/{total_runs} · "
            f"Jahr {year_index}/{year_total} · Cluster {cluster_index}/{cluster_total} · {state}"
        ),
    )


# Leitet den Fortschritt eines einzelnen Optimierungslaufs aus DG-Artefakten ab.
def _derive_single_progress(
    log_text: str,
    status: str,
    *,
    demand_progress: dict[str, Any] | None = None,
) -> ProgressSnapshot:
    explicit_matches = list(_EXPLICIT_PROGRESS_PATTERN.finditer(log_text))
    if explicit_matches:
        furthest = max(
            explicit_matches,
            key=lambda match: (float(match.group(1)), match.start()),
        )
        snapshot = _absolute_snapshot(
            float(furthest.group(1)),
            furthest.group(2).strip(),
        )
    elif status == "running":
        snapshot = _phase_snapshot(
            "initialization",
            1.0 / 12.0,
            "District Generator wird gestartet",
        )
    else:
        snapshot = _phase_snapshot("initialization", 0.0, "Bereit")

    detected_snapshots = (
        _demand_snapshot(log_text, demand_progress),
        _district_snapshot(log_text),
        _optimization_snapshot(log_text),
    )
    for detected in detected_snapshots:
        if detected is not None and detected.progress > snapshot.progress:
            snapshot = detected

    if "KPIs saved to:" in log_text and snapshot.progress < 94.5:
        snapshot = _phase_snapshot("kpis", 0.9, "Kennzahlen sind gespeichert")
    if "Certificate saved to" in log_text and snapshot.progress < 99.5:
        snapshot = _phase_snapshot("certificate", 0.9, "Quartiersenergieausweis ist erstellt")

    if status == "completed":
        return _phase_snapshot("certificate", 1.0, "Abgeschlossen")
    if status == "stopped":
        return ProgressSnapshot(snapshot.progress, "Vom Benutzer gestoppt")
    if status == "failed":
        return ProgressSnapshot(snapshot.progress, "Fehlgeschlagen")
    return snapshot


def _comparison_variant_events(log_text: str) -> list[_ComparisonVariantEvent]:
    events = [
        _ComparisonVariantEvent(
            start=match.start(),
            end=match.end(),
            objective=match.group(3).lower(),
            index=min(
                max(1, int(match.group(1))),
                max(1, int(match.group(2))),
            ),
            total=max(1, int(match.group(2))),
            state=match.group(4).lower(),
        )
        for match in _COMPARISON_VARIANT_EVENT_PATTERN.finditer(log_text)
    ]

    # Bereits vorhandene Simulationslogs bleiben auswertbar. Die alten Marker
    # enthielten weder Index noch Abschlussereignisse; die feste Reihenfolge
    # entspricht DEFAULT_OBJECTIVES des Vergleichsdienstes.
    legacy_indices = {"economic": 1, "ecological": 2}
    events.extend(
        _ComparisonVariantEvent(
            start=match.start(),
            end=match.end(),
            objective=match.group(1).lower(),
            index=legacy_indices[match.group(1).lower()],
            total=2,
            state="start",
        )
        for match in _LEGACY_COMPARISON_VARIANT_PATTERN.finditer(log_text)
    )
    return sorted(events, key=lambda event: event.start)


def _is_comparison_log(log_text: str) -> bool:
    return bool(
        _COMPARISON_COMMON_START_PATTERN.search(log_text)
        or _LEGACY_COMPARISON_COMMON_PATTERN.search(log_text)
        or _COMPARISON_VARIANT_EVENT_PATTERN.search(log_text)
        or _LEGACY_COMPARISON_VARIANT_PATTERN.search(log_text)
    )


def _comparison_phase(event: _ComparisonVariantEvent, detail: str) -> str:
    label = _COMPARISON_OBJECTIVE_LABELS.get(event.objective, event.objective)
    position = f" ({event.index}/{event.total})" if event.total > 1 else ""
    return f"{label}{position} · {detail}"


def _comparison_progress(
    log_text: str,
    status: str,
    *,
    demand_progress: dict[str, Any] | None,
    objectives: tuple[str, ...] | None,
) -> ProgressSnapshot:
    events = _comparison_variant_events(log_text)
    variant_total = max(
        (event.total for event in events),
        default=len(objectives) if objectives else 2,
    )
    total_work = _COMPARISON_COMMON_WORK + variant_total * _COMPARISON_VARIANT_WORK

    comparison_completed = bool(
        _COMPARISON_COMPLETED_PATTERN.search(log_text)
        or _LEGACY_COMPARISON_COMPLETED_PATTERN.search(log_text)
    )
    if status == "completed":
        return ProgressSnapshot(
            100.0,
            "Optimierung abgeschlossen" if variant_total == 1
            else "Beide Optimierungen abgeschlossen",
        )
    if comparison_completed and status == "running" and variant_total == 1:
        return ProgressSnapshot(99.9, "Ergebnisse werden vorbereitet")
    if comparison_completed and status not in {"failed", "stopped"}:
        return ProgressSnapshot(100.0, "Beide Optimierungen abgeschlossen")

    if events:
        current = events[-1]
        if current.state == "start":
            # Nur Ausgaben seit dem Start der aktiven Variante auswerten. So
            # können KPIs und Zertifikat der vorherigen Variante den aktuellen
            # Clusterfortschritt nicht überlagern.
            active_log = log_text[current.end :]
            local = _derive_single_progress(active_log, "running")
            local_progress = max(
                _COMPARISON_COMMON_WORK,
                min(100.0, local.progress),
            )
            completed_work = (
                _COMPARISON_COMMON_WORK
                + (current.index - 1) * _COMPARISON_VARIANT_WORK
                + (local_progress - _COMPARISON_COMMON_WORK)
            )
            phase = _comparison_phase(current, local.phase)
        else:
            # Ein abgeschlossener oder fehlgeschlagener Versuch gibt seinen
            # Ablaufslot frei. Dadurch beginnt die nächste Variante ohne
            # Rücksprung am gleichen globalen Prozentwert.
            completed_work = (
                _COMPARISON_COMMON_WORK
                + min(current.index, variant_total) * _COMPARISON_VARIANT_WORK
            )
            detail = "abgeschlossen" if current.state == "completed" else "fehlgeschlagen"
            phase = _comparison_phase(current, detail)
        progress = _clamp(completed_work / total_work * 100.0)
    else:
        common = _derive_single_progress(
            log_text,
            "running" if status == "running" else "idle",
            demand_progress=demand_progress,
        )
        common_progress = min(_COMPARISON_COMMON_WORK, common.progress)
        common_label = (
            "Quartiersvorbereitung" if variant_total == 1
            else "Gemeinsame Quartiersvorbereitung"
        )
        if _COMPARISON_COMMON_COMPLETED_PATTERN.search(log_text):
            common_progress = _COMPARISON_COMMON_WORK
            phase = f"{common_label} abgeschlossen"
        else:
            phase = f"{common_label} · {common.phase}"
        progress = _clamp(common_progress / total_work * 100.0)
        if status == "running":
            progress = max(1.0, progress)

    if status == "running" and variant_total == 1:
        progress = min(progress, 99.9)
    if status == "stopped":
        return ProgressSnapshot(progress, f"Vom Benutzer gestoppt · {phase}")
    if status == "failed" or (events and events[-1].state == "failed"):
        # 100 % ist bei Vergleichsläufen ausschließlich einem vollständig
        # erfolgreichen Abschluss vorbehalten. Der Prozessstatus läuft dem
        # Log kurz hinterher; deshalb muss bereits der FAILED-Marker deckeln.
        failed_phase = (
            f"Fehlgeschlagen · {phase}" if status == "failed" else phase
        )
        return ProgressSnapshot(min(progress, 99.9), failed_phase)
    return ProgressSnapshot(progress, phase)


# Leitet den genauesten verfügbaren Fortschritt aus DG-Artefakten ab
def derive_progress(
    log_text: str,
    status: str,
    *,
    demand_progress: dict[str, Any] | None = None,
    objectives: tuple[str, ...] | None = None,
) -> ProgressSnapshot:
    if _is_comparison_log(log_text):
        return _comparison_progress(
            log_text,
            status,
            demand_progress=demand_progress,
            objectives=objectives,
        )
    return _derive_single_progress(
        log_text,
        status,
        demand_progress=demand_progress,
    )


# Hilfsfunktion für die Anzeige des Fortschritts in Prozent
def format_progress_percent(value: Any) -> str:
    try:
        progress = _clamp(float(value))
    except (TypeError, ValueError):
        progress = 0.0
    return str(int(progress))
