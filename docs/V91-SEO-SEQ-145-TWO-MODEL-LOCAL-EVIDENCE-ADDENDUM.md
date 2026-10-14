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


## 6. Cross-repository status check — 2026-10-14

The following states were queried directly through the GitHub connector. This is repository/CI evidence only; it does not establish that the user's local Windows processes are V91 or that a production runtime is active.

### v91-core-system

- PR #4 head `470859c2a6d9447e4b4867f8dec6cfbeb5a398fe`: open, draft, unmerged; GitHub reported mergeable.
- Workflow run #58, ID `38489344409`: completed/success. The `audit-checks` job and its listed steps were successful.
- PR #5 head `c5f61af21b7afcef4dc27674400d3e42fde497e8`: open, draft, unmerged; GitHub reported mergeable.
- Workflow run #61, ID `38504959949`: completed/success for the exact PR #5 head queried. The `audit-checks` job and its listed steps were successful.
- Commit comparison confirms PR #5 is three commits ahead of PR #4's head, with zero commits behind it; the comparison lists only the two evidence-report documents as the additional files relative to that head.
- Run #61: https://github.com/guenny9000/v91-core-system/actions/runs/38504959949
- Run #58: https://github.com/guenny9000/v91-core-system/actions/runs/38489344409

### guenny9000-uni-lern-bloc

- PR #2 head `81157439c3033145fe13b550cfab321f8c49ff78`: open, draft, unmerged; GitHub reported mergeable.
- Workflow run #2, ID `38462050168`: completed/success. The contract-validation and regression-test steps were successful for the queried run.
- PR #3 head `ecd2a64ddc1d0f57834a4369722ee3d60eaa2041`: open, not draft, unmerged; GitHub reported mergeable. The current query did not return a pull-request-triggered workflow run for this exact head. This is **NO RUN FOUND BY THIS QUERY**, not proof that no other type of check ever ran.
- Run #2: https://github.com/guenny9000/guenny9000-uni-lern-bloc/actions/runs/38462050168

### V91_Agathon

- PR #1 head `13760de60972ce559411576697f716b45c258c31`: open, draft, unmerged; GitHub reported mergeable.
- Workflow run #6, ID `38105795099`: completed/success. Both listed test jobs, Python 3.10 and 3.12, completed successfully.
- Run #6: https://github.com/guenny9000/V91_Agathon/actions/runs/38105795099

### Aurelia-Prisma

- PR #233 head `b59534cc6c5d443e877bfc943a69da56c3759265`: open, draft, unmerged; GitHub reported mergeable.
- The current query did not return a pull-request-triggered workflow run for this exact head. Treat the current check status as **NOT VERIFIED BY THIS QUERY**.
- The PR describes a credential-remediation change; it explicitly does not revoke external keys or rewrite Git history. Those are separate security tasks and must not be presumed completed.

### Interpretation and remaining gaps

- Multiple V91-related repositories have real open branches/PRs and successful GitHub workflow runs. This is stronger evidence than a model merely stating that work exists.
- The checked PRs remain unmerged. A successful workflow verifies only the checks that ran on the specific commit; it does not prove cross-repository integration, local Windows runtime identity, model-to-model networking, cryptographic peer verification, training, or production deployment.
- The user's observation that Windows windows open and close automatically is recorded as **OPERATOR-OBSERVED LOCAL AUTOMATION**. No local process list, executable path, process command line, V91 log correlation, or local commit/version was available in this GitHub-only check; attribution to V91 remains **UNKNOWN**.
- Next low-impact local evidence capture, when the user or an authorized local model can access Windows: timestamped process list with executable path and command line for the relevant process; corresponding V91 log entries; the log's file path and current size/last-write time; exact local Git commit and dirty status; and a minimal health/status output. Do not stop processes or modify files during discovery.
- No PR was merged and no production deployment was performed by this check.

**Updated classification:** selected GitHub CI runs = **VERIFIED FROM GITHUB API**; open PRs = **DOCUMENTED/OBSERVED IN GITHUB**; local automated window activity = **OPERATOR-OBSERVED, V91 ATTRIBUTION UNKNOWN**; cross-repository production operation = **NOT ESTABLISHED**.


