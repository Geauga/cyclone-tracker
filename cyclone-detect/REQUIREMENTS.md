# Cyclone Detect

## Purpose

Detect tropical cyclone candidates in gridded weather or climate-model output and link candidates into tracks over time.

## Scope

1: Read selected model fields with explicit dimensions, coordinates, units, grid definition, and time/calendar metadata.

2: Apply a scientifically specified detection method with configurable, documented criteria and inspectable intermediate results.

3: Link detections across time using explicit displacement, gap, and conflict-handling rules.

4: Export candidate diagnostics and resulting tracks with algorithm settings and input provenance.

## Boundaries

Live official-storm monitoring belongs to `cyclone-monitor`. Historical best-track analysis belongs to `cyclone-history`. Detected candidates must not automatically be labeled confirmed tropical cyclones. Validation and classification criteria require agreement before implementation.

## Decisions required

1: Target model or dataset, available variables and vertical levels, grid geometry, and spatial and temporal resolution.

2: Scientific detection method and required validation reference.

3: Input size, computational environment, and memory constraints.

4: Track linking criteria, minimum persistence, and output formats.

## Proposed acceptance criteria

Check detection and linking against controlled synthetic fields and an agreed reference case. Verify time gaps, longitude boundaries, competing nearby candidates, missing fields, and units. Keep detection diagnostics and linking decisions available for inspection. Quantitative skill thresholds will be specified with the validation dataset.

## Status

Specification scaffold only; no runnable package or detection algorithm yet.
