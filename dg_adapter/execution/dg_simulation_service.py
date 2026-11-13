# Schnittstelle für den Start der Optimierung, das Abfragen des Fortschritts und das Stoppen der Optimierung

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..input.config_service import APP_ROOT, DG_ROOT, _dg_python
from ..shared.scenario_names import validate_scenario_name
from .dg_progress_service import derive_progress
from ..output.results_reader import scenario_results_path
from .dg_run_service import scenario_run_path
from .dg_comparison_service import planned_objectives
from ..input.config_service import DG_SCENARIOS_DIR
from ..shared.dg_paths import seed_control_dir


@dataclass
class _RunningSimulation:
    scenario_name: str
    process: subprocess.Popen
    log_path: Path
    started_at: datetime
    objectives: tuple[str, ...] = ("economic",)
    started_tick: float | None = None
    log_entries: list[dict[str, Any]] = field(default_factory=list)
    log_entries_lock: threading.Lock = field(default_factory=threading.Lock)
    output_thread: threading.Thread | None = None
    completion_reported: bool = False
    stop_requested: bool = False
    last_progress: float = 0.0
    last_phase: str = "Bereit"


_SIMULATIONS: dict[str, _RunningSimulation] = {}
_SIMULATION_LOCK = threading.Lock()
_MAX_LOG_CHARACTERS = 120_000


# Prüft laufende DG-Kindprozesse unabhängig von Browserabfragen.
def has_running_simulations() -> bool:
    with _SIMULATION_LOCK:
        return any(item.process.poll() is None for item in _SIMULATIONS.values())


def _elapsed_since_start(simulation: _RunningSimulation) -> float:
    """Liefert eine von Uhrzeitänderungen unabhängige Laufzeit."""

    if simulation.started_tick is not None:
        return max(0.0, time.perf_counter() - simulation.started_tick)
    return max(0.0, (datetime.now() - simulation.started_at).total_seconds())


def _append_log_entry(
    simulation: _RunningSimulation,
    text: str,
    *,
    elapsed_seconds: float | None = None,
) -> None:
    entry = {
        "text": text,
        "elapsed_seconds": (
            _elapsed_since_start(simulation)
            if elapsed_seconds is None
            else max(0.0, float(elapsed_seconds))
        ),
    }
    with simulation.log_entries_lock:
        simulation.log_entries.append(entry)


def _capture_process_output(simulation: _RunningSimulation) -> None:
    """Schreibt den Klartext-Log und misst jede Ausgabezeile beim Eintreffen."""

    stream = simulation.process.stdout
    if stream is None:
        return
    try:
        with simulation.log_path.open("a", encoding="utf-8", newline="\n") as log_file:
            for line in stream:
                elapsed_seconds = _elapsed_since_start(simulation)
                log_file.write(line)
                log_file.flush()
                _append_log_entry(
                    simulation,
                    line.rstrip("\r\n"),
                    elapsed_seconds=elapsed_seconds,
                )
    finally:
        stream.close()


def _wait_for_output_capture(simulation: _RunningSimulation) -> None:
    thread = simulation.output_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)


def _dg_python_path() -> Path:
    return _dg_python()


