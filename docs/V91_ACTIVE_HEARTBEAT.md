# V91 active heartbeat — scope and evidence

## Purpose
This workflow replaces passive-only documentation with a real, scheduled GitHub Actions check. It is configured to run every six hours (UTC) and can also be started manually. Each run executes the repository test suite and saves a timestamped JSON artifact containing the exact commit and run identity.

## Activation boundary
- The workflow is stored on the feature branch. Pushes to this named feature branch are configured to trigger a run for initial verification. The six-hour schedule is not activated until the workflow is merged into the repository's default branch.
- A manual run may be started against a branch if repository permissions and GitHub Actions settings allow it.
- Creating this file does not itself start a run. A run ID and result are required before claiming a heartbeat has executed.
- This workflow monitors only the repository test suite on a GitHub-hosted runner. It does not monitor the user's PC, local V91 processes, other models, external services, world events, or news feeds.
- It does not deploy, modify permissions, or perform external actions. GitHub's scheduled workflows can be delayed and are not a real-time or guaranteed-uptime monitoring service.

## Evidence states
- DOCUMENTED: workflow and this scope note exist in the branch.
- IMPLEMENTED: GitHub Actions can load the workflow after it is present in an eligible branch.
- VERIFIED: only after a specific run completes and its logs/artifact are inspected.
- PRODUCTIVE: not claimed without measured baseline and demonstrated operational value.

## Safe follow-up
1. Review the workflow diff and confirm GitHub Actions are enabled.
2. Trigger a manual run on this branch if available.
3. Inspect the test result and JSON artifact.
4. Merge only after review and successful checks if the repository owner chooses.
5. After merge, confirm that scheduled runs actually occur.
6. Add separate, explicitly scoped news-source checks only after selecting reliable public feeds and defining how failures, stale items, and source attribution will be recorded.

## Rollback
Remove `.github/workflows/v91-active-heartbeat.yml` and `docs/V91_ACTIVE_HEARTBEAT.md` in a reviewed follow-up commit, or revert the commit that introduced them. Existing code and data are not changed by the workflow.
