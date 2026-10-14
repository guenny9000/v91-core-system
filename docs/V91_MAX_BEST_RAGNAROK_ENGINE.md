# MAX BEST RAGNARÖK proposal engine

## What it does

`ragnarok/engine.py` provides a pure, side-effect-free planner for caller-supplied inventory records. It prioritizes evidence collection, separates evidence from authorization, requires reversibility and measured baselines, and proposes an isolated test as the strongest next step. It never executes a proposed action.

## What it does not do

- It does not scan the machine or the internet.
- It does not connect to Gemini, Copilot, local models, operating systems, or cloud services.
- It does not schedule itself or run continuously.
- It does not execute shell commands, modify services, change permissions, or deploy changes.
- It cannot verify that supplied evidence is true; it labels and reasons over the input it receives.

## Input contract

Pass a list of objects with a human-readable `name`, an `evidence` list, and—where applicable—`authorized`, `reversible`, `baseline`, and `measured_benefit` fields. Missing evidence remains unknown. `authorized` must be explicitly `true` for the planner to proceed beyond recommendation-only. Even fully populated records produce only an isolated-test proposal, never live execution.

## Verification

`tests/test_ragnarok_engine.py` checks empty input, missing evidence, authorization separation, irreversible changes, missing baselines, proposal-only behavior, and invalid input. A passing test proves these tested code paths only; it does not prove any external integration or real-world benefit.
