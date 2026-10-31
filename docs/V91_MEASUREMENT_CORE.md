# V91 Measurement Core – manual deployment guide

## Scope

This is a read-only measurement prototype. It records real local CPU/memory/disk readings when the optional `psutil` package is installed, and disk capacity through Python's standard library. Missing sources are represented as `UNKNOWN`. Energy, water, emissions and material quantities are not estimated: they remain UNKNOWN until physical meters or verified activity data are connected.

The JSONL ledger is hash-chained and fsynced. This detects accidental or deliberate modification when the chain is re-verified, but it is NOT WORM storage, a digital signature, trusted timestamping, or proof that a sensor reading is true. A local administrator can still replace both the ledger and its hashes. The lock is a simple exclusive lock file; if a process crashes, a stale lock may require manual inspection.

No network access, shell execution, Docker control, automatic scaling, shutdown, or configuration changes are performed.

## Install

Python 3.10+ is recommended. From the repository root:

```bash
python -m pip install psutil pytest
```

On Windows, use `py -m pip install psutil pytest` if `python` is not available.

## One manual measurement

```bash
python controller/measurement_core.py --ledger runtime/v91-measurements.jsonl --root .
```

The command prints the snapshot and appends one record. Without psutil, CPU, memory and disk I/O remain UNKNOWN; disk capacity can still be measured.

## Verify the ledger

```bash
python controller/measurement_core.py --verify-only --ledger runtime/v91-measurements.jsonl
```

Expected results: `EMPTY_LEDGER` if no records exist, or `CHAIN_VALID` with an event count. A verification result does not mean the measurements themselves are physically accurate.

## Tests

```bash
python -m pytest tests/ -q
python -m py_compile controller/metrics.py controller/measurement_core.py
```

## Status vocabulary

- UNKNOWN: no usable source or no sample.
- DATA_AVAILABLE: a value was collected from the named source.
- INVALID: a value failed validation; it must not be used.
- CHAIN_VALID: the local hash chain verifies.
- EMPTY_LEDGER: no records exist; this is not a measurement pass.
- FAILED_CLOSED: verification or collection could not safely complete.

## Next stages (not implemented here)

1. Add sensor-specific adapters only after the exact device/API and units are known.
2. Add authenticated remote anchoring if stronger audit evidence is required.
3. Add calibrated energy/water meters before reporting ecological savings.
4. Add retention, backup and recovery tests.
5. Keep all actions separate from observation and require explicit human authorization.
