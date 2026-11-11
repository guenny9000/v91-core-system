# V91 Non-Military Use-Domain Policy Gate

**Status: IMPLEMENTED AS A PURE CLASSIFIER; NOT INTEGRATED INTO A RUNTIME ADMISSION PATH.**

## Purpose

Provide a deterministic, fail-closed classification primitive for V91 workflows.
Explicitly declared domains for weapons development, targeting, combat operations,
military surveillance, and arms production are blocked. Missing or unrecognized
domains return `REVIEW_REQUIRED`; UNKNOWN is never PASS.

Civilian sustainability, humanitarian, education, general research, and critical
supply protection are only marked `ALLOW_FOR_REVIEWED_WORKFLOW`. The result always
sets `execution_authorized=false`. A separate trusted authorization and admission
path is required before any work can run.

## Evidence and limitations

- The module evaluates an exact enum value. It does not infer intent from free text,
  inspect model prompts, classify images, or detect hidden military use.
- A supplied label is a claim, not evidence. Production integration must bind the
  classification to an authenticated task submitter and independently reviewed
  provenance. Relabeling or omission must not bypass admission.
- This module does not stop, isolate, modify, or access any external process,
  device, network, weapon system, military infrastructure, or third-party service.
- It does not change the scope of Core Issue #70, which explicitly concerns
  controlled shutdown of V91 systems owned or operated by the user.
- It does not claim that any real-world arms production, war activity, or harmful
  system has been isolated or reduced.

## Tests

The unit tests cover every allowed and restricted enum, malformed values, and the
invariant that classification never grants execution authority. Runtime integration,
signed provenance, independent review, and adversarial relabeling tests remain open.
