"""Startet genau eine lokale HEO-Instanz und verwaltet deren belegten Port."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import select
import signal
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


@contextmanager
def startup_lock(directory):
    """Hält eine exklusive projektbezogene Sperre während der Instanzverwaltung."""

    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "server.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def request_local(url, *, token=None):
    """Sendet eine lokale Statusabfrage oder mit Token ein Lebenszeichen ohne System-Proxy."""

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, method="POST" if token else "GET")
    if token:
        req.add_header("X-HEO-Instance", token)
    with opener.open(req, timeout=2) as response:
        return json.loads(response.read()) if not token else None


def wait_until_ready(url, instance, timeout=30):
    """Wartet bis zum Timeout auf die erwartete Instanz; löst danach RuntimeError aus."""

    deadline = time.monotonic() + timeout
    while True:
        try:
            if request_local(url + "_heo/status").get("instance") == instance:
                return
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("HEO wurde gestartet, antwortet aber noch nicht. Bitte erneut versuchen.")
        time.sleep(.1)


# Ein belegter Port allein identifiziert keine eigene HEO-Instanz.
def port_in_use(port):
    """Prüft, ob ein TCP-Port auf der lokalen Loopback-Adresse Verbindungen annimmt."""

    with socket.socket() as connection:
        connection.settimeout(.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


# Die Linux-Startkennung verhindert die Verwechslung mit einer inzwischen fremden PID.
def process_identity(pid):
    """Liest Linux-Startkennung, Boot-ID und Arbeitsordner eines Prozesses."""

    stat = Path(f"/proc/{pid}/stat").read_text()
    return {
        "start": stat.rsplit(")", 1)[1].split()[19],
        "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "cwd": str(Path(f"/proc/{pid}/cwd").resolve(strict=True)),
    }


# Relative Skriptpfade gelten nur zusammen mit dem separat geprüften Projekt-CWD.
def is_heo_command(command, root):
    """Erkennt den HEO-Modulstarter oder einen direkten App.py-Aufruf im angegebenen Projekt."""

    args = [os.fsdecode(part) for part in command if part]
    if len(args) >= 4 and args[1:3] == ["-m", "heo.application.launcher"]:
        return "--run-app" in args[3:]
    if len(args) != 2:
        return False
    script = Path(args[1])
    if not script.is_absolute():
        script = root / script
    return script.resolve() == (root / "App.py").resolve()


# Port-Socket, Benutzer, Arbeitsordner und Launcher müssen gemeinsam zur eigenen Instanz passen.
def find_legacy_owner(root, port):
    """Sucht unter Linux eine zum Projekt und Port gehörende ältere HEO-Instanz."""

    if sys.platform != "linux":
        return {}
    try:
        listeners = {
            row.split()[9]
            for row in Path("/proc/net/tcp").read_text().splitlines()[1:]
            if row.split()[1] == f"0100007F:{port:04X}" and row.split()[3] == "0A"
        }
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if proc.stat().st_uid != os.getuid():
                    continue
                command = (proc / "cmdline").read_bytes().split(b"\0")
                if not is_heo_command(command, root):
                    continue
                identity = process_identity(int(proc.name))
                if identity["cwd"] != str(root.resolve()):
                    continue
                if any(os.readlink(fd) in {f"socket:[{inode}]" for inode in listeners}
                       for fd in (proc / "fd").iterdir()):
                    return {"pid": int(proc.name), "project": str(root.resolve()), "identity": identity}
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return {}


def recover_owned_process(record, root):
    """Beendet eine verifizierte Linux-HEO-Instanz ohne Kindprozesse; meldet den Erfolg als Bool."""

    if sys.platform != "linux" or not hasattr(os, "pidfd_open"):
        return False
    try:
        pid = int(record["pid"])
        if pid <= 1 or record["project"] != str(root.resolve()):
            return False
        fd = os.pidfd_open(pid)
        try:
            if Path(f"/proc/{pid}").stat().st_uid != os.getuid():
                return False
            if process_identity(pid) != record["identity"]:
                return False
            if record["identity"]["cwd"] != str(root.resolve()):
                return False
            command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            if not is_heo_command(command, root):
                return False
            # Laufende Solver und andere Hintergrundarbeiten dürfen nicht verwaisen.
            def has_children():
                """Prüft, ob einer der Threads des Prozesses noch Kindprozesse besitzt."""

                return any(
                    path.read_text().strip()
                    for path in Path(f"/proc/{pid}/task").glob("*/children")
                )
            if has_children():
                return False
            signal.pidfd_send_signal(fd, signal.SIGTERM)
            if not select.select([fd], [], [], 5)[0]:
                if has_children():
                    return False
                signal.pidfd_send_signal(fd, signal.SIGKILL)
                if not select.select([fd], [], [], 5)[0]:
                    return False
            return True
        finally:
            os.close(fd)
    except (OSError, ValueError, KeyError):
        return False


def run(root, app_factory, busy, *, port=8050):
    """Öffnet eine vorhandene eigene Instanz oder betreibt einen lokalen Server bis zur Abschaltung."""

    from werkzeug.serving import make_server
    from .browser_lifecycle import BrowserLifecycle

    root = root.resolve()
    directory = root / ".heo-runtime"
    record_path = directory / "server.json"
    url = f"http://127.0.0.1:{port}/"
    server = None
    stopped = threading.Event()
    with startup_lock(directory):
        if port_in_use(port):
            try:
                status = request_local(url + "_heo/status")
                if status.get("project") != str(root) or status.get("protocol") != 1:
                    raise RuntimeError("Port 8050 wird von einer anderen Anwendung verwendet.")
                request_local(url + "_heo/heartbeat", token=status["instance"])
            except (OSError, ValueError, KeyError):
                # Eine gerade regulär schließende Instanz erhält zuerst Zeit zum Freigeben.
                for _ in range(10):
                    if not port_in_use(port):
                        break
                    time.sleep(.1)
                if port_in_use(port):
                    try:
                        record = json.loads(record_path.read_text())
                    except (OSError, ValueError):
                        record = {}
                    if not record:
                        record = find_legacy_owner(root, port)
                    if not recover_owned_process(record, root):
                        raise RuntimeError(
                            "Der HEO-Port ist belegt. Die Instanz kann nicht sicher ersetzt werden "
                            "(andere Anwendung oder laufende Hintergrundarbeit). Bitte später erneut öffnen."
                        )
            else:
                if not webbrowser.open(url):
                    raise RuntimeError(f"Der Browser konnte nicht geöffnet werden: {url}")
                return
        app = app_factory()
        lifecycle = BrowserLifecycle(root, busy)
        lifecycle.install(app.server)
        # make_server meldet Bindungsfehler teilweise mit SystemExit.
        try:
            server = make_server("127.0.0.1", port, app.server, threaded=True)
        except SystemExit as exc:
            raise RuntimeError(f"Der lokale Port {port} konnte nicht geöffnet werden.") from exc
        record = {"pid": os.getpid(), "project": str(root), "instance": lifecycle.token}
        if sys.platform == "linux":
            record["identity"] = process_identity(os.getpid())
        record_path.write_text(json.dumps(record))
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        # Prüft echte HTTP-Bereitschaft statt einen festen Browser-Timer zu verwenden.
        try:
            wait_until_ready(url, lifecycle.token)
            if not webbrowser.open(url):
                raise RuntimeError(f"Der Browser konnte nicht geöffnet werden: {url}")
        except Exception:
            server.shutdown()
            server.server_close()
            record_path.unlink(missing_ok=True)
            raise

    # Die Start-Sperre bleibt während des Betriebs frei für weitere Doppelklicks.
    try:
        while serving.is_alive() and not stopped.wait(1):
            if lifecycle.should_stop():
                break
    finally:
        server.shutdown()
        serving.join(timeout=5)
        server.server_close()
        with startup_lock(directory):
            try:
                current = json.loads(record_path.read_text())
                if current.get("instance") == lifecycle.token:
                    record_path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
