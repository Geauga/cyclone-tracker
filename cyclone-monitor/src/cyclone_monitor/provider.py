# provider.py
# User request: global official advisories and source-backed cone/wind overlays.
import io
import json
import logging
import math
import re
import ssl
import time
import zipfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import certifi
import shapefile
from shapely import affinity
from shapely.geometry import LineString, Polygon, box, mapping, shape

LOG = logging.getLogger(__name__)
SWIC = "https://severeweather.wmo.int/json/"
NHC = "https://www.nhc.noaa.gov/CurrentStorms.json"
CENTRES = {
    "3": "RSMC Honolulu", "4": "RSMC Miami", "5": "RSMC Tokyo",
    "6": "RSMC New Delhi", "7": "RSMC La Réunion",
    "8": "TCWC Melbourne", "9": "TCWC Melbourne", "10": "TCWC Melbourne",
    "11": "RSMC Nadi", "12": "TCWC Wellington",
}
COVERAGE = [
    "WMO public website feed; not a guaranteed complete or supported API.",
    "Jakarta and Port Moresby are not represented in the verified WMO issuer mapping; direct feeds are not integrated.",
    "Official cone and polygon wind overlays are integrated for NHC/CPHC when linked and time-matched; other centres' raw wind-radius text is retained.",
    "Absence from this index does not establish that a centre has no active cyclone.",
]


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dt(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def iso(value):
    return dt(value).isoformat().replace("+00:00", "Z")


def number(value):
    if value is None or str(value).strip() in ("", "null", "None"):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite numeric field")
    return result


class HTTPClient:
    """Small conditional-request client, with visible errors and host retry delays."""
    def __init__(self):
        self.cache = {}
        self.retry_after = {}

    def get(self, url):
        host = urlparse(url).hostname
        if urlparse(url).scheme != "https" or host not in {
            "severeweather.wmo.int", "www.nhc.noaa.gov", "www.hurricanes.gov",
        }:
            raise ValueError("Unapproved official data URL: " + url)
        if time.time() < self.retry_after.get(host, 0):
            raise RuntimeError("Provider retry delay in effect for " + host)
        previous = self.cache.get(url)
        headers = {"User-Agent": "CycloneMonitorLocal/0.1 (official-advisory research)"}
        if previous:
            if previous[1]:
                headers["If-None-Match"] = previous[1]
            if previous[2]:
                headers["If-Modified-Since"] = previous[2]
        LOG.info("Fetching %s", url)
        try:
            with urlopen(Request(url, headers=headers), timeout=20,
                         context=ssl.create_default_context(cafile=certifi.where())) as response:
                if urlparse(response.url).hostname not in {
                    "severeweather.wmo.int", "www.nhc.noaa.gov", "www.hurricanes.gov",
                }:
                    raise ValueError("Unexpected redirect host")
                data = response.read(25_000_001)
                if len(data) > 25_000_000:
                    raise ValueError("Official product exceeds 25 MB limit")
                self.cache[url] = (data, response.headers.get("ETag"),
                                   response.headers.get("Last-Modified"))
                return data
        except HTTPError as exc:
            if exc.code == 304 and previous:
                LOG.info("Unchanged: %s", url)
                return previous[0]
            if exc.code in (429, 503):
                wait = exc.headers.get("Retry-After", "300")
                try:
                    deadline = time.time() + float(wait)
                except ValueError:
                    try:
                        deadline = parsedate_to_datetime(wait).timestamp()
                    except (ValueError, TypeError):
                        deadline = time.time() + 300
                self.retry_after[host] = max(time.time() + 30, deadline)
            raise


def split_dateline(geometry):
    """Unwrap consecutive vertices, clip at world boundaries, return valid GeoJSON."""
    def unwrap(coords):
        out = []
        for coord in coords:
            lon, lat = coord[:2]
            if out:
                while lon - out[-1][0] > 180:
                    lon -= 360
                while lon - out[-1][0] < -180:
                    lon += 360
            out.append((lon, lat))
        return out
    kind = geometry["type"]
    if kind == "Point":
        lon, lat = geometry["coordinates"][:2]
        return {"type": "Point", "coordinates": [((lon + 180) % 360) - 180, lat]}
    if kind in ("MultiPolygon", "MultiLineString"):
        single = "Polygon" if kind == "MultiPolygon" else "LineString"
        parts = []
        for coords in geometry["coordinates"]:
            result = split_dateline({"type": single, "coordinates": coords})
            parts.extend(result["coordinates"] if result["type"] == kind else [result["coordinates"]])
        return {"type": kind, "coordinates": parts}
    if kind == "LineString":
        geom = LineString(unwrap(geometry["coordinates"]))
    elif kind == "Polygon":
        rings = geometry["coordinates"]
        shell = unwrap(rings[0])
        holes = []
        for ring in rings[1:]:
            hole = unwrap(ring)
            shift = round((shell[0][0] - hole[0][0]) / 360) * 360
            holes.append([(x + shift, y) for x, y in hole])
        geom = Polygon(shell, holes)
        if not geom.is_valid:
            raise ValueError("Invalid official polygon; not repaired silently")
    else:
        return geometry
    pieces = []
    lo, _, hi, _ = geom.bounds
    for world in range(math.floor((lo + 180) / 360), math.floor((hi + 180) / 360) + 1):
        part = geom.intersection(box(-180 + 360 * world, -90, 180 + 360 * world, 90))
        part = affinity.translate(part, xoff=-360 * world)
        for item in getattr(part, "geoms", [part]):
            if not item.is_empty and item.geom_type == kind:
                pieces.append(mapping(item)["coordinates"])
    if len(pieces) == 1:
        return {"type": kind, "coordinates": pieces[0]}
    return {"type": "Multi" + kind, "coordinates": pieces}


def parse_swic(data, source_url, group_id):
    tracks = data.get("track")
    forecasts = data.get("forecast")
    if not isinstance(tracks, list) or not tracks or not isinstance(forecasts, list):
        raise ValueError("Unrecognized WMO track/forecast schema")
    latest = tracks[-1]
    centre_id = str(latest["center_id"])
    if centre_id not in CENTRES:
        raise ValueError("Issuer is not a supported RSMC/TCWC: " + centre_id)
    reference = dt(latest["analysis_time"])
    points = []
    for kind, values in (("observed", tracks), ("forecast", forecasts)):
        for p in values:
            if kind == "observed":
                valid = iso(p["analysis_time"])
            elif p.get("forecast_time"):
                valid = iso(p["forecast_time"])
            else:
                lead = str(p.get("time_interval", ""))
                if not re.fullmatch(r"\d{3,}", lead) or int(lead[-2:]) >= 60:
                    raise ValueError("Invalid forecast time interval: " + lead)
                valid = (reference + timedelta(hours=int(lead[:-2]), minutes=int(lead[-2:]))).isoformat().replace("+00:00", "Z")
            lat, lon = number(p.get("lat")), number(p.get("lng"))
            if lat is None or lon is None or not -90 <= lat <= 90 or not -360 <= lon <= 360:
                raise ValueError("Missing or invalid track coordinates")
            pressure, wind = number(p.get("pressure")), number(p.get("max_wind_speed"))
            points.append({
                "kind": kind, "valid_time": valid, "latitude": lat,
                "longitude": ((lon + 180) % 360) - 180,
                "wind_kt": wind, "pressure_hpa": pressure,
                "gust_kt": number(p.get("gust")), "intensity": p.get("intensity"),
                "wind_radii_text": p.get("wind_radii"),
                "issuer": CENTRES.get(str(p.get("center_id", centre_id)), "Unmapped source centre"),
                "source_storm_id": p.get("tc_id", latest.get("tc_id")),
                "wind_averaging_minutes": None,
            })
    key = "swic-" + str(data["sys_id"]) + "-" + centre_id
    return {
        "key": key, "group_id": group_id, "name": latest.get("tc_name") or latest.get("tc_id") or key,
        "storm_id": latest.get("tc_id") or str(data["sys_id"]),
        "issuer": CENTRES[centre_id], "centre_id": centre_id,
        "analysis_time": iso(latest["analysis_time"]), "issue_time": None,
        "issue_time_note": "WMO supplies analysis time; advisory issuance is not supplied in this feed.",
        "source_url": source_url, "points": points, "overlays": [],
        "overlay_status": {"cone": "Unavailable in WMO track feed", "wind": "Polygon overlay unavailable; any published radii text is retained"},
    }


def parse_gis(raw, kind, meta, product):
    features = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(n.file_size for n in z.infolist()) > 80_000_000:
            raise ValueError("GIS archive expands beyond 80 MB")
        for name in z.namelist():
            wanted = name.endswith("_pgn.shp") if kind == "cone" else name.endswith("_forecastradii.shp")
            if not wanted:
                continue
            stem = name[:-4]
            projection = z.read(stem + ".prj").decode("utf-8", errors="replace")
            # NOAA publishes degree longitude/latitude on its 6,371,200 m sphere.
            # Preserve that CRS explicitly; do not claim a datum transformation.
            geographic = projection.startswith("GEOGCS[") and 'UNIT["Degree"' in projection
            known_datum = "WGS" in projection or ('GCS_Sphere' in projection and '6371200' in projection)
            if not geographic or not known_datum:
                raise ValueError("GIS coordinate system is not recognized geographic longitude/latitude")
            reader = shapefile.Reader(shp=io.BytesIO(z.read(name)), dbf=io.BytesIO(z.read(stem + ".dbf")),
                                      shx=io.BytesIO(z.read(stem + ".shx")))
            for record in reader.iterShapeRecords():
                props = record.record.as_dict()
                adv = str(props.get("ADVISNUM", props.get("ADVNUM", "")))
                if adv.lstrip("0") != str(meta["advNum"]).lstrip("0"):
                    raise ValueError("GIS advisory number differs from linked product")
                if props.get("STORMID") and props["STORMID"].lower() != product["storm_id"].lower():
                    raise ValueError("GIS storm identifier mismatch")
                valid = None
                if re.fullmatch(r"\d{10}", str(props.get("VALIDTIME", ""))):
                    valid = datetime.strptime(props["VALIDTIME"], "%Y%m%d%H").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                props.update(kind=kind, issue_time=meta["issuance"], valid_time=valid,
                             issuer=product["issuer"], source_url=meta["zipFile"],
                             source_crs_wkt=projection,
                             coordinate_handling="Native geographic longitude/latitude in degrees; no datum shift applied",
                             threshold_kt=props.get("RADII"),
                             meaning=("Official NHC track uncertainty cone; not a wind-impact boundary"
                                      if kind == "cone" else "Official sustained-wind extent; source quadrant radii are in nautical miles"))
                zero_extent = kind == "wind" and all(props.get(q) == 0 for q in ("NE", "SE", "SW", "NW"))
                props["no_extent"] = zero_extent
                geometry = None if zero_extent else split_dateline(record.shape.__geo_interface__)
                features.append({"type": "Feature", "geometry": geometry, "properties": props})
    if not features:
        raise ValueError("Expected GIS polygon layer not present")
    return features


class OfficialProvider:
    def __init__(self, client=None):
        self.client = client or HTTPClient()

    def collect(self):
        """Fetch one snapshot. Returns products, exact source bytes, and explicit failures."""
        index_bytes = self.client.get(SWIC + "tc_inforce.json")
        index = json.loads(index_bytes)
        if not isinstance(index.get("inforce"), list) or not index.get("update"):
            raise ValueError("Unrecognized WMO active index")
        errors, products, expected = [], [], []
        nhc_raw = None
        nhc_storms = {}
        try:
            nhc_raw = self.client.get(NHC)
            nhc_storms = {s["id"].upper(): s for s in json.loads(nhc_raw)["activeStorms"]}
        except Exception as exc:
            LOG.exception("NHC overlay index failed")
            errors.append("NHC overlays: " + str(exc))
        for row in index["inforce"]:
            if not isinstance(row, list) or len(row) < 8:
                raise ValueError("Unrecognized WMO index row")
            group_id = str(row[0])
            ids = [group_id] + str(row[6] or "").split(",")
            centres = str(row[7]).split(",")
            if len([v for v in ids if v]) != len(centres):
                errors.append("WMO issuer association mismatch for " + group_id)
                continue
            for sysid, centre in zip(ids, centres):
                if centre not in CENTRES:
                    continue
                if not re.fullmatch(r"\d+", sysid):
                    errors.append("Invalid WMO system identifier")
                    continue
                key = "swic-" + sysid + "-" + centre
                expected.append(key)
                url = SWIC + "tc_" + sysid + ".json"
                try:
                    raw = self.client.get(url)
                    p = parse_swic(json.loads(raw), url, group_id)
                    if p["key"] != key:
                        raise ValueError("Index and advisory issuer differ")
                    sources = {"wmo-advisory.json": raw, "wmo-index.json": index_bytes}
                    storm = nhc_storms.get(p["storm_id"].upper()) if centre in ("3", "4") else None
                    if storm:
                        sources["nhc-index.json"] = nhc_raw
                        # Attach only products from the same WMO analysis/advisory cycle.
                        for kind, field in (("cone", "trackCone"), ("wind", "forecastWindRadiiGIS")):
                            meta = storm.get(field)
                            if not meta:
                                p["overlay_status"][kind] = "Unavailable: no linked official GIS product"
                                continue
                            if iso(meta["issuance"]) != p["analysis_time"]:
                                p["overlay_status"][kind] = "Unavailable: latest GIS and WMO cycles differ"
                                continue
                            try:
                                gis = self.client.get(meta["zipFile"])
                                sources[kind + ".zip"] = gis
                                features = parse_gis(gis, kind, meta, p)
                                p["overlays"].extend(features)
                                p["overlay_status"][kind] = (
                                    "Official radii are zero; no area to draw"
                                    if all(f["properties"]["no_extent"] for f in features) else "Available")
                                p["issue_time"] = iso(meta["issuance"])
                                p["issue_time_note"] = "Matched NOAA GIS advisory issuance."
                            except Exception as exc:
                                LOG.exception("Overlay failed for %s %s", key, kind)
                                p["overlay_status"][kind] = "Retrieval/parse failure: " + str(exc)
                                errors.append(key + " " + kind + ": " + str(exc))
                    elif centre in ("3", "4") and nhc_raw is None:
                        p["overlay_status"] = {k: "Retrieval failure: NHC index unavailable" for k in ("cone", "wind")}
                    products.append((p, sources))
                except Exception as exc:
                    LOG.exception("Storm failed: %s", key)
                    errors.append(key + ": " + str(exc))
        return {"products": products, "expected_keys": expected, "errors": errors,
                "index_time": iso(index["update"]), "index_count": len(index["inforce"]),
                "retrieved_at": utcnow(), "coverage": COVERAGE}

# Purpose: official feed ingestion and geometry validation; upstream: WMO SWIC JSON and NOAA GIS.
# Upstream purpose: distribute official observations/forecasts. Environment: Python 3.11+, internet.
# Generated: 2026-09-28 America/New_York. New implementation; provider limits are documented in SOURCES.md.
# Change record: new implementation, lines 1-339; finalized 2026-09-29 America/New_York.
