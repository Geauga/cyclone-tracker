# test_monitor.py
# User request: verify official-data semantics, advisory persistence, exports, and session polling.
import copy
import csv
import io
import json
import zipfile

import netCDF4
import pytest
import shapefile
from shapely.geometry import shape

from cyclone_monitor import Archive, export_csv, export_geojson, export_netcdf
from cyclone_monitor.provider import OfficialProvider, SWIC, parse_swic, parse_gis, split_dateline, iso
from cyclone_monitor.server import Monitor, create_app


@pytest.fixture
def source():
    # Explicit synthetic fixture: schema checks, never displayed as real cyclone data.
    return {"sys_id": 9999001, "gts": None, "track": [
        {"center_id": "4", "analysis_time": "2026-09-28 15:00:00", "tc_name": "TEST ONLY",
         "tc_id": "AL992026", "lat": "20", "lng": "179", "max_wind_speed": "0",
         "pressure": None, "gust": None, "wind_radii": None, "intensity": "Test"}],
        "forecast": [{"time_interval": "0930", "lat": "21", "lng": "-179",
                      "max_wind_speed": "35", "pressure": "1000", "gust": None}]}


@pytest.fixture
def product(source):
    return parse_swic(source, SWIC + "tc_9999001.json", "9999001")


def test_times_missing_zero_and_source(product):
    assert product["points"][0]["wind_kt"] == 0
    assert product["points"][0]["pressure_hpa"] is None
    assert product["points"][1]["valid_time"] == "2026-09-29T00:30:00Z"
    assert product["issue_time"] is None
    assert product["issuer"] == "RSMC Miami"
    assert product["points"][0]["wind_averaging_minutes"] is None


@pytest.mark.parametrize("field,value", [("lat", "NaN"), ("lat", 91), ("lng", None)])
def test_invalid_coordinates_rejected(source, field, value):
    source["track"][0][field] = value
    with pytest.raises(ValueError):
        parse_swic(source, SWIC + "fixture", "fixture")


def test_non_rsmc_rejected(source):
    source["track"][0]["center_id"] = "13"
    with pytest.raises(ValueError, match="RSMC"):
        parse_swic(source, SWIC + "fixture", "fixture")


def test_bad_forecast_time_fails_explicitly(source):
    source["forecast"][0]["time_interval"] = "1290"
    with pytest.raises(ValueError):
        parse_swic(source, SWIC + "fixture", "fixture")


def test_archive_dedup_revision_restart_and_originals(tmp_path, source, product):
    archive = Archive(tmp_path / "data.sqlite")
    sources = {"wmo-advisory.json": json.dumps(source).encode(), "wmo-index.json": b'{"update":"first"}'}
    first = archive.save(product, sources)
    sources["wmo-index.json"] = b'{"update":"unrelated storm changed"}'
    assert archive.save(product, sources) == first
    revision = copy.deepcopy(product)
    revision["points"][0]["wind_kt"] = 40
    source["track"][0]["max_wind_speed"] = "40"
    sources["wmo-advisory.json"] = json.dumps(source).encode()
    second = archive.save(revision, sources)
    assert second != first
    reopened = Archive(tmp_path / "data.sqlite")
    assert len(reopened.versions(product["key"])) == 2
    assert reopened.latest()[0]["version"] == second
    assert reopened.get(first)["points"][0]["wind_kt"] == 0
    with zipfile.ZipFile(io.BytesIO(reopened.raw(second))) as z:
        assert json.loads(z.read("wmo-advisory.json")) == source


def test_dateline_line_and_polygon():
    line = split_dateline({"type": "LineString", "coordinates": [[179, 10], [-179, 11]]})
    assert line["type"] == "MultiLineString"
    assert shape(line).length < 4
    polygon = split_dateline({"type": "Polygon", "coordinates": [[[179, 10], [-179, 10], [-179, 12], [179, 12], [179, 10]]]})
    assert polygon["type"] == "MultiPolygon"
    assert shape(polygon).area == pytest.approx(4)


def test_exports_roundtrip(product):
    product["version"] = "test"
    rows = list(csv.DictReader(io.StringIO(export_csv(product).decode("utf-8-sig"))))
    assert rows[0]["wind_kt"] == "0.0"
    assert rows[0]["pressure_hpa"] == ""
    geo = json.loads(export_geojson(product))
    line = [f for f in geo["features"] if f["properties"]["kind"] == "forecast_track"][0]
    assert line["geometry"]["type"] == "MultiLineString"
    data = export_netcdf(product)
    assert data.startswith(b"\x89HDF")
    with netCDF4.Dataset("memory.nc", memory=data) as ds:
        assert len(ds.dimensions["record"]) == 2
        assert ds["wind_kt"][0] == 0
        assert bool(ds["pressure_hpa"][:].mask[0])
        assert ds["kind"][1] == "forecast"
        assert ds["valid_time"][1] > ds["valid_time"][0]
        assert ds.issuer == "RSMC Miami"


def test_csv_source_text_formula_is_escaped(product):
    product["name"] = "=1+1"
    row = next(csv.DictReader(io.StringIO(export_csv(product).decode("utf-8-sig"))))
    assert row["name"] == "'=1+1"