# Startet run.py ohne die Dash-Anwendung zu blockieren
def start_scenario_simulation(
    scenario_name: Any,
    *,
    objectives: tuple[str, ...] = ("economic",),
) -> dict[str, Any]:

    name = validate_scenario_name(scenario_name)
    if not objectives or any(item not in {"economic", "ecological"} for item in objectives):
        raise ValueError("Ungültiger Optimierungsfokus.")
    run_path = scenario_run_path(name).resolve()
    if not run_path.is_file():
        raise FileNotFoundError(f"Szenario-run.py nicht gefunden: {run_path}")

    with _SIMULATION_LOCK:
        previous = _SIMULATIONS.get(name)
        if previous is not None and previous.process.poll() is None:
            return _simulation_payload(previous, status="running", fresh=False)

        objectives = planned_objectives(DG_SCENARIOS_DIR / name, objectives)

        results_path = seed_control_dir(DG_SCENARIOS_DIR / name)
        results_path.mkdir(parents=True, exist_ok=True)
        log_path = results_path / "simulation.log"
        # Der Gebäudezähler gehört immer genau zu einem Simulationslauf. Ein
        # Reststand des vorherigen Laufs darf nicht als neuer Fortschritt
        # interpretiert werden.
        try:
            (results_path / "progress.json").unlink(missing_ok=True)
        except OSError:
            pass
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUNBUFFERED"] = "1"
        environment["HEO_OPTIMIZATION_OBJECTIVES"] = ",".join(objectives)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        log_path.write_text("", encoding="utf-8")
        started_at = datetime.now()
        started_tick = time.perf_counter()
        process = subprocess.Popen(
            [str(_dg_python_path()), str(run_path)],
            cwd=str(APP_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            shell=False,
            creationflags=creation_flags,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        simulation = _RunningSimulation(
            scenario_name=name,
            process=process,
            log_path=log_path,
            started_at=started_at,
            objectives=tuple(objectives),
            started_tick=started_tick,
        )
        _append_log_entry(simulation, "Start der Optimierung", elapsed_seconds=0.0)
        simulation.output_thread = threading.Thread(
            target=_capture_process_output,
            args=(simulation,),
            name=f"heo-log-{name}",
            daemon=True,
        )
        _SIMULATIONS[name] = simulation
        simulation.output_thread.start()
        return _simulation_payload(simulation, status="running", fresh=True)


def _simulation_payload(
    simulation: _RunningSimulation,
    *,
    status: str,
    fresh: bool,
) -> dict[str, Any]:
    log_text, progress, phase = _log_snapshot(
        simulation.log_path,
        status,
        started_at=simulation.started_at,
        objectives=simulation.objectives,
    )
    if progress < simulation.last_progress:
        progress = simulation.last_progress
        if status not in {"stopped", "failed", "completed"}:
            phase = simulation.last_phase
    else:
        # Bei gleichem Prozentwert darf ein neuer Teil-Meilenstein den Text
        # aktualisieren, beispielsweise innerhalb der beiden 47-%-Schritte.
        simulation.last_progress = progress
        simulation.last_phase = phase
    with simulation.log_entries_lock:
        log_entries = [dict(entry) for entry in simulation.log_entries]
    return {
        "scenario_name": simulation.scenario_name,
        "requested_objectives": list(simulation.objectives),
        "status": status,
        "running": status == "running",
        "fresh": fresh,
        "pid": simulation.process.pid,
        "returncode": simulation.process.poll(),
        "log_path": str(simulation.log_path.resolve()),
        "log": log_text,
        "log_entries": log_entries,
        "progress": progress,
        "phase": phase,
        "elapsed_seconds": _elapsed_since_start(simulation),
        "started_at": simulation.started_at.isoformat(timespec="seconds"),
    }


def _fresh_demand_progress(
    log_path: Path,
    started_at: datetime | None,
) -> dict[str, Any] | None:
    """Liest nur den zum aktuellen Lauf gehörenden Datahandler-Zähler."""

    if started_at is None:
        return None
    progress_path = log_path.parent / "progress.json"
    try:
        # Eine kleine Toleranz berücksichtigt Dateisysteme mit grober Zeitauflösung.
        if progress_path.stat().st_mtime < started_at.timestamp() - 1.0:
            return None
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _log_snapshot(
    log_path: Path,
    status: str,
    *,
    started_at: datetime | None = None,
    objectives: tuple[str, ...] | None = None,
) -> tuple[str, float, str]:
    """Liest den Log-Tail und berechnet adapterseitig den DG-Fortschritt."""

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    snapshot = derive_progress(
        text,
        status,
        demand_progress=_fresh_demand_progress(log_path, started_at),
        objectives=objectives,
    )

    if len(text) > _MAX_LOG_CHARACTERS:
        text = "… vorherige Log-Ausgabe gekürzt …\n" + text[-_MAX_LOG_CHARACTERS:]
    return text.rstrip(), snapshot.progress, snapshot.phase


# Holt den Gesamtfortschritt
def poll_scenario_simulation(scenario_name: Any) -> dict[str, Any]:

    name = validate_scenario_name(scenario_name)
    with _SIMULATION_LOCK:
        simulation = _SIMULATIONS.get(name)
        if simulation is None:
            log_path = seed_control_dir(DG_SCENARIOS_DIR / name) / "simulation.log"
            log_text, progress, phase = _log_snapshot(log_path, "idle")
            return {
                "scenario_name": name,
                "status": "idle",
                "running": False,
                "fresh": False,
                "returncode": None,
                "log_path": str(log_path.resolve()),
                "log": log_text,
                "progress": progress,
                "phase": phase,
            }

        returncode = simulation.process.poll()
        if returncode is None:
            return _simulation_payload(simulation, status="running", fresh=False)

        _wait_for_output_capture(simulation)
        fresh = not simulation.completion_reported
        simulation.completion_reported = True
        status = (
            "stopped"
            if simulation.stop_requested
            else "completed"
            if returncode == 0
            else "failed"
        )
        return _simulation_payload(simulation, status=status, fresh=fresh)


# Stop-Funktion der Optimierung durch den User
def stop_scenario_simulation(scenario_name: Any) -> dict[str, Any]:

    name = validate_scenario_name(scenario_name)
    with _SIMULATION_LOCK:
        simulation = _SIMULATIONS.get(name)
        if simulation is None:
            log_path = seed_control_dir(DG_SCENARIOS_DIR / name) / "simulation.log"
            log_text, progress, phase = _log_snapshot(log_path, "idle")
            return {
                "scenario_name": name,
                "status": "idle",
                "running": False,
                "fresh": False,
                "returncode": None,
                "log_path": str(log_path.resolve()),
                "log": log_text,
                "progress": progress,
                "phase": phase,
            }

        if simulation.process.poll() is None:
            simulation.stop_requested = True
            simulation.process.terminate()
            try:
                simulation.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                simulation.process.kill()
                simulation.process.wait(timeout=5)
            _wait_for_output_capture(simulation)
            stop_message = "Simulation durch HEO gestoppt."
            try:
                with simulation.log_path.open("a", encoding="utf-8", newline="\n") as log_file:
                    log_file.write(f"\n{stop_message}\n")
            except OSError:
                pass
            _append_log_entry(simulation, stop_message)

        simulation.completion_reported = True
        return _simulation_payload(simulation, status="stopped", fresh=True)
