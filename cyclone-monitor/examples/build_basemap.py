# build_basemap.py
# User request: keep archived storm maps usable locally without a tile service.
import argparse
import io
import json
import zipfile
from pathlib import Path

import shapefile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.source_zip) as z:
        base = "ne_110m_admin_0_countries"
        reader = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")),
                                  shx=io.BytesIO(z.read(base + ".shx")),
                                  dbf=io.BytesIO(z.read(base + ".dbf")), encoding="utf-8")
        features = [{"type": "Feature", "geometry": r.shape.__geo_interface__,
                     "properties": {"name": r.record.as_dict()["ADMIN"]}} for r in reader.iterShapeRecords()]
    args.output.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                     ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Saved", len(features), "Natural Earth countries to", args.output)


if __name__ == "__main__":
    main()
# Purpose: bundle public-domain Natural Earth country boundaries as GeoJSON.
# Upstream: official Natural Earth 110m admin-0 countries ZIP; purpose: cartographic context.
# Environment: Python 3.11+, pyshp. Generated: 2026-09-28 America/New_York.
# Change record: new implementation, lines 1-33; finalized 2026-09-29 America/New_York.
