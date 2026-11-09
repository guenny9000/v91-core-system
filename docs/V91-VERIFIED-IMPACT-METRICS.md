# V91 Verified Impact Metrics

**Status: IMPLEMENTED IN SOURCE ON A REVIEW BRANCH; NOT DEPLOYED.**

## Purpose

Convert environmental and resource claims into comparable, location-bound measurements. The evaluator supports biodiversity, ecosystem restoration, peatlands, water, energy, materials, waste, emissions, and land use.

## Required reporting discipline

Every measurement records indicator, unit, location, reporting period, baseline, measured value, whether lower or higher values represent improvement, implementation status separately from evidence status, and source publishers/URLs.

The evaluator calculates absolute change and percentage improvement where mathematically defined. A zero baseline produces an UNKNOWN percentage rather than division by zero. Negative values, non-finite values, naive timestamps, invalid domains, and non-HTTPS source URLs are rejected.

## Evidence grades

The word "verified" in the project name does not mean this evaluator independently verifies source identity or truth. The module validates input structure and performs arithmetic on caller-supplied records only.

- UNKNOWN: no source record supplied.
- DOCUMENTED: one or more structurally valid source records supplied.
- CORROBORATED: reserved for a future verifier; this evaluator does not emit it. Two distinct publisher labels are not proof of independent publishers.
- INDEPENDENTLY_VERIFIED: not an output status. The boolean verification_claim_received only records that the caller asserted independent verification; the assertion is not checked by this code.

The independent_publishers field counts distinct caller-supplied publisher labels only. It does not verify publisher identity, independence, URL ownership, or truth. The evidence_status_counts object retains a CORROBORATED key for schema compatibility, but its value remains zero until a separate verification mechanism exists.

A hash, URL, source count, or caller flag alone does not prove truth. Global impact status always remains UNKNOWN because local records cannot establish a global result.

## Run tests

    python -m unittest tests.test_impact_metrics -v

The module evaluates supplied data only. It does not ingest live feeds, fund or perform restoration, authorize interventions, or claim that any hectares have been restored.
