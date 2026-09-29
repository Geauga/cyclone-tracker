# live_check.py
# User request: verify real official feeds, archive, and all three export formats.
import argparse
import io
import json
import logging
from pathlib import Path

import netCDF4

from cyclone_monitor import Archive, OfficialProvider, export_csv, export_geojson, export_netcdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(args.data_dir / "live-check.log", encoding="utf-8")])
    result = OfficialProvider().collect()
    archive = Archive(args.data_dir / "advisories.sqlite3")
    report = []
    for product, raw in result["products"]:
        version = archive.save(product, raw)
        assert archive.save(product, raw) == version
        saved = archive.get(version)
        geojson = json.loads(export_geojson(saved))
        assert geojson["features"]
        assert export_csv(saved).decode("utf-8-sig").startswith("key,")
        with netCDF4.Dataset("roundtrip.nc", memory=export_netcdf(saved)) as ds:
            assert len(ds.dimensions["record"]) == len(saved["points"])
            assert ds.issuer == saved["issuer"]
            assert len(ds.dimensions["overlay"]) == len(saved["overlays"])
        report.append({"name": saved["name"], "issuer": saved["issuer"], "version": version,
                       "points": len(saved["points"]), "overlays": len(saved["overlays"]),
                       "overlay_status": saved["overlay_status"]})
        logging.info("Verified %s: %d points, %d overlays, all exports", saved["name"], len(saved["points"]), len(saved["overlays"]))
    state = {k: v for k, v in result.items() if k != "products"}
    archive.state("last_refresh", state)
    output = dict(state, verified=report)
    (args.data_dir / "live-check.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if result["index_count"] and not report:
        raise RuntimeError("Index lists storms, but no official advisories could be verified")


if __name__ == "__main__":
    main()
# Purpose: explicit one-shot live integration verification; not a background scheduler.
# Upstream: official provider and export modules. Environment: installed package, internet.
# Generated: 2026-09-28 America/New_York. Logs: selected data-dir/live-check.log.
# Change record: new implementation, lines 1-52; finalized 2026-09-29 America/New_York.
