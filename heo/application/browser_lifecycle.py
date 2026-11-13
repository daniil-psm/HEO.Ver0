"""Verwaltet Browser-Lebenszeichen und die automatische Beendigung des lokalen Servers."""
from __future__ import annotations

import logging
import secrets
import threading
import time

from flask import abort, jsonify, request


# Ein Lebenszeichen irgendeines Tabs hält die gemeinsame Instanz am Leben.
class BrowserLifecycle:
    """Verwaltet Lebenszeichen, aktive Requests und die Abschaltfrist einer HEO-Instanz."""

    def __init__(self, project, busy, *, timeout=30, startup_grace=120, clock=time.monotonic):
        """Initialisiert Projektkennung, Zeitlimits und den Aufruf zur Prüfung laufender Arbeiten."""

        self.project = str(project.resolve())
        self.busy = busy
        self.timeout = timeout
        self.clock = clock
        self.deadline = clock() + startup_grace
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.active_requests = 0
        self.closing = False

    # Die Fristverlängerung muss atomar gegenüber der Abschaltentscheidung bleiben.
    def touch(self):
        """Verlängert die Frist; liefert False, wenn die Abschaltung bereits begonnen hat."""

        with self.lock:
            if self.closing:
                return False
            self.deadline = self.clock() + self.timeout
            return True

    # Offene Requests und laufende Optimierungen schützen auch ohne Browser.
    def should_stop(self):
        """Entscheidet unter Berücksichtigung aktiver Arbeiten, ob der Server enden soll."""

        with self.lock:
            if self.closing:
                return True
            try:
                busy = self.active_requests or self.busy()
            except Exception:
                logging.exception("HEO: Hintergrundstatus unklar; automatische Abschaltung ausgesetzt.")
                busy = True
            if busy:
                self.deadline = self.clock() + self.timeout
                return False
            if self.clock() >= self.deadline:
                self.closing = True
                return True
            return False

    def install(self, app):
        """Registriert Request-Zähler sowie Status- und Lebenszeichen-Endpunkte an Flask."""

        @app.before_request
        def enter_request():
            """Zählt den Request und lehnt neue Requests während der Abschaltung mit HTTP 503 ab."""

            with self.lock:
                if self.closing:
                    abort(503)
                self.active_requests += 1
            if request.path == "/":
                self.touch()

        @app.teardown_request
        def leave_request(error):
            """Verringert den Zähler nach Abschluss eines Requests."""

            with self.lock:
                self.active_requests = max(0, self.active_requests - 1)

        @app.get("/_heo/status")
        def status():
            """Liefert Projekt, Instanzkennung und Protokollversion ohne HTTP-Caching."""

            response = jsonify(project=self.project, instance=self.token, protocol=1)
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.post("/_heo/heartbeat")
        def heartbeat():
            """Prüft Herkunft und Instanzkennung und bestätigt ein angenommenes Lebenszeichen mit HTTP 204."""

            if request.headers.get("Origin", request.host_url.rstrip("/")) != request.host_url.rstrip("/"):
                abort(403)
            if not secrets.compare_digest(request.headers.get("X-HEO-Instance", ""), self.token):
                abort(403)
            if not self.touch():
                abort(503)
            return "", 204
