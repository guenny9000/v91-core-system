# V91 Resource Savings & Real-World Impact Verification Protocol

**Status: PROPOSED SPECIFICATION — NOT IMPLEMENTED OR DEPLOYED BY THIS DOCUMENT.**

This protocol turns a reported opportunity into a bounded, auditable measurement project. It is designed for water, energy, compute, materials, waste, finance, time, and infrastructure. It does not authorize interventions, connect to sensors, prove source truth, or establish real-world impact by itself.

## 1. Non-negotiable distinctions

Keep these dimensions separate; never compress them into one green status:

| Dimension | Allowed states | Meaning |
|---|---|---|
| Opportunity | `IDENTIFIED`, `DUPLICATE`, `REJECTED` | A lead exists; no intervention or saving is implied. |
| Work | `NOT_STARTED`, `PLANNED`, `IN_PROGRESS`, `COMPLETED`, `ABORTED` | What the V91 team or external operator actually did. |
| Measurement | `MISSING`, `QUARANTINED`, `COMPARABLE`, `INCOMPARABLE` | Whether data passed quality and comparability checks. |
| Impact | `UNKNOWN`, `NO_IMPROVEMENT`, `GROSS_REDUCTION_OBSERVED`, `NET_SAVING_SUPPORTED`, `INDEPENDENTLY_VERIFIED`, `REJECTED` | Strength of the impact conclusion. |
| Authorization | `NOT_REQUIRED_READ_ONLY`, `PENDING`, `AUTHORIZED`, `DENIED`, `EXPIRED` | Whether a proposed action was explicitly permitted. |

A successful test, a merged PR, a hash, a sensor reading, a press release, or an operator assertion is not by itself evidence of a net saving. `UNKNOWN` never means zero, pass, or success. A hash establishes byte identity only relative to the bytes hashed; it does not establish truth, source identity, calibration, or immutability.

## 2. Lifecycle and fail-closed gates

1. **Capture lead:** preserve the original source, publication date, retrieval time, publisher, exact claim, location/system boundary, and source URL or archive reference. Do not silently rewrite the claim.
2. **Deduplicate:** normalize source URL, publisher, event/site, metric, and time window. Link duplicate reports to one canonical opportunity; do not count them as separate impact.
3. **Qualify:** identify the resource, owner/operator, measurable lever, baseline availability, likely intervention, and whether V91 has a lawful role. If no measurable lever or responsible operator exists, reject or park the lead.
4. **Design measurement before action:** pre-register metric, unit, boundary, baseline and after windows, sampling plan, inclusion/exclusion rules, expected confounders, uncertainty method, and stop criteria. Record the plan before observing results.
5. **Authorize and assess risk:** separate read-only analysis from external action. Record owner, approver, scope, expiry, rollback owner, safety constraints, and affected users. No third-party changes, physical repairs, migrations, service pauses, or purchases without the responsible operator's authorization.
6. **Observe baseline:** preserve raw observations and provenance. Missing, stale, implausible, uncalibrated, or incomplete measurements are quarantined, not imputed as zero.
7. **Implement intervention:** record exactly what changed, when, by whom, under which authorization, including downtime, side effects, and deviations from the pre-registered plan.
8. **Observe after-period:** use the same meter/source, unit, boundary, workload definition, sampling method, and comparable operating conditions wherever possible.
9. **Calculate net effect:** include direct implementation, migration, maintenance, training, disposal, replacement, financing, and other material lifecycle costs. Account for rebound, shifted consumption, displaced emissions, and service-quality changes.
10. **Review and publish:** retain raw data and calculation version; obtain independent review for material public claims. Publish limitations and adverse effects alongside positive results.
11. **Close or continue:** only promote the impact state when its explicit acceptance criteria are met. Otherwise retain UNKNOWN, QUARANTINED, INCOMPARABLE, or NO_IMPROVEMENT.

## 3. Record model: append-only events, not one mutable status blob

Use JSONL as an event stream. Each line is one immutable event with a unique `event_id`, a stable `case_id`, a UTC timestamp, schema version, actor, event type, and references to prior events. Corrections append a superseding event; never rewrite history. A hash chain can reveal modification of retained records, but JSONL plus hashes is not WORM. If retention must resist privileged deletion, use an independently administered immutable storage policy or external trusted anchor and test its retention controls.

Recommended event envelope:

```json
{
  "schema": "v91.resource-impact.event.v1",
  "event_id": "uuid",
  "case_id": "uuid",
  "sequence": 1,
  "recorded_at_utc": "2026-11-23T10:07:00Z",
  "event_type": "OPPORTUNITY_CAPTURED",
  "actor": {
    "type": "human | v91_component | external_operator",
    "id": "stable non-secret identifier"
  },
  "payload": {},
  "evidence_refs": [],
  "previous_event_sha256": null
}
```

Do not put credentials, personal data, precise household location, or raw sensitive telemetry into public records. Use access-controlled evidence references and data minimization.

