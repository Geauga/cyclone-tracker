# Cyclone Monitor

## Purpose

Retrieve active tropical cyclones and present their observed positions, reported intensity, and official forecast tracks.

## Confirmed direction

The user selected Cyclone Monitor as the first project and requested global coverage from RSMCs (written as "RMSCs" in the prompt).

The selected deliverable is an installable Python package plus a web dashboard with an interactive map of storms and official forecast tracks. The package must be usable independently in scripts and notebooks. The dashboard uses the package's retrieval and processing logic. The user selected local deployment: run on the user's computer and open in a browser, binding to the loopback interface by default. Fetch official data over the internet. The implementation uses Flask, Waitress, and Leaflet.

The user selected automatic updates every five minutes while the dashboard is open, with a manual Refresh button. The five-minute default interval is configurable. Automatic polling stops when no dashboard sessions remain open; a running local server alone must not continue polling. No operating-system scheduler or Codex automation is required. A refresh checks for newly available official products; it does not imply that the issuing centre has published a new advisory. Respect provider rate limits and retry delays; display any resulting delay or retrieval failure.

Use official WMO-designated tropical cyclone centres as the source authorities. WMO lists six RSMCs: Miami, Honolulu, Tokyo, New Delhi, La Reunion, and Nadi. Global coverage also requires the regional responsibilities of TCWCs; WMO lists Melbourne, Jakarta, Port Moresby, and Wellington. Including these TCWCs is the working interpretation of the global-coverage requirement, not an additional explicit user selection.

