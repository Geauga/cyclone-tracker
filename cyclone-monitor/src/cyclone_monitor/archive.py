# archive.py
# User request: persistent, deduplicated local advisories, corrections, and original sources.
import hashlib
import io
import json
import sqlite3
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .provider import utcnow


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS advisories(
                    id TEXT PRIMARY KEY, storm_key TEXT NOT NULL, analysis_time TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL, last_seen TEXT NOT NULL, document TEXT NOT NULL,
                    raw_zip BLOB NOT NULL);
                CREATE INDEX IF NOT EXISTS storm_time ON advisories(storm_key, analysis_time);
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, product, sources):
        # Retrieval time and unrelated index updates must not generate duplicate versions.
        canonical = json.dumps(product, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        main_raw = json.dumps(json.loads(sources["wmo-advisory.json"]), sort_keys=True, separators=(",", ":"))
        version = hashlib.sha256((canonical + main_raw).encode()).hexdigest()[:24]
        now = utcnow()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for name, payload in sources.items():
                z.writestr(name, payload)
            z.writestr("normalized.json", canonical)
            z.writestr("retrieval.json", json.dumps({"retrieved_at": now, "source_url": product["source_url"]}))
        with self.connect() as db:
            db.execute("INSERT INTO advisories VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen",
                       (version, product["key"], product["analysis_time"], now, now, canonical, buffer.getvalue()))
        return version

    def get(self, version):
        with self.connect() as db:
            row = db.execute("SELECT document,retrieved_at,last_seen FROM advisories WHERE id=?", (version,)).fetchone()
        if row is None:
            raise KeyError(version)
        p = json.loads(row[0])
        p.update(version=version, retrieved_at=row[1], last_seen=row[2])
        return p

    def versions(self, key=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM advisories " + ("WHERE storm_key=? " if key else "") +
                "ORDER BY analysis_time DESC,retrieved_at DESC,rowid DESC", (key,) if key else ()
            ).fetchall()
        result = []
        for (version,) in rows:
            p = self.get(version)
            last = [v for v in p["points"] if v["kind"] == "observed"][-1]
            result.append({k: p[k] for k in ("version", "key", "name", "storm_id", "issuer",
                                            "analysis_time", "issue_time", "retrieved_at", "last_seen")} |
                          {"latest": last, "overlay_status": p["overlay_status"], "group_id": p["group_id"]})
        return result

    def latest(self):
        with self.connect() as db:
            rows = db.execute("""
                SELECT a.id FROM advisories a WHERE a.rowid = (
                    SELECT b.rowid FROM advisories b WHERE b.storm_key=a.storm_key
                    ORDER BY b.analysis_time DESC,b.retrieved_at DESC,b.rowid DESC LIMIT 1)
                ORDER BY a.analysis_time DESC,a.retrieved_at DESC
            """).fetchall()
        result = []
        for (version,) in rows:
            p = self.get(version)
            last = [v for v in p["points"] if v["kind"] == "observed"][-1]
            result.append({k: p[k] for k in ("version", "key", "name", "storm_id", "issuer",
                                            "analysis_time", "issue_time", "retrieved_at", "last_seen")} |
                          {"latest": last, "overlay_status": p["overlay_status"], "group_id": p["group_id"]})
        return result

    def raw(self, version):
        with self.connect() as db:
            row = db.execute("SELECT raw_zip FROM advisories WHERE id=?", (version,)).fetchone()
        if row is None:
            raise KeyError(version)
        return row[0]

    def state(self, key, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute("INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (key, json.dumps(value)))
                return value
            row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

# Purpose: atomic SQLite archive and exact-source ZIPs. Upstream: OfficialProvider normalized products.
# Upstream purpose: retrieve official data. Environment: Python 3.11+, local writable disk.
# Generated: 2026-09-28 America/New_York. New file; no automatic deletion.
# Change record: new implementation, lines 1-114; finalized 2026-09-29 America/New_York.