### Required case facts

Every case must eventually capture:

- **Identity:** case ID, schema version, domain, site/system boundary, responsible operator, and non-sensitive location granularity.
- **Claim provenance:** original claim text, publisher, canonical URL/archive reference, publication time, retrieval time, and whether the claim is an announcement, estimate, pilot, measured result, or independently audited result.
- **V91 role:** exact deterministic analysis or recordkeeping task; code/revision and test evidence if applicable; explicit statement of what V91 did not do.
- **External action:** operator, authorization reference, intervention description, actual start/end times, deviations, and rollback/recovery evidence.
- **Measurement plan:** metric definition, unit, direction of improvement, meter/source IDs, calibration status, sample interval, timezone, boundary, baseline and after windows, workload/output denominator, exclusions, and predeclared analysis.
- **Results:** raw evidence references, SHA-256 digests, parser and calculation versions, sample counts, missing/rejected counts, uncertainty, gross change, lifecycle costs, net change, and caveats.
- **Review:** reviewer identity/role, independence declaration, review date, checks performed, unresolved objections, and decision.

### Measurement record

A baseline or after observation should contain at least:

```json
{
  "period_start_utc": "2026-11-01T00:00:00Z",
  "period_end_utc": "2026-11-08T00:00:00Z",
  "metric_id": "water_volume",
  "value": 1234.5,
  "unit": "m3",
  "source_id": "meter-opaque-id",
  "source_type": "direct_meter | calculated | estimate | manual",
  "calibration_ref": "evidence-reference-or-null",
  "sample_count": 672,
  "expected_sample_count": 672,
  "missing_count": 0,
  "raw_artifact_ref": "access-controlled-reference",
  "raw_artifact_sha256": "64 lowercase hex characters",
  "collection_method_version": "1.0.0"
}
```

This is a shape example, not a claim that any such data exists. The raw artifact must remain retrievable to an authorized reviewer. A digest without accessible evidence is insufficient for audit.

## 4. Comparability and causal attribution

A simple before/after difference is descriptive, not automatically causal. Before accepting an impact:

- Compare like with like: same physical/system boundary, metric definition, unit, meter, workload/output, operating hours, occupancy or service level, and sampling cadence.
- Account for seasonality, weather, production volume, occupancy, tariffs, scheduled maintenance, outages, equipment changes, and other material confounders.
- Prefer a pre-registered control site, matched comparison, interrupted time series, or difference-in-differences where feasible. Explain why the chosen design supports attribution.
- If no defensible counterfactual exists, report **observed change after intervention**, not **saving caused by intervention**.
- Preserve adverse outcomes: lower consumption caused by reduced service, unmet demand, reduced accessibility, deferred maintenance, or shifted burden is not automatically a benefit.
- State uncertainty and measurement error. Do not use a fixed sample count or arbitrary DQI threshold as a universal proof of validity; the required sample size and uncertainty method depend on the meter, variability, and decision stakes.

## 5. Gross and net calculation

For a metric where lower is better:

`gross_reduction = adjusted_baseline_use - adjusted_after_use`

For a metric where higher is better, define the direction explicitly; never infer it from the metric name.

`net_saving = gross_monetary_benefit - implementation_cost - migration_cost - operating_cost_delta - maintenance_cost_delta - financing_cost - disposal_cost - other_material_costs`

All terms must share currency, price basis, and time horizon. Record nominal/real currency, price year, tariff/source, discount rate if used, and whether taxes are included. Do not mix physical units and money in one total.

Report separately:
- physical reduction (e.g. m3, kWh, kg, CPU-hours);
- gross monetary benefit;
- one-time and recurring costs;
- net monetary saving over a stated horizon;
- uncertainty interval and sensitivity to assumptions;
- displaced or rebound consumption;
- service quality and human impact.

Annualization is allowed only with a stated method and representative observation period. Label extrapolations as estimates, not realized annual savings. Never sum overlapping site, portfolio, and national estimates.

## 6. Impact promotion criteria

- `IDENTIFIED`: source and specific opportunity captured.
- `GROSS_REDUCTION_OBSERVED`: comparable raw baseline and after data show a reduction beyond the declared measurement uncertainty; causal attribution is not yet established.
- `NET_SAVING_SUPPORTED`: gross effect, lifecycle costs, boundary, period, service quality, and confounders are documented; a defensible analysis supports a positive net effect.
- `INDEPENDENTLY_VERIFIED`: a suitably independent reviewer has inspected raw evidence, method, authorization, cost accounting, and limitations and signed/recorded the review. This status cannot be self-assigned by the calculation function.
- `NO_IMPROVEMENT` or `REJECTED`: evidence indicates no positive result, adverse effect, invalid measurement, or unsupported attribution.
- `UNKNOWN` / `QUARANTINED` / `INCOMPARABLE`: evidence is missing, weak, invalid, or non-comparable.

