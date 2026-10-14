# V91 SEO/SEQ-145 — Addendum: Two-Model Local Evidence

**Classification:** OPERATOR-SUPPLIED OUTPUT; NOT INDEPENDENTLY RE-RUN BY THIS REVIEWER  
**Date reported:** 2026-10-14  
**Related PR at time of review:** [#5](https://github.com/guenny9000/v91-core-system/pull/5)  
**Related commit at time of review:** `2bae946c761601df1d435238d93e44e4cbbadb0a`

## 1. Reports received

Two independent model sessions reportedly queried the same Windows host and ran local tests.

### Model 1 (reported)
- CPU: AMD Ryzen 9 9900X, 12 cores / 24 threads
- CPU load: 29%
- GPU: NVIDIA GeForce RTX 5080; driver 616.56
- VRAM: 16,303 MB total; 4,344 MB free; 11,634 MB used
- GPU utilization: 3%; temperature: 43 °C
- RAM: 63,090.72 MB total; 32,437.38 MB available; reported load 48%
- `test_v91_local.py`: reported PASSED
- SHA-256 expected tail: `ecb208e383054284b7e0194be8288cfdcaa185622faf6c8eb14c3db686e4a5c8`

### Model 2 (reported)
- CPU: AMD Ryzen 9 9900X, 12 cores / 24 logical threads
- CPU load: 14.89%, sampled via Windows `GetSystemTimes`
- GPU: NVIDIA GeForce RTX 5080; driver 616.56
- VRAM: 16,303 MB total; 4,309 MB free; 11,669 MB used
- GPU utilization: 2%; temperature: 47 °C
- RAM: 63,090.72 MB total; 30,404.21 MB available; reported load 51%
- `python -m unittest discover -s . -p "test*.py"`: reported 3 tests passed
- Same expected SHA-256 tail as Model 1
- Reported ledger file readable and policy JSON normalized to UTF-8

## 2. Interpretation and consistency checks

The CPU readings differ (29% vs 14.89%), as do GPU temperature, utilization, and available RAM. These may be valid snapshots taken at different times or with different sampling methods; they should not be averaged into a single “true” value. Store timestamp, command, host, and raw output for each sample.

The VRAM arithmetic does not reconcile exactly in either report:
- Model 1: 4,344 + 11,634 = 15,978 MB, 325 MB below the reported 16,303 MB total.
- Model 2: 4,309 + 11,669 = 15,978 MB, also 325 MB below the reported total.

Preserve the raw `nvidia-smi` output and investigate whether this is an output transcription, unit/reporting, or collection issue. Do not silently “correct” it.

The RAM load percentages are rounded reports and should be recomputed from the raw values with a documented formula. The CPU snapshots are not a sustained benchmark. Low GPU utilization is only a snapshot, not evidence of model throughput or full GPU capability.

A repeated expected hash is not, by itself, proof of deterministic behavior. The test must recompute the value from the exact input/code, compare it with the expected value, and record exit code, stdout/stderr, and hashes of the tested files. A passing test suite proves only the assertions that were actually executed.

## 3. Evidence state

- Hardware identity and telemetry: **REPORTED / NOT INDEPENDENTLY RE-RUN HERE**
- Local test results: **REPORTED / NOT INDEPENDENTLY RE-RUN HERE**
- Ledger integrity: **REPORTED READABLE; FULL CHAIN/IMMUTABILITY NOT ESTABLISHED**
- Policy JSON encoding normalization: **REPORTED; semantic equivalence and policy safety not independently checked**
- GitHub CI: check the exact head SHA and workflow run before assigning VERIFIED to the current PR revision.
- Global merge: **UNKNOWN / NOT CONFIRMED**
- Production deployment: **UNKNOWN / NOT CLAIMED**

## 4. Next evidence capture

For each local run, preserve:
1. Exact commit SHA and clean/dirty Git status.
2. SHA-256 hashes of `v91_hardware_adapter.py`, `test_v91_local.py`, `v91_evidence_result.json`, and relevant policy/ledger files.
3. Raw CPU, RAM, and `nvidia-smi` output with UTC timestamp.
4. Exact test command, exit code, full test names/count, stdout/stderr.
5. The exact input and recomputed hash used for the determinism check.
6. A ledger verification result that checks sequence continuity and every previous-hash/current-hash link, if those fields are part of the actual ledger format.

Avoid placing secrets, credentials, personal data, or private payloads in the report. Do not describe a local file as GitHub-linked evidence unless its contents or hash are actually committed and inspected.

**Core rule:** CLAIM ≠ EVIDENCE. A second model's matching report improves cross-checking but is not a substitute for reproducible execution evidence.


## 5. Follow-up evidence reported on 2026-10-14

The operator supplied a further report claiming that `nvidia-smi -q -d MEMORY` showed 16,303 MiB total, 326 MiB reserved, 5,218 MiB used, and 10,760 MiB free. These numbers are internally close but sum to 16,304 MiB, one MiB above the reported total. The reserved-memory explanation is plausible, but the raw command output has not been independently captured by this reviewer; retain it as **OPERATOR-SUPPLIED** until the original output is committed or otherwise made inspectable. Do not state that the arithmetic is exact.

The operator also supplied a local Git test report showing 10 tests passed on a local `pr-5` checkout, plus SHA-256 values for three local audit files. These are reported local results, not independently reproduced here. A file hash identifies those exact file bytes only when the file itself is available for re-hashing; it does not establish WORM storage or ledger immutability.

### GitHub Actions — directly queried

For commit `2d121c03df13d7dfa440b844f67d7fa8a9a33c72`, GitHub's workflow-run API returned:
- Workflow: `v91 Audit Pipeline`
- Run ID: `38504159083` (run number 60)
- Status/conclusion: `completed / success`
- Job: `audit-checks` — completed successfully
- Steps reported successful: checkout, Python setup, dependency installation, unit tests, hash verification, and artifact upload

Run link: https://github.com/guenny9000/v91-core-system/actions/runs/38504159083

This verifies that GitHub reports a successful workflow for that exact commit. It does not establish that all security properties are proven, that local hardware values were tested by CI, that the PR is merged, or that anything is deployed to production.

### PR relationship — directly queried

At the latest check, PR #4 and PR #5 were both **open, draft, and unmerged**. Both reported `mergeable: true`. PR #5's changed-file list includes the six shared cooperative-handshake/workflow files plus the two report files. The local claim that PR #5 is a linear superset of PR #4 is consistent with the reported branch history, but the repository's merge state remains unchanged until a merge actually occurs.

Recommended safe sequence: finish review of PR #4, merge it only through the repository's required approval process, then refresh/rebase PR #5 against the updated `main`, rerun checks on the new exact head SHA, and review the reduced documentation-only diff. Do not treat CI success alone as merge authorization.

**Updated state:** exact-commit CI = **VERIFIED FROM GITHUB API**; local measurements/tests = **OPERATOR-REPORTED**; PR merge = **NOT MERGED**; global merge = **UNKNOWN**; production = **NOT ESTABLISHED**.
