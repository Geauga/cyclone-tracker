# use_archive.py
# User request: use the package independently and export an archived advisory.
import argparse
from pathlib import Path

from cyclone_monitor import Archive, export_csv, export_geojson, export_netcdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="Existing advisories.sqlite3")
    parser.add_argument("--version", help="Version ID; defaults to the newest archived storm snapshot")
    parser.add_argument("--output", type=Path, default=Path("exports"))
    args = parser.parse_args()
    if not args.archive.is_file():
        parser.error("The archive file does not exist")
    archive = Archive(args.archive)
    records = archive.latest()
    if not records:
        parser.error("The archive has no advisories")
    product = archive.get(args.version or records[0]["version"])
    args.output.mkdir(parents=True, exist_ok=True)
    stem = product["key"] + "-" + product["version"]
    for suffix, exporter in (("csv", export_csv), ("geojson", export_geojson), ("nc", export_netcdf)):
        target = args.output / (stem + "." + suffix)
        target.write_bytes(exporter(product))
        print("Exported", target.resolve())


if __name__ == "__main__":
    main()
# Purpose: independent archive/export usage. Upstream: previously retrieved SQLite archive.
# Upstream purpose: preserve official advisory snapshots. Environment: installed package, local disk.
# Generated: 2026-09-29 America/New_York. No network requests.
# Change record: new implementation, lines 1-34; finalized 2026-09-29 America/New_York.
