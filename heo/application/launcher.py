"""Richtet eine eigene HEO-Umgebung ein und startet die App unter Windows/Linux."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import venv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = Path("heo") / "application"
LAUNCHER_MODULE = "heo.application.launcher"
PYTHON_VERSION = (3, 12)
SETUP_VERSION = 1


class SetupError(RuntimeError):
    """Eine fehlgeschlagene Einrichtung darf die App nicht starten."""


def requirements_path(root: Path) -> Path:
    """Liefert den Pfad zur Paketliste innerhalb des übergebenen Projektordners."""

    return root / APPLICATION_DIR / "requirements.txt"


def environment_dir(root: Path) -> Path:
    """Liefert den plattformspezifischen Ordner der verwalteten HEO-Python-Umgebung."""

    return root / (".venv-windows" if sys.platform == "win32" else ".venv-linux")


def environment_python(directory: Path) -> Path:
    """Liefert den plattformspezifischen Interpreterpfad einer Python-Umgebung."""

    return directory / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def child_environment(python: Path) -> dict[str, str]:
    """Erstellt Prozessvariablen für den angegebenen HEO-Interpreter ohne fremde Python-Pfade."""

    environment = os.environ.copy()
    # Keine fremde Python-Umgebung in die neue Umgebung hineinreichen.
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment.update(
        VIRTUAL_ENV=str(python.parent.parent),
        PATH=str(python.parent) + os.pathsep + environment.get("PATH", ""),
        PYTHONNOUSERSITE="1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        HEO_DG_PYTHON=str(python),
    )
    return environment


def _read_json(path: Path) -> dict:
    """Liest ein JSON-Objekt; fehlende, ungültige oder anders strukturierte Daten ergeben ein leeres Dict."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, value: dict) -> None:
    """Speichert ein JSON-Objekt über eine temporäre Datei am angegebenen Pfad."""

    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _owner(root: Path) -> dict:
    """Liefert die Kennung der verwalteten Umgebung aus Projekt, Plattform und Python-Version."""

    return {"project": str(root), "platform": sys.platform, "python": list(PYTHON_VERSION)}


def _requirements_state(root: Path) -> dict:
    """Liefert Einrichtungsversion und Prüfsumme der aktuellen Paketliste."""

    return {
        "setup_version": SETUP_VERSION,
        "requirements_sha256": hashlib.sha256(requirements_path(root).read_bytes()).hexdigest(),
    }


# Gleichzeitige Starts dürfen nicht dieselbe Umgebung installieren.
@contextmanager
def _setup_lock(root: Path, *, wait: bool = False):
    """Hält die Einrichtungssperre; ein erfolgloser Sperrversuch löst SetupError aus."""
    name = "windows" if sys.platform == "win32" else "linux"
    lock_dir = root / ".heo-runtime" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"setup-{name}.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except OSError as exc:
            raise SetupError("Ein anderer HEO-Start richtet die Umgebung bereits ein. Bitte danach erneut starten.") from exc
        try:
            yield
        finally:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_python(python: Path, directory: Path) -> None:
    """Prüft Interpreter, Python-Version, 64-Bit-Architektur und Umgebungsordner; meldet SetupError."""

    if not python.is_file():
        raise SetupError(f"Die HEO-Umgebung ist noch nicht eingerichtet: {directory}")
    probe = subprocess.run(
        [str(python), "-I", "-c",
         "import json, struct, sys; print(json.dumps([list(sys.version_info[:2]), sys.prefix, struct.calcsize('P') * 8]))"],
        env=child_environment(python), capture_output=True, text=True, check=True,
    )
    version, prefix, bits = json.loads(probe.stdout)
    if version != list(PYTHON_VERSION) or bits != 64 or Path(prefix).resolve() != directory.resolve():
        raise SetupError(f"Die Umgebung {directory.name} passt nicht zu Python 3.12 (64 Bit). Bitte den Ordner umbenennen und erneut starten.")


