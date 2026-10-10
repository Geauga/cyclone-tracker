# track_map.py
# User request: generate portable cyclone track maps for a public repository.
import argparse
import copy
import html
import json
import math
import textwrap
from pathlib import Path
from shapely.geometry import shape
from shapely.errors import GEOSException

from .archive import Archive
from .exports import export_geojson

STATIC = Path(__file__).with_name("static")
COLORS = {"observed": "#087f86", "observed_track": "#087f86", "forecast": "#376b91",
          "forecast_track": "#376b91", "cone": "#669ab5", "wind": "#bd902a"}


def _collection(data):
    if not isinstance(data, dict):
        raise ValueError("Map input must be an advisory or GeoJSON object")
    if data.get("type") != "FeatureCollection":
        data = json.loads(export_geojson(data))
    data = copy.deepcopy(data)
    if not isinstance(data.get("features"), list) or not data["features"]:
        raise ValueError("Map input must contain GeoJSON features")
    def validate_coordinates(coords):
        if not isinstance(coords, list) or not coords:
            raise ValueError("Empty or malformed geometry coordinates")
        if isinstance(coords[0], (int, float)):
            if len(coords) < 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                                     not math.isfinite(v) for v in coords):
                raise ValueError("Coordinates must be finite numbers")
            if not -180 <= coords[0] <= 180 or not -90 <= coords[1] <= 90:
                raise ValueError("Expected geographic longitude/latitude in degrees")
        else:
            for child in coords:
                validate_coordinates(child)
    for feature in data["features"]:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("Expected GeoJSON Features")
        feature["properties"] = feature.get("properties") or {}
        if not isinstance(feature["properties"], dict):
            raise ValueError("Feature properties must be an object")
        geometry = feature.get("geometry")
        if geometry is not None:
            if not isinstance(geometry, dict):
                raise ValueError("Geometry must be an object or null")
            if geometry.get("type") not in {"Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
                raise ValueError("Unsupported map geometry")
            validate_coordinates(geometry.get("coordinates"))
            try:
                parsed = shape(geometry)
                if parsed.is_empty or not parsed.is_valid:
                    raise ValueError("Empty or invalid map geometry")
            except (GEOSException, TypeError, IndexError) as exc:
                raise ValueError("Malformed map geometry") from exc
    if not any(f.get("geometry") for f in data["features"]):
        raise ValueError("Map input has no drawable geometry")
    # Also reject NaN in properties, rather than embedding invalid JavaScript/JSON.
    json.dumps(data, allow_nan=False)
    return data


def _details(data):
    keys = ("name", "storm_id", "issuer", "analysis_time", "issue_time", "version", "retrieved_at", "source_url")
    details = []
    for key in keys:
        values = list(dict.fromkeys(str(f["properties"][key]) for f in data["features"]
                                    if f["properties"].get(key) is not None))
        if values:
            details.append(key.replace("_", " ").title() + ": " + "; ".join(values))
    return details


def _safe_json(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _html_map(data, title):
    template = (STATIC / "track-map.html").read_text(encoding="utf-8")
    leaflet = (STATIC / "vendor/leaflet.js").read_text(encoding="utf-8")
    # Leaflet's optional layer-toggle icons are not used; strip asset URLs to keep the file offline.
    css = (STATIC / "vendor/leaflet.css").read_text(encoding="utf-8")
    import re
    css = re.sub(r"url\([^)]*\)", "none", css)
    replacements = {"TITLE": html.escape(title), "DETAILS": "\n".join(_details(data)),
                    "DATA": _safe_json(data), "BASEMAP": (STATIC / "countries.geojson").read_text(encoding="utf-8"),
                    "LEAFLET_JS": leaflet, "LEAFLET_CSS": css,
                    "MAP_JS": (STATIC / "track-map.js").read_text(encoding="utf-8")}
    # One pass: untrusted values cannot introduce a new placeholder for later substitution.
    return re.sub(r"@@([A-Z_]+)@@", lambda m: html.escape(replacements[m[1]]) if m[1] == "DETAILS"
                  else replacements[m[1]], template).encode("utf-8")


def _svg_map(data, title):
    escape = html.escape
    details = [line for detail in _details(data) for line in textwrap.wrap(detail, width=130)]
    top = max(150, 100 + 17 * len(details))
    bottom, footer = top + 540, top + 570
    height = footer + 120
    def xy(point):
        return 50 + (point[0] + 180) * 3, top + (90 - point[1]) * 3
    def path(geometry):
        kind, coords = geometry["type"], geometry["coordinates"]
        groups = [coords] if kind == "LineString" else coords if kind in {"MultiLineString", "Polygon"} else [r for p in coords for r in p]
        return " ".join("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, group)) +
                        (" Z" if "Polygon" in kind else "") for group in groups)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 {height}" role="img">',
             '<title>' + escape(title) + '</title>',
             f'<defs><clipPath id="world"><rect x="50" y="{top}" width="1080" height="540"/></clipPath></defs>',
             f'<rect width="1180" height="{height}" fill="#f7fafb"/>',
             '<g font-family="sans-serif" fill="#173747">',
             f'<text x="50" y="38" font-size="24">{escape(title)}</text>',
             '<text x="50" y="64" font-size="13">Archived / imported snapshot · UTC times · Original wind conventions</text>']
    for i, detail in enumerate(details):
        parts.append(f'<text x="50" y="{84 + i * 17}" font-size="12">{escape(detail)}</text>')
    parts.append(f'<g clip-path="url(#world)"><rect x="50" y="{top}" width="1080" height="540" fill="#dcebf0"/>')
    basemap = json.loads((STATIC / "countries.geojson").read_text(encoding="utf-8"))
    for f in basemap["features"]:
        parts.append(f'<path d="{path(f["geometry"])}" fill="#f2f4ee" stroke="#b2c6cc" stroke-width="0.5" fill-rule="evenodd"/>')
    for lon in range(-180, 181, 30):
        x, _ = xy([lon, 0])
        parts.append(f'<path d="M{x},{top} V{bottom}" stroke="#bacfd6" stroke-width="0.5"/>')
    for lat in range(-60, 61, 30):
        _, y = xy([0, lat])
        parts.append(f'<path d="M50,{y} H1130" stroke="#bacfd6" stroke-width="0.5"/>')
    # Polygons first, tracks second, points last so observations remain visible.
    features = sorted(data["features"], key=lambda f: 0 if "Polygon" in (f.get("geometry") or {}).get("type", "")
                      else 2 if (f.get("geometry") or {}).get("type") == "Point" else 1)
    for feature in features:
        geometry, props = feature.get("geometry"), feature["properties"]
        if geometry is None:
            continue
        color = COLORS.get(props.get("kind"), "#586d85")
        tooltip = escape(json.dumps(props, ensure_ascii=False, allow_nan=False))
        if geometry["type"] == "Point":
            x, y = xy(geometry["coordinates"])
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" stroke="white"><title>{tooltip}</title></circle>')
        else:
            polygon = "Polygon" in geometry["type"]
            dash = ' stroke-dasharray="7 5"' if props.get("kind") == "forecast_track" else ""
            parts.append(f'<path d="{path(geometry)}" fill="{color if polygon else "none"}" fill-opacity="0.2" '
                         f'stroke="{color}" stroke-width="{1 if polygon else 2.5}" fill-rule="evenodd"{dash}><title>{tooltip}</title></path>')
    parts.append(f'</g><text x="50" y="{footer}" font-size="14">Teal: observed · Dashed blue: forecast · Blue fill: official cone · Gold: wind extent</text>')
    parts.append(f'<text x="50" y="{footer+23}" font-size="12">Equirectangular projection · Natural Earth public-domain basemap · Cones are not wind-impact boundaries</text>')
    parts.append(f'<text x="50" y="{footer+46}" font-size="12">Missing overlays are not estimated. Zero-radius features retain metadata with no drawn extent.</text>')
    parts.append('<metadata>' + escape(json.dumps({"details": _details(data), "geojson": data}, allow_nan=False)) + '</metadata></g></svg>')
    return "\n".join(parts).encode("utf-8")


def export_track_map(data, format="html", title=None):
    """Return a self-contained HTML map or SVG from an advisory or FeatureCollection."""
    collection = _collection(data)
    names = list(dict.fromkeys(str(f["properties"]["name"]) for f in collection["features"] if f["properties"].get("name")))
    title = title or (" / ".join(names) + " · Track map" if names else "Cyclone track map")
    if format == "html":
        return _html_map(collection, title)
    if format == "svg":
        return _svg_map(collection, title)
    raise ValueError("Map format must be html or svg")


def write_track_map(data, output, format=None, title=None):
    """Generate first, then write; an invalid input leaves existing output untouched."""
    output = Path(output)
    payload = export_track_map(data, format or output.suffix.lstrip(".").lower(), title)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a portable cyclone track map without fetching data")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", type=Path, help="Existing advisories.sqlite3")
    source.add_argument("--geojson", type=Path, help="Exported geographic FeatureCollection")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--version", help="Exact archived advisory version")
    selection.add_argument("--storm", help="Archive storm key; select its newest snapshot")
    parser.add_argument("--output", type=Path, required=True, help="Output .html or .svg")
    parser.add_argument("--format", choices=("html", "svg"))
    parser.add_argument("--title")
    args = parser.parse_args(argv)
    if args.geojson and (args.version or args.storm):
        parser.error("--version and --storm require --archive")
    try:
        if not (args.archive or args.geojson).is_file():
            raise ValueError("Input file does not exist")
        if args.archive:
            archive = Archive(args.archive)
            versions = archive.versions(args.storm)
            if not versions and not args.version:
                raise ValueError("No matching archived advisory")
            data = archive.get(args.version or versions[0]["version"])
            print("Selected snapshot:", data["key"], data["version"], data["analysis_time"])
        else:
            data = json.loads(args.geojson.read_text(encoding="utf-8-sig"))
        output = write_track_map(data, args.output, args.format, args.title)
        print("Generated track map:", output.resolve())
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
# Purpose: independent portable interactive/vector maps with original provenance.
# Upstream: Archive and export_geojson retain official advisory tracks and geometry.
# Environment: Python 3.11+, bundled Leaflet/Natural Earth. Generated: 2026-10-09 America/New_York.
# Change record: new file, lines 1-211; finalized 2026-10-10 America/New_York.
