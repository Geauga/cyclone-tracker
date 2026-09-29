# server.py
# User request: local browser dashboard, five-minute refresh only during active sessions.
import io
import logging
import math
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, request, send_file

from .archive import Archive
from .exports import export_csv, export_geojson, export_netcdf
from .provider import COVERAGE, OfficialProvider, dt, utcnow

LOG = logging.getLogger(__name__)


class Monitor:
    def __init__(self, archive, provider=None, interval=300, clock=time.monotonic):
        self.archive = archive
        self.provider = provider or OfficialProvider()
        self.interval = interval
        self.clock = clock
        self.sessions = {}
        self.lock = threading.RLock()
        self.busy = False
        self.last_attempt = None
        self.errors = []
        self.status = archive.state("last_refresh") or {}
        self.stop = threading.Event()

    def heartbeat(self, session):
        with self.lock:
            self.sessions[session] = self.clock()

    def close_session(self, session):
        with self.lock:
            self.sessions.pop(session, None)

    def active(self):
        with self.lock:
            now = self.clock()
            self.sessions = {k: v for k, v in self.sessions.items() if now - v < 45}
            return bool(self.sessions)

    def due(self):
        return self.active() and not self.busy and (
            self.last_attempt is None or self.clock() - self.last_attempt >= self.interval)

    def refresh(self, manual=False):
        with self.lock:
            if not self.active() or self.busy:
                return False
            if self.last_attempt is not None and self.clock() - self.last_attempt < (30 if manual else self.interval):
                return False
            self.busy = True
            self.last_attempt = self.clock()
        threading.Thread(target=self._refresh, daemon=True, name="official-data-refresh").start()
        return True

    def _refresh(self):
        try:
            result = self.provider.collect()
            errors = list(result["errors"])
            for product, sources in result["products"]:
                try:
                    version = self.archive.save(product, sources)
                    LOG.info("Archived %s %s as %s", product["name"], product["analysis_time"], version)
                except Exception as exc:
                    LOG.exception("Archive write failed for %s", product["key"])
                    errors.append(product["key"] + ": archive write failed: " + str(exc))
            state = {k: v for k, v in result.items() if k not in ("products", "errors")}
            state["errors"] = errors
            self.archive.state("last_refresh", state)
            with self.lock:
                self.status = state
                self.errors = errors
        except Exception as exc:
            LOG.exception("Refresh failed; retaining archive and last known index")
            with self.lock:
                self.errors = ["Refresh failed: " + str(exc)]
        finally:
            with self.lock:
                self.busy = False

    def run(self):
        while not self.stop.wait(1):
            if self.due():
                self.refresh()

    def snapshot(self):
        with self.lock:
            result = dict(self.status)
            result.update(busy=self.busy, interval=self.interval,
                          errors=list(self.errors or self.status.get("errors", [])),
                          coverage=COVERAGE, active_sessions=len(self.sessions), server_time=utcnow())
        expected = result.get("expected_keys")
        rows = self.archive.latest()
        for row in rows:
            row["in_latest_index"] = None if expected is None else row["key"] in expected
            row["age_hours"] = (dt(result["server_time"]) - dt(row["analysis_time"])).total_seconds() / 3600
        result["storms"] = rows
        result["missing_keys"] = [] if expected is None else [k for k in expected if k not in {r["key"] for r in rows}]
        result["next_refresh_seconds"] = None if self.last_attempt is None else max(0, round(self.interval - (self.clock() - self.last_attempt)))
        return result


def create_app(data_dir, provider=None, interval=300, start_worker=True):
    static = Path(__file__).with_name("static")
    app = Flask(__name__, static_folder=str(static))
    app.config.update(MAX_CONTENT_LENGTH=8192)
    monitor = Monitor(Archive(Path(data_dir) / "advisories.sqlite3"), provider, interval)
    app.extensions["monitor"] = monitor
    if start_worker:
        threading.Thread(target=monitor.run, daemon=True, name="session-polling").start()

    @app.before_request
    def local_requests():
        host = request.host.split(":")[0]
        if host not in ("localhost", "127.0.0.1"):
            abort(403)
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                abort(403)
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                abort(403)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return send_file(static / "index.html")

    @app.get("/api/state")
    def state():
        return jsonify(monitor.snapshot())

    def session_id():
        session = str(request.args.get("session", ""))
        if not 8 <= len(session) <= 80 or not all(c.isalnum() or c == "-" for c in session):
            abort(400, "Invalid dashboard session")
        return session

    @app.post("/api/session")
    def heartbeat():
        monitor.heartbeat(session_id())
        monitor.refresh()
        return jsonify(ok=True)

    @app.post("/api/close")
    def close():
        monitor.close_session(session_id())
        return jsonify(ok=True)

    @app.post("/api/refresh")
    def refresh():
        monitor.heartbeat(session_id())
        return jsonify(started=monitor.refresh(manual=True))

    @app.post("/api/settings")
    def settings():
        value = (request.get_json(silent=True) or {}).get("interval")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 60 <= value <= 86400:
            abort(400, "Interval must be between 60 and 86400 seconds")
        with monitor.lock:
            monitor.interval = int(value)
        return jsonify(interval=monitor.interval)

    @app.get("/api/archive/<key>")
    def versions(key):
        return jsonify(monitor.archive.versions(key))

    @app.get("/api/advisory/<version>")
    def advisory(version):
        try:
            return jsonify(monitor.archive.get(version))
        except KeyError:
            abort(404)

    @app.get("/api/export/<version>/<format>")
    def export(version, format):
        try:
            p = monitor.archive.get(version)
        except KeyError:
            abort(404)
        if format == "csv":
            payload, mime, ext = export_csv(p), "text/csv", "csv"
        elif format == "geojson":
            payload, mime, ext = export_geojson(p), "application/geo+json", "geojson"
        elif format == "nc":
            payload, mime, ext = export_netcdf(p), "application/x-netcdf", "nc"
        elif format == "raw":
            payload, mime, ext = monitor.archive.raw(version), "application/zip", "zip"
        else:
            abort(404)
        return send_file(io.BytesIO(payload), mimetype=mime, as_attachment=True,
                         download_name=p["key"] + "-" + version + "." + ext)

    return app

# Purpose: loopback dashboard API and session-scoped collector. Upstream: Archive and OfficialProvider.
# Upstream purpose: retrieve and persist official advisories. Environment: Python 3.11+, local server.
# Generated: 2026-09-28 America/New_York. New file; closed/crashed sessions expire within 45 seconds.
# Change record: new implementation, lines 1-216; finalized 2026-09-29 America/New_York.
