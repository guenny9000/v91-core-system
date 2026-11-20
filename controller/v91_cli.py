#!/usr/bin/env python3
"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------


V91 CLI.

  python controller/v91_cli.py evaluate TARGET --resource-util 0.8 --entropy 0.7 \
      --environment 0.6 --human-impact 0.1 [--ledger FILE]
  python controller/v91_cli.py verify [--ledger FILE]

Exit codes: 0 ok / approved or idle, 1 invalid input or broken ledger, 2 rejected (human impact).
"""

import argparse
import json
import sys

from enforcement import StewardshipGate
from ledger import verify_chain

DEFAULT_LEDGER = "v91_stewardship_ledger.jsonl"
DEFAULT_MEASUREMENT_STORE = "v91_measurements.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="v91")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("evaluate", help="score a proposal and record the decision (advisory)")
    ev.add_argument("target")
    for name in ("resource-util", "entropy", "environment", "human-impact"):
        ev.add_argument(f"--{name}", type=float, required=True)
    ev.add_argument("--ledger", default=DEFAULT_LEDGER)

    vf = sub.add_parser("verify", help="re-verify the whole hash chain")
    vf.add_argument("--ledger", default=DEFAULT_LEDGER)

    im = sub.add_parser("impact", help="compare real baseline/after measurements, record result")
    im.add_argument("measure")
    im.add_argument("--baseline", required=True, help="CSV timestamp,value,source_type")
    im.add_argument("--after", required=True, help="CSV timestamp,value,source_type")
    im.add_argument("--unit", required=True)
    im.add_argument("--co2-factor", type=float, default=None, help="kg CO2 per unit (cite source)")
    im.add_argument("--co2-source", default=None, help="required with --co2-factor")
    im.add_argument("--higher-is-better", action="store_true")
    im.add_argument("--ledger", default=DEFAULT_LEDGER)

    rp = sub.add_parser("report", help="verified totals (chain must be valid)")
    rp.add_argument("--ledger", default=DEFAULT_LEDGER)

    sr = sub.add_parser("stewardship-report", help="decision counts and percentages")
    sr.add_argument("--ledger", default=DEFAULT_LEDGER)

    co = sub.add_parser("collect-local", help="record real local memory-in-use samples to CSV")
    co.add_argument("--out", required=True)
    co.add_argument("--samples", type=int, default=10)
    co.add_argument("--interval", type=float, default=1.0)

    lg = sub.add_parser("legacy-gate", help="evaluate legacy transformation evidence record")
    lg.add_argument("--record", required=True, help="JSON record file")

    rec = sub.add_parser("record", help="record one real measurement (zero-code operator entry)")
    rec.add_argument("sensor_id", help="e.g. VB-Alsfeld-01")
    rec.add_argument("--metric", required=True, help="e.g. grundlast")
    rec.add_argument("--value", required=True, help="numeric value; German decimal comma accepted (142,5)")
    rec.add_argument("--unit", required=True, help="e.g. watt, kwh, liter")
    rec.add_argument("--min", type=float, required=True, help="plausibility lower bound of this measurement")
    rec.add_argument("--max", type=float, required=True, help="plausibility upper bound of this measurement")
    rec.add_argument("--timestamp", default=None, help="tz-aware source time ISO format (default: now UTC, never backdated)")
    rec.add_argument("--source", default=None, help="provenance label, e.g. zaehlerfoto-20261118.jpg")
    rec.add_argument("--store", default=DEFAULT_MEASUREMENT_STORE)

    ij = sub.add_parser("import-json", help="import another node's measurement JSON list through the same gate")
    ij.add_argument("file")
    ij.add_argument("--metric", required=True)
    ij.add_argument("--unit", required=True)
    ij.add_argument("--min", type=float, required=True)
    ij.add_argument("--max", type=float, required=True)
    ij.add_argument("--tag", required=True, help="import provenance tag, e.g. lauterbach-2026-11-18")
    ij.add_argument("--store", default=DEFAULT_MEASUREMENT_STORE)

    args = parser.parse_args(argv)

    if args.cmd == "collect-local":
        from collector import collect

        collect(args.out, args.samples, args.interval)
        print(f"wrote {args.samples} samples to {args.out}")
        return 0

    if args.cmd == "impact":
        from impact import compute_impact, load_csv, record_impact

        try:
            result = compute_impact(
                args.measure, load_csv(args.baseline), load_csv(args.after), args.unit,
                args.co2_factor, higher_is_worse=not args.higher_is_better,
                co2_source=args.co2_source,
            )
            from ledger import HashChainLedger

            result["hash"] = record_impact(HashChainLedger(args.ledger), result)["hash"]
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("VALID", "NO_IMPROVEMENT") else 3

    if args.cmd == "report":
        from impact import verified_summary

        chain = verify_chain(args.ledger)
        if not chain["chain_valid"]:
            print(json.dumps(chain, indent=2))
            return 1
        print(json.dumps({**chain, **verified_summary(args.ledger)}, indent=2))
        return 0

    if args.cmd == "stewardship-report":
        from stewardship_report import summarize

        result = summarize(args.ledger)
        print(json.dumps(result, indent=2))
        return 0 if result["chain_valid"] else 1

    if args.cmd == "legacy-gate":
        from legacy_gate import evaluate_record, load_record

        try:
            result = evaluate_record(load_record(args.record))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
        return 0 if result["decision"] == "READY" else 3

    if args.cmd == "record":
        from operator_entry import record_measurement
        from measurement_store import MeasurementStore, MeasurementStoreError

        try:
            value = float(args.value.replace(",", "."))
        except ValueError:
            print("error: --value must be numeric (142.5 or 142,5)", file=sys.stderr)
            return 1
        try:
            result = record_measurement(
                store=MeasurementStore(args.store),
                sensor_id=args.sensor_id,
                metric=args.metric,
                value=value,
                unit=args.unit,
                minimum=args.min,
                maximum=args.max,
                timestamp=args.timestamp,
                source=args.source or "operator-manual",
            )
        except (MeasurementStoreError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if result["status"] == "RECORDED":
            print(json.dumps(result, indent=2))
            return 0
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 3

    if args.cmd == "import-json":
        from operator_entry import import_foreign_file
        from measurement_store import MeasurementStore, MeasurementStoreError

        try:
            summary = import_foreign_file(
                store=MeasurementStore(args.store),
                path=args.file,
                metric=args.metric,
                unit=args.unit,
                minimum=args.min,
                maximum=args.max,
                source_tag=args.tag,
            )
        except (MeasurementStoreError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(summary, indent=2))
        return 0 if summary["quarantined"] == 0 else 3

    if args.cmd == "verify":
        report = verify_chain(args.ledger)
        print(json.dumps(report, indent=2))
        return 0 if report["chain_valid"] else 1

    payload = {
        "resource_util": args.resource_util,
        "entropy": args.entropy,
        "environment": args.environment,
        "human_impact": args.human_impact,
    }
    try:
        result = StewardshipGate(args.ledger).evaluate(args.target, payload)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 2 if result["decision"] == "REJECTED_HUMAN_IMPACT" else 0


if __name__ == "__main__":
    sys.exit(main())
