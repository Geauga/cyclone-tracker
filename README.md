# Tropical cyclone projects

This workspace contains three independently scoped projects. Each directory has its own requirements, agent operating instructions, and append-only work log.

1: `cyclone-monitor` — Retrieve and present active tropical cyclones, observed positions, intensity, and official forecast tracks.

2: `cyclone-history` — Load historical cyclone tracks, compare storms, and calculate research statistics.

3: `cyclone-detect` — Detect and follow tropical cyclones in gridded weather or climate-model output.

Cyclone Monitor now has a working Python package and local browser dashboard, using WMO official-centre track data and matched NOAA GIS overlays. It updates every five minutes (configurable) while open and includes manual refresh, SQLite advisory replay, and CSV/GeoJSON/NetCDF exports. See [launch instructions](cyclone-monitor/README.md) and [coverage limits](cyclone-monitor/SOURCES.md). Cyclone History and Cyclone Detect remain specification projects.

The directories currently share this local Git repository. They are not separate Git repositories or registered Codex projects. Do not introduce nested repositories. Each project should remain independently installable and testable when implemented, without imports from sibling projects.

Cyclone Monitor accepts direct agency feeds and official WMO aggregation while retaining original issuer metadata. The implemented WMO mapping includes six RSMCs and Melbourne/Wellington entries; Jakarta and Port Moresby direct feeds are not integrated. Polygon overlays currently use NHC/CPHC products only.

The monitor will also retain distinct retrieved advisories locally for replay, comparison, and export across restarts. This archive may have gaps when the dashboard is closed.

The selected dashboard scope includes tracks, intensity, advisory metadata, and official uncertainty cones and wind-radius overlays where available. Unavailable source fields or overlays will be labeled rather than estimated.

Execution location: local filesystem and local Git repository. No GitHub, Google Drive API, or Colab execution has been performed. The workspace resides under the user's OneDrive directory; OneDrive synchronization is outside this task's verification.
