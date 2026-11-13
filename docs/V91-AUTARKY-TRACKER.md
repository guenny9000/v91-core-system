# V91 Local Autarky & Resilience Tracker (Issue #83)

**Status: PHASE 2 WIRED TO THE MEASUREMENT LEDGER (CI-TESTED). STILL LOCAL-ONLY: NO LIVE SOLAR/GRID METER IS CONNECTED, SO ENERGY AUTARKY IS UNKNOWN UNTIL REAL METER DATA EXISTS IN THE LEDGER (WIRING != MEASURED VALUES).**

## What it does

- `EnergyAutarky`: self-sufficiency share from measured solar/grid intervals. Intervals with missing values are UNKNOWN and excluded — never interpolated. No data → status UNKNOWN, never HEALTHY.
- `RegionalLoopIndicator`: share of locally consumed units that were locally produced, from a local JSON config. Missing/invalid config → UNKNOWN.
- `BiodiversityLog`: optional observation diary, SHA-256 hash-chained JSONL, counting only. Tampering breaks `verify_chain()`; corrupt lines fail closed.

## Phase 2 wiring (this change)

- `controller/autarky_report.py`: `load_measurement_records()` verifies the full hash chain of the real measurement ledger (`controller/measurement_core.py`, default `runtime/v91-measurements.jsonl`) BEFORE reading, fail-closed on corruption; `build_report()` combines ledger state, `EnergyAutarky`, optional `RegionalLoopIndicator` and `BiodiversityLog`.
- CLI: `python -m controller.autarky_report --ledger runtime/v91-measurements.jsonl [--regional-config ...] [--biodiversity-log ...]` (exit 2 = FAILED_CLOSED).
- `main.py`: opt-in `--autarky-ledger` (+ optional `--autarky-regional-config`, `--autarky-biodiversity-log`). The report is attached to the cycle result after each run. A broken ledger is reported as `autarky.status=ERROR` in the output — visible, never silent, and it does not kill the measurement cycle.
- Honest data rule: solar_w/grid_w count only when the ledger entry says `DATA_AVAILABLE` with a non-negative number. Today the measurement core records no physical energy meter, so the honest expectation is `UNKNOWN` until a real meter writes into the ledger.

## Honest limits

- Local view only. No network calls, no external systems, no market or policy effects.
- WIRING != MEASURED VALUES: the wiring is tested; the solar/grid values themselves are UNKNOWN until a physical meter or trusted accounting feeds the ledger.
- A metric is a measurement, not an achievement: nothing is „purified" or „liberated" by computing it.
