# Cyclone Monitor

An installable Python package and local browser dashboard for official tropical cyclone advisories. Distribution name: **cyclone-monitor-local**; Python import: **cyclone_monitor**.

## Run on this computer

The project virtual environment is installed. From this directory, run **.\start.ps1**, then open [the local dashboard](http://127.0.0.1:8765). Keep the terminal running. Press Ctrl+C to stop the server.

If PowerShell policy prevents running the script, invoke **.\.venv\Scripts\python.exe -m cyclone_monitor --data-dir data** from this directory. No execution-policy change is necessary.

The dashboard checks every five minutes while open and has a manual Refresh button. Change the interval in the dashboard or pass **-Interval 900** to start.ps1. Repeated manual requests are limited to one per 30 seconds. Multiple tabs share one collector. Closed sessions stop polling; a crashed or suspended tab expires after 45 seconds. An already-started request may finish and be archived.

## Install elsewhere

Python 3.11 or newer is required. Create a virtual environment with **python -m venv .venv**, then install this directory with **.\.venv\Scripts\python.exe -m pip install .** on Windows. On macOS/Linux, use **.venv/bin/python -m pip install .**.

Alternatively, install the wheel from dist/ using **python -m pip install path-to-wheel.whl**. Launch the installed command **cyclone-monitor --data-dir path-to-local-data**. It binds only to 127.0.0.1, port 8765. Use **--port** to choose another port.

The CLI default data directory is %LOCALAPPDATA%\CycloneMonitor on Windows or ~/.local/share/CycloneMonitor elsewhere. The supplied Windows launcher explicitly uses this project's data/ directory.

## Dashboard

1: Search the storm directory and choose a storm to inspect observed and forecast tracks, wind, pressure, source attribution, and timestamps.

2: Toggle official uncertainty cones and wind extents. Select a wind valid time to avoid mixing multiple forecast times. Unavailable and zero-radius products are distinguished.

3: Select an archived advisory or press Replay. Compare with another version to show its forecast in purple. Comparisons use the selected storm's issuing centre; no wind-averaging conversion is inferred.

4: Download CSV, GeoJSON, NetCDF, or a ZIP of original downloaded products for the selected version. A source correction or newly available overlay can produce a new snapshot even when the issue time is unchanged.

5: Expand Sources & coverage for the feed timestamp and integration limits. Successful retrieval does not mean an agency has issued a new advisory. Records older than 12 hours are highlighted as an explicit display threshold.

The bundled Natural Earth basemap, map controls, archived advisories, and exports work without an external tile service. New advisories require internet access. The low-resolution basemap provides regional/global context.

## Data and scientific meaning

CSV contains one row per observed or forecast track point, with units in column names and attribution/time fields. Text that could become a spreadsheet formula is escaped. Missing numbers remain empty; zero remains zero.

GeoJSON contains point records, observed/forecast lines, and available official polygon overlays. Geometry crossing the date line is split. Official all-zero wind radii are retained as a feature with null geometry and a no_extent property.

NetCDF contains a record dimension, numeric positions/intensity, UTC valid times, explicit observed/forecast labels, source fields, and missing-value masks. An overlay dimension stores lossless GeoJSON feature strings, including quadrant radii, source CRS and original metadata. This is an application schema, not a claimed CF-compliant gridded dataset.

The WMO feed supplies analysis time and does not always supply advisory issuance or wind-averaging period. Those fields remain unavailable unless independently matched to an official product. Analysis time, issue time, and retrieval time are distinct.

NOAA GIS may use geographic angular coordinates on its documented spherical CRS. Native longitude/latitude values are retained for display, and the original CRS WKT is exported; no datum shift is claimed.

## Sources and coverage limits

This version uses WMO SWIC's public website JSON feed for RSMC/TCWC tracks, with NOAA NHC/CPHC GIS supplements. Read [SOURCES.md](SOURCES.md) for exact endpoints, issuer mapping, metadata handling, and limitations.

The verified WMO mapping contains all six RSMCs and Melbourne/Wellington TCWC entries. Jakarta and Port Moresby direct feeds are not integrated. The feed is not a guaranteed complete global advisory archive.

Polygon cones and wind overlays are integrated for NHC/CPHC only, when source identifiers and advisory cycles match. Other centres' available wind-radius text is preserved but is not converted into inferred geometry. Other agencies' cone feeds remain future integration work. Missing, failed, or mismatched products are labeled.

The archive contains only data actually retrieved. It cannot fill periods when the dashboard was closed, and snapshots may omit advisories appearing between checks. No archive purge runs automatically.

## Files, Python API, and diagnostics

The provider.py module retrieves and validates data; archive.py stores SQLite advisory versions; exports.py supplies the independent export API; server.py serves the app and manages polling. The static directory contains the interface and offline basemap.

The complete example examples/use_archive.py reads an existing archive and exports an advisory without starting the dashboard or making network requests.

The data/advisories.sqlite3 file contains advisory snapshots and original-source ZIPs. The data/monitor.log file retains server diagnostics; stdout/stderr remain visible. When backing up, stop the server and copy the whole data directory, including any SQLite WAL/SHM files. Data, virtual environments, research downloads, caches, exports, and build output are excluded from Git.

## Verification

Install test dependencies with **.\.venv\Scripts\python.exe -m pip install ".[test]"**. Run **.\.venv\Scripts\python.exe -m pytest -v**. Tests use explicitly synthetic fixtures and never present them as current storms.

Run **.\.venv\Scripts\python.exe examples/live_check.py --data-dir data** for a one-shot live check. It logs provider errors, checks archive deduplication and exports, and writes data/live-check.json plus data/live-check.log. This command intentionally fetches once independently of browser sessions.

Build distributions with **.\.venv\Scripts\python.exe -m build**. These commands do not publish to GitHub or a package registry, commit, or push.

## Execution location

This project runs locally. No Colab runtime, Google Drive API, GitHub remote, or hosted website is involved. The checkout is under OneDrive; its synchronization is outside the package's control.
