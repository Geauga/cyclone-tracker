# Validation record — 2026-09-29

Execution: local Windows, Python 3.12.14, project virtual environment. No Colab or hosted deployment. Version: 0.1.0.

## Automated checks

The 19 pytest cases cover time/offset handling; missing versus zero values; source attribution and filtering; invalid coordinates and forecast intervals; snapshot deduplication, corrections and persistence; original-source recovery; dateline geometry; CSV/GeoJSON/NetCDF round trips; CSV formula escaping; session expiry and idle polling; retained cached data after retrieval failure; empty versus malformed indexes; loopback API restrictions; spherical NOAA CRS; zero-radius polygons; and advisory mismatch rejection. Fixtures are synthetic.

## Live source and browser checks

Live WMO retrieval returned six storms on September 28 and seven on September 29. These are observations of the feed during testing, not a completeness assertion or a current forecast bulletin. Archived snapshots survived a server restart. Live exports passed parsing and unchanged-advisory deduplication checks. Full diagnostics remain in ignored data/live-check.log and data/monitor.log.

NOAA GIS testing identified a spherical geographic CRS and all-zero quadrant products. The parser retains the native CRS and represents explicit zero extent with null geometry and no_extent metadata. Invalid nonzero geometry remains an explicit error. Regression cases cover these distinctions.

The dashboard was inspected at desktop and narrow widths. Hanna's official cone and wind polygons were displayed. Selecting a September 28 snapshot showed ARCHIVE REPLAY, its own analysis time, archived intensity and matching overlay times. Comparing it with September 29 showed a -5 kt selected-minus-comparison difference. The browser console contained no captured errors or warnings at the final inspection.

A NetCDF downloaded using the dashboard opened successfully with netCDF4: 11 track/intensity records and five overlay features. The independent examples/use_archive.py script exported CSV, GeoJSON and NetCDF from the existing archive without network access.

## Packaging

Both wheel and source distribution built successfully with python -m build. The wheel installed into a project-only test directory with dependencies supplied by the existing virtual environment. Python isolated-mode verification confirmed imports came from that installed wheel, and all seven checked app/API/static routes returned HTTP 200. The source archive includes documentation, examples and the Windows launcher. No archive data or research downloads are distributed. The final source test run passed all 19 cases in 0.68 seconds.

Bundled Leaflet and Natural Earth resources allow the basemap to load without third-party tile requests; dependency installation and live advisories still require internet access. Final browser capture: data/dashboard-preview.png. Temporary viewport overrides were reset and the working local tab was retained.

## Limits

The verified WMO issuer mapping includes the six RSMCs plus Melbourne and Wellington TCWCs. Jakarta and Port Moresby direct integrations remain absent. Only NHC/CPHC polygon feeds are integrated. Other radii text remains source text. No observations of inactive centres during this check establish their future feed reliability. The 12-hour age highlight is a UI threshold, not an agency-specific freshness rule.

The automated checks do not establish exhaustive provider coverage, long-duration reliability, or complete recovery from every OS interruption. Archives contain only retrieved products. This release is a local working monitor with these limits recorded explicitly.

## Track map generator — version 0.2.0, 2026-10-09/10

Added an independent CLI/Python generator and selected-advisory dashboard downloads for standalone HTML and SVG maps. No new data providers or global coverage claims were introduced. The example maps use the saved Hanna advisory analyzed at 2026-09-29 15:00 UTC, not current data.

The 27-case suite passed in 1.12 seconds. Eight new cases cover offline HTML asset embedding, hostile source-text escaping, original GeoJSON/provenance recovery, missing versus zero wind extent, preserved date-line geometry, four invalid-coordinate inputs without overwriting an existing output, GeoJSON CLI generation/missing archive handling, and exact archived-revision selection. The existing API integration case also checks HTML/SVG downloads. After the final SVG wrapping adjustment, all eight map cases passed again in 0.47 seconds. Node syntax checks passed for the generator and dashboard JavaScript.

CLI and the complete Python example generated maps from the existing archive. The SVG was rendered through a project-only PyMuPDF installation and visually inspected; timestamps and long source URLs fit the header, with track, basemap and legend visible. Preview: exports/hanna-track-preview.png. The renderer is a verification tool, not a package dependency.

Interactive browser rendering could not be inspected on October 9: the computer-use/Node runtime exited during startup on both attempts. HTML markup, embedded data, offline asset completeness and JavaScript syntax were checked. Earlier dashboard browser checks above apply to the September release. Any later browser verification is recorded in the work log.

Initial pytest errors occurred during temporary-directory setup because Windows denied access to old Temp/pytest and cache directories. Fresh project-local temporary/cache paths resolved those errors. Complete successful logs: data/map-tests-20261009-final.log and data/map-layout-tests-20261009.log. Build and installed-wheel verification details are retained in the work log. GitHub's API confirmed Geauga/cyclone-tracker is public on October 9; publication is verified again after push.

The final build/publication step was interrupted on October 9 when automatic approval review ran out of workspace credits. No action from that rejected call executed. Work resumed with the user's October 10 instruction to continue.
