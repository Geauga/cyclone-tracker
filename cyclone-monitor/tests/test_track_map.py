# test_track_map.py
# User request: verify standalone track maps, archive selection and safe offline artifacts.
import copy
import json
from html.parser import HTMLParser
from xml.etree import ElementTree

import pytest

from cyclone_monitor import Archive, export_geojson, export_track_map, write_track_map
from cyclone_monitor.provider import parse_swic
from cyclone_monitor.track_map import main


@pytest.fixture
def advisory():
    source = {"sys_id": 9999002, "gts": None, "track": [
        {"center_id": "4", "analysis_time": "2026-09-28 15:00:00", "tc_name": "SYNTHETIC TEST",
         "tc_id": "AL992026", "lat": "20", "lng": "179", "max_wind_speed": "0",
         "pressure": None, "gust": None, "wind_radii": None, "intensity": "Test"}],
        "forecast": [{"time_interval": "1200", "lat": "21", "lng": "-179",
                      "max_wind_speed": "35", "pressure": "1000", "gust": None}]}
    product = parse_swic(source, "https://severeweather.wmo.int/json/test.json", "9999002")
    product["overlays"] = [{"type": "Feature", "geometry": None,
                           "properties": {"kind": "wind", "no_extent": True, "NE": 0,
                                          "SE": 0, "SW": 0, "NW": 0, "threshold_kt": 34}}]
    return product


class MapDocument(HTMLParser):
    def __init__(self, payload):
        super().__init__()
        self.scripts = []
        self.script_id = None
        self.json_text = ""
        self.external = []
        self.feed(payload.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append(attrs)
            self.script_id = attrs.get("id")
        if tag in ("script", "link", "img") and (attrs.get("src") or attrs.get("href")):
            self.external.append(attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self.script_id = None

    def handle_data(self, text):
        if self.script_id == "track-data":
            self.json_text += text


def test_html_offline_provenance_and_no_script_injection(advisory):
    advisory["name"] = '</script><script>alert("test")</script>@@MAP_JS@@'
    original = copy.deepcopy(advisory)
    output = export_track_map(advisory)
    document = MapDocument(output)
    assert len(document.scripts) == 4
    assert not document.external
    decoded = json.loads(document.json_text)
    assert decoded == json.loads(export_geojson(advisory))
    assert decoded["features"][0]["properties"]["name"] == advisory["name"]
    assert decoded["features"][0]["properties"]["wind_kt"] == 0
    assert b'fetch(' not in output
    assert advisory == original


def test_svg_preserves_dateline_and_null_extent_metadata(advisory):
    output = export_track_map(advisory, "svg", title="Test <map>")
    root = ElementTree.fromstring(output)
    ns = {"s": "http://www.w3.org/2000/svg"}
    assert root.find("s:title", ns).text == "Test <map>"
    metadata = json.loads(root.find(".//s:metadata", ns).text)
    features = metadata["geojson"]["features"]
    assert next(f for f in features if f["properties"].get("kind") == "forecast_track")["geometry"]["type"] == "MultiLineString"
    assert features[-1]["geometry"] is None and features[-1]["properties"]["no_extent"]
    assert "forecast" in output.decode() and "Equirectangular" in output.decode()


@pytest.mark.parametrize("coordinates", [[181, 20], [10, 91], [float("nan"), 20], [True, 20]])
def test_invalid_geojson_leaves_output_untouched(tmp_path, coordinates):
    data = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
            "geometry": {"type": "Point", "coordinates": coordinates}}]}
    output = tmp_path / "map.html"
    output.write_text("previous output")
    with pytest.raises(ValueError):
        write_track_map(data, output)
    assert output.read_text() == "previous output"


def test_geojson_cli_and_missing_archive(tmp_path, advisory):
    geojson = tmp_path / "track.geojson"
    geojson.write_bytes(export_geojson(advisory))
    output = tmp_path / "track.svg"
    main(["--geojson", str(geojson), "--output", str(output)])
    ElementTree.fromstring(output.read_bytes())
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(SystemExit):
        main(["--archive", str(missing), "--output", str(output)])
    assert not missing.exists()


def test_archive_cli_selects_exact_revision(tmp_path, advisory):
    archive = Archive(tmp_path / "advisories.sqlite3")
    first = archive.save(advisory, {"wmo-advisory.json": b'{}'})
    changed = copy.deepcopy(advisory)
    changed["points"][0]["wind_kt"] = 50
    archive.save(changed, {"wmo-advisory.json": b'{}'})
    output = tmp_path / "archive.html"
    main(["--archive", str(archive.path), "--version", first, "--output", str(output)])
    data = json.loads(MapDocument(output.read_bytes()).json_text)
    assert data["features"][0]["properties"]["version"] == first
    assert data["features"][0]["properties"]["wind_kt"] == 0

# Purpose: artifact semantics, offline packaging, hostile text and exact replay regression checks.
# Upstream: track_map.py and Archive, which generate/preserve advisory snapshots.
# Environment: pytest, Python 3.11+. Generated: 2026-10-09 America/New_York.
# Change record: new file, lines 1-120; finalized 2026-10-10 America/New_York.