def prepare_environment(root: Path, *, check_only: bool = False) -> Path:
    """Prüft oder erstellt die verwaltete Python-Umgebung und liefert ihren Interpreterpfad."""

    directory = environment_dir(root)
    python = environment_python(directory)
    owner_path = directory / ".heo-managed.json"
    ready_path = directory / ".heo-ready.json"
    expected = _requirements_state(root)

    # Besitzkennung und Ordner prüfen, bevor die verwaltete Umgebung verändert wird.
    if directory.is_symlink():
        raise SetupError(f"{directory.name} ist eine Verknuepfung. Bitte fuer HEO einen eigenen Umgebungsordner verwenden.")
    if directory.exists() and _read_json(owner_path) != _owner(root):
        raise SetupError(
            f"{directory.name} stammt nicht von diesem Starter oder wurde verschoben. "
            "Der Ordner bleibt unveraendert. Bitte umbenennen und erneut starten."
        )
    if check_only:
        _validate_python(python, directory)
        if _read_json(ready_path) != expected:
            raise SetupError("Die Paketliste wurde noch nicht vollstaendig installiert. Bitte normal starten.")
        return python

    # Eine unvollständige eigene Umgebung kann beim nächsten Start weiter eingerichtet werden.
    if not directory.exists():
        directory.mkdir()
        _write_json(owner_path, _owner(root))
    if not python.is_file() or not (directory / "pyvenv.cfg").is_file():
        print(f"HEO: Erstelle {directory.name} mit Python 3.12 ...", flush=True)
        try:
            venv.EnvBuilder(with_pip=True).create(directory)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SetupError(
                "Die Umgebung konnte nicht erstellt werden. Unter Linux muss das Paket python3.12-venv verfuegbar sein. "
                f"Ein erneuter Start versucht die Einrichtung wieder. Details: {exc}"
            ) from exc
    # Die Paketinstallation gilt erst nach Interpreterprüfung und erfolgreichem pip check als bereit.
    _validate_python(python, directory)
    if _read_json(ready_path) != expected:
        print("HEO: Installiere die benoetigten Pakete. Beim ersten Start kann dies einige Minuten dauern ...", flush=True)
        environment = child_environment(python)
        # Repariert auch einen zuvor unterbrochenen ersten Einrichtungsversuch.
        subprocess.run([str(python), "-I", "-m", "ensurepip", "--upgrade"], cwd=root, env=environment, check=True)
        subprocess.run(
            [str(python), "-I", "-m", "pip", "install", "-r", str(requirements_path(root))],
            cwd=root, env=environment, check=True,
        )
        subprocess.run([str(python), "-I", "-m", "pip", "check"], cwd=root, env=environment, check=True)
        _write_json(ready_path, expected)
    return python


def run_browser_app(*, open_existing: bool = False) -> None:
    """Öffnet die eigene Instanz erneut oder startet einen verwalteten Server."""
    from heo.application.server_runtime import run

    # Die Wiederaufnahme einer vorhandenen Instanz benötigt keine Dash-Importe.
    def app_factory():
        """Importiert und liefert die Dash-App für eine neu zu startende Instanz."""

        from heo.application.heo_dash import app
        return app

    def busy():
        """Prüft, ob noch Simulationen des DG-Adapters laufen."""

        from dg_adapter.execution.dg_simulation_service import has_running_simulations
        return has_running_simulations()

    run(PROJECT_ROOT, app_factory, busy)


def main(argv: list[str] | None = None) -> int:
    """Verarbeitet Startoptionen, richtet HEO ein und liefert den Prozess-Exitcode."""

    parser = argparse.ArgumentParser(description="HEO einrichten und im Browser starten.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--setup-only", action="store_true", help="Nur die Umgebung einrichten; App nicht starten.")
    mode.add_argument("--check", action="store_true", help="Einrichtung ohne Installation oder App-Start pruefen.")
    mode.add_argument("--run-app", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--open-existing", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if sys.platform not in {"linux", "win32"}:
            raise SetupError("Dieser Starter unterstuetzt Windows und Linux.")
        if sys.version_info[:2] != PYTHON_VERSION or struct.calcsize("P") != 8:
            raise SetupError("Bitte Python 3.12 (64 Bit) installieren und den HEO-Starter erneut ausfuehren.")
        for name in (APPLICATION_DIR / "heo_dash.py", APPLICATION_DIR / "requirements.txt"):
            if not (PROJECT_ROOT / name).is_file():
                raise SetupError(f"{name} fehlt im Projektordner. Bitte den vollstaendigen Projektordner uebertragen.")
        if args.run_app:
            run_browser_app(open_existing=args.open_existing)
            return 0
        if args.check:
            python = prepare_environment(PROJECT_ROOT, check_only=True)
        else:
            with _setup_lock(PROJECT_ROOT, wait=True):
                python = prepare_environment(PROJECT_ROOT)
        if args.setup_only or args.check:
            print(f"HEO: Umgebung bereit ({python}).", flush=True)
            return 0
        print("HEO: Öffne die Anwendung. Nach Schließen aller Tabs endet der Server automatisch.", flush=True)
        command = [str(python), "-m", LAUNCHER_MODULE, "--run-app"]
        if args.open_existing:
            command.append("--open-existing")
        return subprocess.call(command, cwd=PROJECT_ROOT, env=child_environment(python))
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"HEO konnte nicht gestartet werden: {exc}", file=sys.stderr)
        print("Bei einem Installationsfehler die Meldung oben pruefen und den Starter erneut ausfuehren. Bestehende Entwicklungsumgebungen bleiben erhalten.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
