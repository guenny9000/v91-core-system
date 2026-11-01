#!/usr/bin/env python3
"""
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

    co = sub.add_parser("collect-local", help="record real local memory-in-use samples to CSV")
    co.add_argument("--out", required=True)
    co.add_argument("--samples", type=int, default=10)
    co.add_argument("--interval", type=float, default=1.0)

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
