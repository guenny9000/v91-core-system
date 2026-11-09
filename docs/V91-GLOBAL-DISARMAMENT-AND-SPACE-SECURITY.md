# V91 Global Disarmament & Space Security Monitor

**Status: IMPLEMENTED IN SOURCE ONLY — runtime operation and external verification are not yet established.**

This component is a read-only evidence evaluator for public, lawfully obtained records concerning arms control, disarmament, weapons transfers, military production, autonomous weapons governance, and space security. It does not connect to external systems or issue operational commands.

## Safety and mission

V91's long-term objective is universal, non-discriminatory, verifiable disarmament and the peaceful conversion of destructive military capacity toward civilian protection, health, repair, reconstruction, and ecological restoration. The same evidence standard applies to every state and non-state actor; no country receives an evidence-based exemption.

The monitor supports that objective through evidence collection and evaluation. It is not an enforcement or coercive shutdown system. It has no weapon-control, military-network, satellite-command, targeting, cyber-intrusion, or deorbit execution interface.

## Evidence grades

- **UNKNOWN:** no admissible source record. UNKNOWN is never PASS.
- **DOCUMENTED:** at least one source record exists.
- **CORROBORATED:** at least two distinct publishers are represented.
- **VERIFIED:** a strong verification method is declared, at least two distinct publishers are present, and both a primary record and an independent-verifier record are supplied with SHA-256 digests.

The grade is a conservative record-level screening result, not an adjudication of legal compliance. The presence of a URL or hash does not prove truth, publisher identity, authenticity, or immutability. Human expert review and source-specific verification remain necessary.

## Space security classification

A satellite is not automatically a weapon or a weapon of mass destruction. Each space record must distinguish **civilian**, **dual_use**, **military**, and **unknown**. Civilian communications, navigation, weather, disaster response, and scientific services are protected critical infrastructure. The monitor does not propose disabling them. Anti-satellite weapons, military payloads, nuclear weapons in space, and civilian/dual-use services are distinct categories and must not be conflated.

## Data contract

A dataset is a JSON object with a `records` array. Each record requires:

- `record_id`, `category`, `claim`, `scope`, `observed_at`
- optional `space_object_class` and `verification_method`
- `sources`: objects with HTTPS `url`, `publisher`, `source_type`, `role`, `retrieved_at`, and lowercase 64-character `sha256`

The accepted categories and values are enforced in `monitor.py`. Unknown categories, invalid timestamps, non-HTTPS links, missing provenance, and malformed digests are rejected. The evaluator performs no network access; a future ingestion adapter must be separately reviewed, source-allowlisted, rate-limited, and tested.

## Local use

```python
from disarmament.monitor import evaluate_dataset

report = evaluate_dataset({"records": []})
print(report)
```

Run the focused tests with:

```bash
python -m unittest tests.test_disarmament_monitor -v
```

## Initial public-source register

See [source_registry.json](../data/disarmament/source_registry.json). The register identifies candidate public sources; it is not an assertion that their feeds have been connected, polled, or independently verified.

## Operational milestones still open

1. Build a reviewed, read-only ingestion adapter for public treaty and institutional records.
2. Add provenance-preserving snapshots and independently anchored integrity receipts.
3. Add expert-reviewed treaty-specific obligations and verification profiles.
4. Add duplicate detection, source conflict handling, correction history, and human adjudication.
5. Run CI and security review on the exact commit; then stage a local pilot.
6. Only after measured deployment and monitoring may the component be described as operational.

No global inventory, worldwide compliance result, automatic disarmament action, or satellite removal is claimed by this implementation.
