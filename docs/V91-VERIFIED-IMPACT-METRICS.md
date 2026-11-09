# V91 Verified Impact Metrics

**Status: IMPLEMENTED IN SOURCE ON A REVIEW BRANCH; NOT DEPLOYED.**

## Purpose

Convert environmental and resource claims into comparable, location-bound measurements. The evaluator supports biodiversity, ecosystem restoration, peatlands, water, energy, materials, waste, emissions, and land use.

## Required reporting discipline

Every measurement records indicator, unit, location, reporting period, baseline, measured value, whether lower or higher values represent improvement, implementation status separately from evidence status, and source publishers/URLs.

The evaluator calculates absolute change and percentage improvement where mathematically defined. A zero baseline produces an UNKNOWN percentage rather than division by zero. Negative values, non-finite values, naive timestamps, invalid domains, and non-HTTPS source URLs are rejected.

## Evidence grades

- UNKNOWN: no source supplied, or no valid verification basis.
- DOCUMENTED: one or more source records supplied.
- CORROBORATED: at least two distinct publishers supplied.
- INDEPENDENTLY_VERIFIED: caller supplies an explicit independent-verification assertion, at least two distinct publishers, and a named verification method. This is still a recorded assertion, not an independent verification performed by this code.

A hash, URL, or source count alone does not prove truth. Global impact status always remains UNKNOWN because local records cannot establish a global result.

## Run tests

    python -m unittest tests.test_impact_metrics -v

The module evaluates supplied data only. It does not ingest live feeds, fund or perform restoration, authorize interventions, or claim that any hectares have been restored.
