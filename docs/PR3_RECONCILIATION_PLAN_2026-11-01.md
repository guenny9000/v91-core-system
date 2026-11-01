# PR #3 Reconciliation Plan (risk-first)

Status: `BLOCKED` for direct merge.

Scope: [PR #3](https://github.com/guenny9000/v91-core-system/pull/3),
branch `fix/reality-first-safe-controller-2026-10-12`.

## Current evidence

- Divergence vs `main`: 57 commits ahead, 57 behind.
- Changed files: 33.
- Trial merge into current `main` conflicts in runtime/safety paths:
  - `.github/workflows/audit.yml`
  - `README.md`
  - `controller/anomaly.py`
  - `controller/controller.py`
  - `controller/real_metrics.py`
  - `docker-compose.yml`
  - `tests/test_controller_safety.py`
  - `tests/test_real_metrics.py`
  - `tests/test_v91_state_check.py`
  - `v91_state_check.py`

Gate record: [pr3_reconciliation_record.json](../examples/legacy_records/pr3_reconciliation_record.json)

## Why direct merge is blocked

The branch touches core runtime and safety files while being heavily diverged
from `main`; conflict resolution would be non-trivial and regression risk is
high without staged reconciliation and retesting.

## Controlled path forward

1. Create `reconcile/pr3` from current `main`.
2. Bring over small, testable feature groups (cherry-pick or manual port):
   - state validation and guideline hash updates
   - isolated metric improvements
   - documentation-only commits
3. After each feature group:
   - run full test suite
   - run CI pipeline
   - run `legacy-gate` on updated record
4. Keep high-risk runtime merges (`controller.py`, `docker-compose.yml`) for
   last, with explicit before/after behavior checks.
5. Close PR #3 only after all needed changes are integrated and verified.
