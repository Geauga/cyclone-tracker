# generate_track_map.py
# User request: demonstrate generating shareable cyclone track maps through the Python API.
import argparse
from pathlib import Path

from cyclone_monitor import Archive, write_track_map


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="Existing advisories.sqlite3")
    parser.add_argument("--version", help="Exact advisory ID; otherwise newest archived snapshot")
    parser.add_argument("--output", type=Path, default=Path("exports"))
    args = parser.parse_args()
    if not args.archive.is_file():
        parser.error("Archive does not exist")
    archive = Archive(args.archive)
    versions = archive.versions()
    if not versions:
        parser.error("Archive contains no advisories")
    product = archive.get(args.version or versions[0]["version"])
    for suffix in ("html", "svg"):
        output = args.output / (product["key"] + "-" + product["version"] + "." + suffix)
        print("Generated:", write_track_map(product, output).resolve())


if __name__ == "__main__":
    main()
# Purpose: complete independent map-generation example. Upstream: previously collected Archive snapshot.
# Upstream purpose: retain official observations, forecasts and provenance. Environment: installed package.
# Generated: 2026-10-09 America/New_York. No network or dashboard required.
# Change record: new file, lines 1-31; finalized 2026-10-10 America/New_York.
