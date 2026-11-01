#!/usr/bin/env python3
"""Summaries for stewardship decision ledgers."""

import json
from collections import Counter
from typing import Any

from ledger import verify_chain


def summarize(path: str) -> dict[str, Any]:
    """Return counts and percentages for stewardship decisions."""
    chain = verify_chain(path)
    if not chain["chain_valid"]:
        return {
            **chain,
            "total_entries": chain["records_checked"],
            "decision_counts": {},
            "decision_percent": {},
            "human_impact_veto_count": 0,
            "executed_true_count": 0,
        }

    counts: Counter[str] = Counter()
    total = 0
    veto_count = 0
    executed_true = 0

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            payload = rec.get("payload", {})
            decision = str(payload.get("decision", "UNKNOWN_DECISION"))
            counts[decision] += 1
            total += 1
            if decision == "REJECTED_HUMAN_IMPACT":
                veto_count += 1
            if payload.get("executed") is True:
                executed_true += 1

    percent = {
        decision: round((count / total) * 100.0, 2) if total else 0.0
        for decision, count in counts.items()
    }
    return {
        **chain,
        "total_entries": total,
        "decision_counts": dict(sorted(counts.items())),
        "decision_percent": dict(sorted(percent.items())),
        "human_impact_veto_count": veto_count,
        "executed_true_count": executed_true,
    }