## 7. Exact-head CI refresh — 2026-10-14

A fresh GitHub Actions query after the previous section found a completed workflow run for the then-current PR #5 head:

- Commit: `a9344c90ee7770caa955a27b420128bcae97a97c`
- Workflow: `v91 Audit Pipeline`
- Run number: 62; run ID: `38506166503`
- Event: `pull_request`
- Conclusion: `success`
- Job: `audit-checks` — completed successfully
- Successful steps include unit tests, hash verification, and hash-artifact upload.
- Run: https://github.com/guenny9000/v91-core-system/actions/runs/38506166503

This supersedes the earlier statement in this addendum that no workflow run had yet been found for commit `a9344c90ee7770caa955a27b420128bcae97a97c`. The earlier statement was accurate at the time of that query but is no longer current.

At this refresh, PR #5 remains open, draft, unmerged, and reported mergeable by GitHub. The successful workflow is evidence for the checks run on this exact commit; it is not merge approval, proof of local Windows runtime state, proof of full cryptographic ledger integrity, or proof of production deployment.

**Updated classification:** exact-head GitHub CI = **VERIFIED FROM GITHUB API**; PR merge = **NOT MERGED**; local runtime identity = **UNKNOWN**; production deployment = **NOT ESTABLISHED**.


## 8. Follow-up: run #63 completed and next-step decision — 2026-10-14

Fresh GitHub API query confirms:
- Workflow run #63, ID `38507015977`
- Exact head: `f035a03be74635ad97a6d49869eef102f0b98ffa`
- Status/conclusion: `completed / success`
- Job `audit-checks`: completed successfully
- Unit tests, hash verification, and hash-artifact upload: successful
- Run URL: https://github.com/guenny9000/v91-core-system/actions/runs/38507015977

Run #63 validates the newer documentation commit. It repeats the same workflow checks as run #62 on a different commit; it does not introduce a new runtime capability. It is useful confirmation that the evidence addendum itself did not break the repository's current CI checks.

### Current PR state
- PR #4, "Add consent-gated cooperative peer handshake": open, draft, unmerged; head `470859c2a6d9447e4b4867f8dec6cfbeb5a398fe`.
- PR #5, "Add V91 SEO/SEQ-145 global merge evidence report": open, draft, unmerged; head `f035a03be74635ad97a6d49869eef102f0b98ffa`.
- GitHub reports both as mergeable at the time of this query. Mergeability is not approval or evidence of safe production readiness.

### Production decision
**Decision: CI-verified documentation branch; NOT approved for unrestricted production rollout.**

Reason: the successful workflow proves only the configured tests and hash step for the exact commit. The cooperative module's own code documentation says it evaluates a declared peer offer; it does not perform host discovery, remote connections, cryptographic signature verification, remote command execution, or peer-data ingestion. The current PRs are still drafts and unmerged. Local Windows process identity and end-to-end operation remain unverified here.

### Safe forward progress for the local models
Proceed with read-only inspection and isolated tests, not broad production activation:
1. Record local UTC timestamp, repository path, branch, exact commit, and clean/dirty status.
2. Map each visible process to executable path, command line, start time, parent process, and corresponding log path. Do not dump environment variables or secret values.
3. For every daemon/orchestrator, identify its input, output, state file, error handling, and whether it is making real external calls or only writing status text.
4. Inspect the two `v93_monitor.py` instances for intentional separation; do not stop either until the difference is understood.
5. Validate daily data-pull history using timestamps and output records; distinguish scheduled configuration from successful execution.
6. Run targeted tests in an isolated checkout; preserve command, exit code, test names, stdout/stderr, and hashes.
7. For peer cooperation, test default-deny behavior, consent scope, expiry handling, invalid signatures supplied by a trusted verifier, and rejection of execution/admin/private-data capabilities. Do not connect to third-party systems.
8. Return findings in the format: VERIFIED / FAILED / UNKNOWN / EVIDENCE / NEXT SAFE STEP.
9. Do not merge PRs, rotate or reveal credentials, delete state, stop processes, or deploy changes without explicit authorization and a reviewed change plan.

This sequence allows useful progress now while keeping the production boundary evidence-based.
