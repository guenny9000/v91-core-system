# V91 Local Autarky & Resilience Tracker (Issue #83)

**Status: IMPLEMENTED AS TESTED LOCAL METRICS; NOT CONNECTED TO LIVE MEASUREMENT SOURCES (SCRIPTED != INSTALLED).**

## What it does

- `EnergyAutarky`: self-sufficiency share from measured solar/grid intervals. Intervals with missing values are UNKNOWN and excluded — never interpolated. No data → status UNKNOWN, never HEALTHY.
- `RegionalLoopIndicator`: share of locally consumed units that were locally produced, from a local JSON config. Missing/invalid config → UNKNOWN.
- `BiodiversityLog`: optional observation diary, SHA-256 hash-chained JSONL, counting only. Tampering breaks `verify_chain()`; corrupt lines fail closed.

## Honest limits

- Local view only. No network calls, no external systems, no market or policy effects.
- Wiring to the real V91 measurement cycle (Last/Platte/Netzstrom) is the separate next step; until then the metrics consume supplied records only.
- A metric is a measurement, not an achievement: nothing is „purified" or „liberated" by computing it.