# exports.py
# User request: CSV, GeoJSON, and NetCDF exports retaining scientific metadata.
import csv
import io
import json
import threading

import netCDF4
import numpy as np

from .provider import dt, split_dateline

NETCDF_LOCK = threading.Lock()  # netCDF-C is not thread safe.


def metadata(p):
    return {k: p.get(k) for k in ("key", "name", "storm_id", "issuer", "analysis_time", "issue_time",
                                "source_url", "version", "retrieved_at", "issue_time_note")}


def export_csv(p):
    stream = io.StringIO(newline="")
    rows = [metadata(p) | point for point in p["points"]]
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        # Preserve numeric values; protect spreadsheet users from source-text formulas.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
                         for k, v in row.items()})
    return stream.getvalue().encode("utf-8-sig")


def export_geojson(p):
    features = []
    for point in p["points"]:
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [point["longitude"], point["latitude"]]},
                         "properties": metadata(p) | point})
    observed = [q for q in p["points"] if q["kind"] == "observed"]
    forecast = [q for q in p["points"] if q["kind"] == "forecast"]
    for kind, points in (("observed_track", observed), ("forecast_track", observed[-1:] + forecast if forecast else [])):
        if len(points) >= 2:
            geometry = split_dateline({"type": "LineString", "coordinates": [[q["longitude"], q["latitude"]] for q in points]})
            features.append({"type": "Feature", "geometry": geometry, "properties": metadata(p) | {"kind": kind}})
    features.extend(p["overlays"])
    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, allow_nan=False).encode()


def export_netcdf(p):
    """Ragged advisory point records and lossless GeoJSON overlay strings; no false CF claim."""
    with NETCDF_LOCK:
        nc = netCDF4.Dataset("advisory.nc", "w", memory=1_000_000, format="NETCDF4")
        try:
            nc.title = "Official tropical cyclone advisory snapshot"
            nc.schema_version = "cyclone-monitor-0.1"
            nc.description = "Point records with explicit observed/forecast kind; polygons preserved as GeoJSON strings."
            for key, value in metadata(p).items():
                nc.setncattr(key, "" if value is None else str(value))
            points = p["points"]
            nc.createDimension("record", len(points))
            variables = {"latitude": "degrees_north", "longitude": "degrees_east",
                         "wind_kt": "knots", "pressure_hpa": "hPa", "gust_kt": "knots",
                         "wind_averaging_minutes": "minutes"}
            for name, unit in variables.items():
                var = nc.createVariable(name, "f8", ("record",), fill_value=-9999.0)
                var.units = unit
                var[:] = np.ma.array([q.get(name) if q.get(name) is not None else 0 for q in points],
                                     mask=[q.get(name) is None for q in points])
            valid = nc.createVariable("valid_time", "f8", ("record",))
            valid.units = "seconds since 1970-01-01 00:00:00 UTC"
            valid.calendar = "proleptic_gregorian"
            valid[:] = [dt(q["valid_time"]).timestamp() for q in points]
            for name in ("kind", "issuer", "source_storm_id", "intensity", "wind_radii_text"):
                variable = nc.createVariable(name, str, ("record",))
                variable[:] = np.asarray([str(q.get(name) or "") for q in points], dtype=object)
            nc.createDimension("overlay", len(p["overlays"]))
            geometry = nc.createVariable("overlay_geojson", str, ("overlay",))
            if p["overlays"]:
                geometry[:] = np.asarray([json.dumps(v, ensure_ascii=False) for v in p["overlays"]], dtype=object)
            nc.overlay_status_json = json.dumps(p["overlay_status"])
            return bytes(nc.close())
        except Exception:
            if nc.isopen():
                nc.close()
            raise

# Purpose: self-describing portable exports. Upstream: Archive advisory documents.
# Upstream purpose: preserve retrieved official products. Environment: Python 3.11+, netCDF4.
# Generated: 2026-09-28 America/New_York. New file; no intensity averaging conversion.
# Change record: new implementation, lines 1-88; finalized 2026-09-29 America/New_York.
