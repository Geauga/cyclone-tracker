# Source inventory and integration boundaries

Investigated on 2026-09-28; implementation verification continued on 2026-09-29.

## Official track source

[WMO SWIC](https://severeweather.wmo.int/) publishes a browser application. Its public js/tropical-cyclone1.js references the active index at https://severeweather.wmo.int/json/tc_inforce.json and per-system documents under https://severeweather.wmo.int/json/tc_<sysid>.json. This is an observed website interface, not a documented stability or availability contract.

The [WMO source policy](https://severeweather.wmo.int/tc.html) distinguishes RSMCs, TCWCs and NMHS issuers. The adapter filters the verified website issuer mapping to IDs 3–12: Honolulu, Miami, Tokyo, New Delhi, La Réunion, Melbourne (three IDs), Nadi and Wellington. It does not substitute JTWC, Hong Kong, Beijing, Philippines or Macao products for the selected source family.

The [RSMC directory](https://severeweather.wmo.int/rsmcs.html) and [TCWC directory](https://severeweather.wmo.int/tcwcs.html) identify the regional centres. Jakarta and Port Moresby are absent from the verified JSON issuer mapping. Their direct feeds are not integrated; no absence-of-storm claim is made for them.

Each source system ID and the WMO primary-group association are preserved. The first version does not infer cross-basin identities from matching names; an unlinked handoff may appear as separate records.

Missing source fields remain missing. Raw WMO JSON, the index snapshot, original point issuer fields, and wind-radius text are preserved. Forecast lead times are interpreted as hours/minutes relative to the latest analysis, following the site's data-loading logic. Explicit forecast times take precedence.

## Official overlay source

[NHC product examples](https://www.nhc.noaa.gov/productexamples/) identify https://www.nhc.noaa.gov/CurrentStorms.json as the live current-products summary. Its trackCone.zipFile and forecastWindRadiiGIS.zipFile fields link to official shapefile archives. See [NHC GIS products](https://www.nhc.noaa.gov/gis/).

Only allowlisted HTTPS hosts are fetched. Archives are read in memory without filesystem extraction. The adapter validates expected layers, geographic coordinates, advisory numbers, and storm IDs where supplied. Metadata must match the selected WMO analysis cycle; mismatched cycles are reported rather than attached. An intermediate NOAA advisory can temporarily leave the WMO-based view without an overlay.

The source projection may be NOAA's GCS_Sphere with radius 6,371,200 metres. Published longitude/latitude angles are retained without claiming a datum transformation. The exact source WKT and handling note are exported. This distinction matters for uses demanding surveyed positional precision.

Explicit all-zero quadrant radii are valid no-area records, not missing fields or parser failures. Original files are retained even if parsing fails. Malformed nonzero polygons are rejected with diagnostics rather than silently repaired. Source ring-orientation warnings remain in the logs.

Non-NOAA official cone and polygon-wind feeds are not integrated. Published WMO wind-radius text remains inspectable. Supporting a centre's tracks does not imply support for every product from that centre.

## Local map assets

Leaflet 1.9.4 is bundled with its upstream license in src/cyclone_monitor/static/vendor/. Assets came from the fixed-version package distribution.

The basemap derives from [Natural Earth 110m countries](https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/), a public-domain dataset. The examples/build_basemap.py script converts its official archive to bundled GeoJSON. No external tile server is used.

## Operational limits

Five-minute polling checks availability; it does not change publication frequency. Conditional HTTP requests reuse unchanged products. HTTP 429/503 retry delays are honored. Schema changes and retrieval failures are visible and do not erase the archive.

There is no claim of complete global coverage, continuous collection while closed, or complete recovery of advisories issued between polls. Those require additional integrations and a different collection lifecycle.
