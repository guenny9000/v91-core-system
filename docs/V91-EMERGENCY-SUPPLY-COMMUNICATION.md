# V91 emergency supply and communications assessment

**Status: IMPLEMENTED IN THIS BRANCH; NOT YET CI-VERIFIED OR DEPLOYED.**

## Purpose

This first increment provides a local, read-only assessment of operator-supplied
readiness records for essential resources and backup communications. Default
items are water, food, medical kit, and backup communications. Operators may
supply a different comma-separated list.

The assessment deliberately distinguishes a fresh source report from verified
physical availability. A manifest entry is not a sensor reading, a stock count
verified by an independent party, or proof that a service can actually be used.

## Manifest format

Example:

```json
{
  "schema_version": "v91.emergency_supply.v1",
  "items": {
    "water": {
      "status": "available",
      "observed_at_utc": "2026-11-24T18:00:00Z",
      "source": "local_inventory_check",
      "evidence_ref": "inventory-record-001",
      "quantity": 20,
      "minimum_quantity": 10,
      "unit": "L"
    },
    "comms_backup": {
      "status": "available",
      "observed_at_utc": "2026-11-24T18:00:00Z",
      "source": "radio_self_test",
      "evidence_ref": "test-record-009"
    }
  }
}
```

A status of `available` is accepted only when source, evidence reference,
and timezone-aware observation time are present and fresh. If quantity is
provided, quantity, minimum quantity, and unit must all be valid. A quantity
below the stated minimum is reported as MISSING. Missing, stale, future-dated,
malformed, or provenance-free information remains UNKNOWN.

## Run

```bash
python -m controller.emergency_supply --manifest config/emergency_manifest.json
python -m controller.emergency_supply --manifest config/emergency_manifest.json --required water,food,medical_kit,radio_backup
```

Exit codes: 0 means all required entries are REPORTED_AVAILABLE; 1 means a
reported shortage or UNKNOWN remains; 2 means the manifest or configuration
could not be assessed. Exit 0 is not independent verification or operational
readiness.

## Safety boundary

This increment does not write to `v91_bridge_inbox.jsonl`: that file belongs
to the existing kern-bridge raw-intake format and must not be mixed with a
different alert schema. It also does not write to the HashChainLedger, send
webhooks, access the network, issue official public warnings, or control
physical infrastructure. Those actions require separate delivery, locking,
authorization, privacy, retry, and recovery design.

No service is automatically stopped or scaled down. Critical supply,
communication, accessibility, monitoring, alarm, and recovery functions must
be protected from resource-saving actions. Classification is not authority.

## Communications design context

Use a layered, independently powered warning mix rather than assuming one
network remains available. The German BBK describes warning apps and mobile
warnings as useful channels but notes that power or mobile-network failures
can disable them; battery-powered, car, or crank radios remain useful fallback
channels. Cell Broadcast requires a functioning mobile cell and a compatible,
powered handset. Official public warnings remain the responsibility of
competent authorities; this module does not connect to MoWaS or issue alerts.

References:
- BBK, warnings and outages: https://www.bbk.bund.de/DE/Warnung-Vorsorge/Vorsorge/In-der-Krise-informiert-sein/Warnungen-erhalten-verstehen/warnungen-erhalten-und-verstehen_node.html
- BBK, Cell Broadcast: https://www.bbk.bund.de/DE/Warnung-Vorsorge/Warnung-in-Deutschland/So-werden-Sie-gewarnt/Cell-Broadcast/cell-broadcast_node.html
- BBK, crisis information and radio fallback: https://www.bbk.bund.de/DE/Warnung-Vorsorge/Vorsorge/In-der-Krise-informiert-sein/in-der-krise-informiert-sein_node.html

## Next gates

1. Add independent evidence adapters for specific stock, power, radio, and
   communication checks, with calibration/ownership/freshness metadata.
2. Design a durable, cross-process-safe alert outbox without mixing ledger
   schemas; verify retries, deduplication, corruption handling, and restore.
3. Add only explicitly configured, privacy-reviewed notification adapters.
4. Test offline operation and failure recovery in disposable environments.
5. Keep the emergency fail-safe implementation plan as the authority for any
   host isolation or emergency action; this supply assessment grants no such
   authority.

Related work: core issues #8 (local-first resilience), #47 (capability-aware
resource admission), and #103 (authenticated federation transport).