Sources checked on 2026-09-28: [WMO RSMC directory](https://severeweather.wmo.int/rsmcs.html) and [WMO TCWC directory](https://severeweather.wmo.int/tcwcs.html). These establish source authorities. Implemented endpoints and known coverage limits are recorded in SOURCES.md. Centre-specific publication schedules and remaining direct-feed integrations require further investigation.

The user accepts official WMO aggregation as well as direct RSMC/TCWC feeds, provided original issuing-centre attribution, advisory time, and provenance are preserved. Record the distribution endpoint separately from the issuing centre; WMO distribution does not make WMO the advisory issuer. The [WMO SWIC source policy](https://severeweather.wmo.int/tc.html), checked on 2026-09-28, identifies RSMC/TCWC advisories and NMHS warnings as its sources and notes that information from different centres may differ. Filter and label products according to their issuing authority rather than assuming every aggregated product is an RSMC advisory. This policy check does not establish a supported API, completeness, update latency, or automated access conditions. Live feed and synthetic edge-case validation results are recorded in VALIDATION.md.

Preserve the issuing centre, original storm identifier, source URL, issue time, valid time, intensity units, and source wind-averaging period when available. Do not silently treat different intensity conventions as equivalent. Represent missing provider coverage or a failed feed explicitly; do not report it as no active storms. Storm handoffs between centres require identity reconciliation without discarding the source identifiers.

The user selected a persistent local archive of every distinct advisory actually retrieved, supporting later replay, comparison, and export. Repeated retrieval of unchanged advisory content must not create duplicate advisory versions. Preserve corrected or revised content even if its advisory identifier or issue time is unchanged. Store original source content alongside parsed data and provenance, including retrieval time, so archived data can be inspected and reprocessed. Record multiple distribution sources without conflating advisories issued by different centres. Do not automatically delete archived advisories by default. The archive persists across dashboard restarts; gaps while the dashboard is closed remain possible and must not be represented as complete coverage.

## Scope

1: Identify active storms within the selected agency coverage and retain source storm identifiers.

2: Retrieve source observations and official forecast tracks with issue times, valid times, units, and provenance.

3: Provide a Python API and an interactive web dashboard to list storms, inspect an individual storm's available data, and map observed positions and official forecast tracks. Keep observed and forecast positions visually distinguishable and show source and data times.

4: Distinguish an authoritative empty response from unavailable, malformed, or stale data. Preserve diagnostics for failed retrievals.

5: Archive retrieved advisory versions locally and support selecting earlier advisories for replay, comparison, and export. Clearly distinguish archived views from the latest available data.

6: Include the user-selected core storm information (observed tracks, official forecast tracks, wind speed, pressure, issuing centre, and advisory times) plus official uncertainty cones and wind-radius overlays wherever available. Expose layer toggles and a legend identifying each overlay's issuing centre, advisory issue time, forecast valid time or lead time, units, and wind threshold or published uncertainty meaning as applicable. Preserve published wind-averaging periods, directional/quadrant radii, and asymmetric geometry. Do not silently equate different agencies' definitions or assign a probability where none is supplied.

7: Use official published geometry or render explicitly published radii according to their documented definitions. Never invent a cone from forecast track spread or estimate missing wind radii. Distinguish a missing field, an explicit zero, and a failed overlay retrieval. Label unavailable fields and overlays clearly. When replaying an archived advisory, show only overlays associated with that advisory and their actual valid times.

## Boundaries

Historical dataset ingestion and retrospective research belong to `cyclone-history`. Archiving and replaying advisories collected by this monitor belong to `cyclone-monitor`. Detection in model grids belongs to `cyclone-detect`. This project consumes official forecasts; generating forecasts is outside the initial scope.

## Implementation decisions and remaining integration work

1: Implemented the WMO SWIC JSON adapter, filtering the verified RSMC/TCWC issuer mapping, with matched NHC/CPHC GIS supplements. Exact feeds, validation rules, and coverage gaps are documented in SOURCES.md. Jakarta/Port Moresby direct feeds and non-NOAA polygon overlays remain unimplemented.

2: Implemented a Python package with Flask/Waitress on loopback, a Leaflet dashboard, and a bundled Natural Earth offline basemap. The Windows launcher uses the project virtual environment and local data directory.

3: Implemented configurable five-minute polling during live browser sessions, manual refresh, request coalescing, and session expiry. No collection starts after all sessions close; an in-flight request can finish. Records older than 12 hours are highlighted as a display threshold. Centre-specific publication/freshness schedules remain future work.

4: The user selected CSV, GeoJSON, and NetCDF exports, all implemented, plus original-source ZIP downloads. Notifications and additional layers were not requested. Current cone/wind polygon integration is limited to matching NHC/CPHC products; other source radii text is preserved without inferred geometry.

5: Implemented a transactional SQLite archive with content-based snapshot deduplication, source ZIPs, advisory selection/replay, and comparison tracks. Changes in parsed/enriched content can create snapshot revisions even when source issue time is unchanged. Source handoffs retain WMO group associations; unidentified cross-basin handoffs are not guessed from names.

## Proposed acceptance criteria

Verify at least one representative provider response, no-active-storm response, stale response, and retrieval failure. Observations and forecasts must remain distinguishable, including issue and valid times. Any cached data must retain its retrieval time and source. Confirm actual provider interfaces against official documentation during implementation.

Verify the five-minute default and configurable polling interval with an active dashboard session, manual refresh, and cessation of polling after the last dashboard session closes. Multiple open dashboard tabs must not multiply provider requests. Prevent overlapping refreshes and retain the last successfully retrieved data with an explicit failure or stale status when an update fails.

Verify archive persistence across restarts, deduplication of unchanged advisories, preservation of corrections with unchanged identifiers/timestamps, and recovery of source content and provenance. Replay must display the selected historical advisory's forecast and timestamps without substituting the latest forecast. A failed or interrupted archive write must not corrupt previously stored advisories.

Verify overlays against representative official products, preserving source definitions, wind thresholds, directional radii, issue times, and valid times. Check missing and zero radii separately, absent cones, layer toggles, mismatched advisory versions, and longitude-boundary rendering. Verify that archived replay never substitutes current overlays and that unavailable source data is never drawn as an estimated official product.

## Status

Version 0.1.0 is implemented locally. Automated behavior tests, live feed/export checks, and browser verification are described in README.md and VALIDATION.md. This is a working monitor with explicitly documented integration limits, not a claim of complete global product coverage. Historical analysis and model-grid detection remain separate specification projects.
