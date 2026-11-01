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

    args = parser.parse_args(argv)

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
