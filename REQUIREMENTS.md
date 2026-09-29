# Workspace requirements

## User request

Create software to track tropical cyclones, explore the requirements before implementation, and split the following use cases into different projects.

## Project boundaries

1: `cyclone-monitor` owns active-storm retrieval and presentation of official observations and forecasts.

2: `cyclone-history` owns historical track ingestion and retrospective analysis.

3: `cyclone-detect` owns detection and temporal linking in gridded model output.

Each project owns its dependencies, interfaces, tests, and documentation. No shared runtime package is required at this stage. Exchange formats can be agreed later if an actual cross-project use case requires them.

## Current stage

Cyclone Monitor version 0.1.0 is implemented as the cyclone-monitor-local Python distribution with a Flask/Waitress/Leaflet dashboard running locally. It uses WMO RSMC/TCWC track data, matching NOAA cone/wind GIS products, five-minute session-scoped refresh, SQLite advisory replay, and CSV/GeoJSON/NetCDF exports. Source gaps and scientific interpretation limits are documented in cyclone-monitor/SOURCES.md. The other two projects remain at the requirements stage.

Implementation and verification run locally. The user requested a GitHub push on 2026-09-29; publication status is recorded in the append-only work log.

Both direct agency feeds and official WMO aggregation are accepted, with original attribution, time semantics, and provenance preserved. Live WMO and NOAA feed retrievals have been verified. The public WMO website interface is not a guaranteed complete/stable API; direct Jakarta/Port Moresby feeds and non-NOAA polygon overlays remain outside the implemented adapters.

Cyclone Monitor will persist each distinct retrieved advisory locally for replay, comparison, and export, retaining corrections and avoiding duplicate versions from unchanged polls. This operational archive belongs to the monitor; historical dataset research remains a separate project. Collection gaps while the dashboard is closed are possible.

The first dashboard includes observed and official forecast tracks, wind speed, pressure, source and time metadata, plus official uncertainty cones and wind-radius overlays where published. Missing fields and overlays are marked unavailable; the monitor does not estimate missing official products.
