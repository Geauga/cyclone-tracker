# __main__.py
# User request: launch the local dashboard with visible diagnostics.
import argparse
import logging
import os
from pathlib import Path

from waitress import serve

from .server import create_app


def main():
    parser = argparse.ArgumentParser(description="Local official tropical cyclone monitor")
    default = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "CycloneMonitor"
    parser.add_argument("--data-dir", type=Path, default=default)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=int, default=300, help="Polling seconds while a browser session is open")
    args = parser.parse_args()
    if not 60 <= args.interval <= 86400 or not 1 <= args.port <= 65535:
        parser.error("Use interval 60–86400 seconds and port 1–65535")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(args.data_dir / "monitor.log", encoding="utf-8")])
    app = create_app(args.data_dir, interval=args.interval)
    logging.info("Dashboard: http://127.0.0.1:%s | Archive: %s", args.port, args.data_dir.resolve())
    logging.info("No polling until a dashboard session opens. Ctrl+C stops the server.")
    try:
        serve(app, host="127.0.0.1", port=args.port, threads=6)
    finally:
        app.extensions["monitor"].stop.set()


if __name__ == "__main__":
    main()
# Purpose: local launch and logging. Upstream: server.py creates the web API and polling worker.
# Environment: Python 3.11+, Windows/Linux/macOS. Generated: 2026-09-28 America/New_York.
# Change record: new implementation, lines 1-37; finalized 2026-09-29 America/New_York.
