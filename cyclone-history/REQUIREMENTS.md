# Cyclone History

## Purpose

Load historical tropical cyclone tracks, compare storms, and calculate reproducible research statistics.

## Scope

1: Load a selected historical track dataset while preserving dataset version, source identifiers, agency attribution, units, and missing values.

2: Select storms by supported identifiers, time ranges, or geographic criteria.

3: Compute the agreed statistics and export results with enough metadata to reproduce them.

4: Retain source-specific intensity conventions and make any normalization explicit.

## Boundaries

Live monitoring belongs to `cyclone-monitor`. Detection and temporal linking in gridded output belong to `cyclone-detect`.

## Decisions required

1: Initial historical dataset, geographic coverage, and date range.

2: Python library, command-line tool, application, or another deliverable.

3: Priority analyses, such as lifetime, motion, peak intensity, or track comparison, with explicit mathematical definitions.

4: Required input and output formats, expected data volume, and plotting needs.

## Proposed acceptance criteria

Use a small documented reference dataset to check ingestion, selection, and independently calculated statistics. Handle missing intensities, repeated storm names, irregular time intervals, and longitude discontinuities without silently discarding data. Record assumptions about units and temporal sampling.

## Status

Specification scaffold only; no runnable package or dataset integration yet.
