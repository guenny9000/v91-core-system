"""Command-line interface for isolated Global Guard evaluation."""
from __future__ import annotations

import argparse
import json

from .feedback import summarize_feedback
from .scenario_runner import load_scenarios, run_scenarios, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="V91 Global Guard isolated evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate", help="Run policy scenarios and write JSON report")
    evaluate.add_argument("--input", required=True, help="JSONL scenario file")
    evaluate.add_argument("--output", required=True, help="Output JSON report")

    feedback = sub.add_parser("feedback-summary", help="Summarize reviewed JSONL feedback")
    feedback.add_argument("--input", required=True, help="Feedback JSONL file")
    feedback.add_argument("--output", required=True, help="Output JSON summary")

    args = parser.parse_args()
    if args.command == "evaluate":
        report = run_scenarios(load_scenarios(args.input))
        write_report(report, args.output)
        print(json.dumps(report["summary"], ensure_ascii=False))
        return 0 if report["status"] == "PASS" else 1

    report = summarize_feedback(args.input)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