def test_session_lifecycle_and_no_background(tmp_path):
    now = [100.0]
    m = Monitor(Archive(tmp_path / "a.sqlite"), clock=lambda: now[0])
    assert not m.due()
    m.heartbeat("first")
    assert m.due()
    m.last_attempt = now[0]
    now[0] += 299
    m.heartbeat("first")
    assert not m.due()
    now[0] += 1
    assert m.due()
    m.heartbeat("second")
    m.close_session("first")
    assert m.active()
    m.close_session("second")
    assert not m.due()
    m.heartbeat("crashed-tab")
    now[0] += 46
    assert not m.due()


def test_failed_refresh_retains_previous_state(tmp_path):
    class Failed:
        def collect(self):
            raise RuntimeError("provider offline")
    archive = Archive(tmp_path / "a.sqlite")
    archive.state("last_refresh", {"expected_keys": ["known"], "index_count": 1})
    monitor = Monitor(archive, Failed())
    monitor._refresh()
    result = monitor.snapshot()
    assert result["index_count"] == 1
    assert "provider offline" in result["errors"][0]
    assert result["missing_keys"] == ["known"]


def test_empty_index_differs_from_failure():
    class Empty:
        def get(self, url):
            if url.endswith("tc_inforce.json"):
                return b'{"inforce":[],"update":"2026-09-28 15:00:00"}'
            return b'{"activeStorms":[]}'
    result = OfficialProvider(Empty()).collect()
    assert result["index_count"] == 0 and result["products"] == [] and result["errors"] == []


def test_malformed_index_is_not_empty():
    class Bad:
        def get(self, url):
            return b'{"unexpected":[]}'
    with pytest.raises(ValueError, match="index"):
        OfficialProvider(Bad()).collect()


def test_api_export_and_local_boundary(tmp_path, product, source):
    app = create_app(tmp_path, start_worker=False)
    archive = app.extensions["monitor"].archive
    version = archive.save(product, {"wmo-advisory.json": json.dumps(source).encode()})
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/state").json["storms"][0]["name"] == "TEST ONLY"
    for kind in ("csv", "geojson", "nc", "raw"):
        response = client.get("/api/export/" + version + "/" + kind)
        assert response.status_code == 200 and len(response.data) > 0
    assert client.get("/api/advisory/unknown").status_code == 404
    assert client.get("/api/state", headers={"Host": "external.example"}).status_code == 403
    assert client.post("/api/settings", json={"interval": 60}, headers={"Origin": "https://external.example"}).status_code == 403
    assert client.post("/api/settings", json={"interval": -1}).status_code == 400
    assert client.post("/api/settings", json={"interval": 900}).json == {"interval": 900}


def gis_fixture(zero=False, advisory_number="1"):
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    for field in ("NE", "SE", "SW", "NW", "RADII"):
        writer.field(field, "N")
    for field in ("STORMID", "ADVNUM", "VALIDTIME"):
        writer.field(field, "C", size=30)
    writer.poly([[[10,20],[10,21],[11,21],[11,20],[10,20]]])
    writer.record(*([0,0,0,0] if zero else [10,10,10,10]),34,"al992026",advisory_number,"2026092815")
    writer.close()
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        for ext, stream in (("shp",shp),("shx",shx),("dbf",dbf)):
            z.writestr("test_forecastradii."+ext, stream.getvalue())
        z.writestr("test_forecastradii.prj",'GEOGCS["GCS_Sphere",DATUM["D_Sphere",SPHEROID["Sphere",6371200.0,0.0]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]')
    return buf.getvalue()


@pytest.mark.parametrize("zero", [True,False])
def test_official_gis_spherical_crs_and_zero_extent(product, zero):
    meta={"advNum":"001","issuance":product["analysis_time"],"zipFile":"https://www.nhc.noaa.gov/test.zip"}
    features=parse_gis(gis_fixture(zero), "wind", meta, product)
    assert features[0]["properties"]["no_extent"] is zero
    assert (features[0]["geometry"] is None) is zero
    assert features[0]["properties"]["NE"] == (0 if zero else 10)
    assert "GCS_Sphere" in features[0]["properties"]["source_crs_wkt"]
    product["overlays"]=features
    with netCDF4.Dataset("overlay.nc", memory=export_netcdf(product)) as ds:
        roundtrip=json.loads(ds["overlay_geojson"][0])
        assert roundtrip["properties"]["no_extent"] is zero


def test_overlay_advisory_mismatch_rejected(product):
    meta={"advNum":"002","issuance":product["analysis_time"],"zipFile":"https://www.nhc.noaa.gov/test.zip"}
    with pytest.raises(ValueError, match="advisory number"):
        parse_gis(gis_fixture(), "wind", meta, product)


def test_explicit_timezone_is_converted():
    assert iso("2026-09-28T11:00:00-04:00") == "2026-09-28T15:00:00Z"

# Purpose: behavior tests with explicitly synthetic fixtures. Upstream: package requirements and modules.
# Environment: Python 3.11+, pytest. Generated: 2026-09-28 America/New_York.
# Change record: new implementation, lines 1-230; finalized 2026-09-29 America/New_York.