The evaluator may calculate candidate results. It must not autonomously emit `INDEPENDENTLY_VERIFIED` based on caller-supplied booleans, publisher counts, URLs, or hashes.

## 7. V91 versus operator responsibilities

| Activity | V91 may do when implemented and tested | External owner/operator required |
|---|---|---|
| News/opportunity triage | Parse, classify, deduplicate, preserve citations | Confirm site ownership, relevance, and permission |
| Meter analysis | Validate format, units, timestamps, gaps, and anomaly candidates | Supply authorized data and confirm meter context |
| Baseline/after comparison | Run versioned, reproducible calculations | Approve measurement design and intervention |
| Alerting | Produce explainable, bounded alerts for review | Investigate and decide operational response |
| Physical repair / equipment change | No physical action | Qualified operator performs and documents work |
| IT migration / service change | Prepare impact and rollback analysis | System owner approves and executes |
| Evidence integrity | Hash artifacts and verify local chains | Independent storage/admin controls and external review |
| Impact reporting | Generate status-separated reports | Responsible owner signs factual claims; independent reviewer verifies material claims |

## 8. Example application patterns

### Water loss

A continuous-flow anomaly is only a **lead**. Confirm meter identity, expected legitimate overnight demand, meter resolution, pressure/operating conditions, and known scheduled uses. A qualified operator investigates and repairs. Compare metered volume over comparable periods and normalize for occupancy, weather, and usage. Include repair cost, water treatment/pumping energy where measurable, and any service disruption. Report a repaired leak and a measured volume reduction separately from the amount causally attributed to the intervention.

### Public-sector IT expenditure

Keep announced/forecast savings, approved budgets, contracted savings, invoices paid, and audited realized savings as different measures. Capture licenses, compute, storage, network, power, staff, support, migration, training, dual-running, exit, and ongoing vendor costs. Normalize for workload and service levels; include outages, security, accessibility, and vendor lock-in. A forecast-versus-realized gap is a governance signal, not proof that a particular tool caused the gap.

## 9. Minimum test and review matrix

Before a calculation or workflow is accepted, test at least:

- missing, duplicate, out-of-order, timezone-naive, stale, and clock-skewed observations;
- unit mismatch, meter replacement, calibration expiry, counter rollover, negative values, non-finite values, and sensor error codes;
- missing samples, irregular intervals, changed sampling cadence, and unequal windows;
- workload, occupancy, weather, tariff, and service-level changes;
- zero baseline, sign/direction errors, rounding, currency mismatch, annualization, and overlapping totals;
- implementation and recurring costs greater than gross benefit;
- rebound, shifted burden, reduced service, and adverse human/environmental effects;
- altered raw artifacts, missing evidence references, broken event chain, duplicate event IDs, and unauthorized status promotion;
- failed intervention, rollback, partial rollback, and unavailable operator;
- independent reviewer cannot reproduce the result from retained evidence.

A test passing proves only the tested behavior on the exact revision and environment. Record command, environment, commit SHA, test output, and artifact reference.

## 10. First implementation sequence

1. **Audit existing code before adding modules.** Map `controller/impact.py`, `controller/measurement_ingest.py`, measurement pipeline/store/quarantine modules, and current tests to this protocol. Reuse existing implementations; do not create a parallel ledger or competing impact calculator.
2. Add versioned event and measurement schemas with strict validation and negative tests.
3. Extend the current impact calculator only where gaps are demonstrated: timezone-aware timestamps, explicit interval/window checks, unit and workload comparability, uncertainty, and lifecycle cost accounting.
4. Separate calculated candidate status from reviewer-assigned independent verification.
5. Add immutable event references and artifact-digest verification; do not claim WORM without a tested external retention control.
6. Build read-only fixtures and a synthetic pilot first. Clearly label synthetic data; never mix it with real-world totals.
7. Run the exact repository test suite and CI; publish code/test/CI/review status separately.
8. Only then invite one willing operator to provide a bounded, read-only dataset for a real pilot. No operator, no data, no claimed real-world impact.

## 11. Report format

For each opportunity, report:

- **Case / domain / owner / boundary**
- **Source and original claim** (date, URL, claim class)
- **Current status** across opportunity, work, measurement, impact, and authorization
- **Baseline and after-period** (values, units, sample counts, data quality, evidence refs)
- **Attribution method and uncertainty**
- **Gross physical effect / gross monetary benefit**
- **All lifecycle costs / net effect**
- **Service quality, human impact, rebound, and displaced burden**
- **V91 contribution** versus external operator actions
- **Exact implementation/test/CI/review evidence**
- **Limitations and next authorized step**

If no qualifying evidence exists, state: **NO VERIFIED REAL-WORLD SAVING DEMONSTRATED.**

---

**Implementation boundary:** This document is a proposed contract. Existing code, CI, or documentation must be inspected and mapped before any feature is marked implemented. Production use requires a real operator, authorized data, security/privacy review, tested recovery, and independent verification appropriate to the stakes.
