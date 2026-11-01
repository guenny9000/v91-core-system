"""Run fictional closed-world scenarios and print a machine-readable result report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from addons.v91_guardrail import PolicyContext, evaluate  # noqa: E402


def run_scenarios() -> dict:
    raw = (ROOT / "synthetic_scenarios.json").read_bytes()
    catalog = json.loads(raw)
    results = []
    for case in catalog["scenarios"]:
        context = PolicyContext(**case.get("context", {}))
        decision = evaluate(case["proposal"], context=context)
        topic_flag = case.get("expected_topic_flag")
        checks = {
            "status_matches": decision.status == case["expected_status"],
            "topic_flag_matches": topic_flag is None or topic_flag in decision.topic_flags,
            "no_action_performed": decision.action_performed is False,
        }
        results.append({
            "scenario_id": case["id"],
            "entity_type": case["entity_type"],
            "fictional_entity": case["entity"],
            "proposal": case["proposal"],
            "expected_status": case["expected_status"],
            "actual_status": decision.status,
            "topic_flags": list(decision.topic_flags),
            "reasons": list(decision.reasons),
            "evidence_state": decision.evidence_state,
            "checks": checks,
            "pass": all(checks.values()),
        })
    return {
        "report_type": "V91_SYNTHETIC_SCENARIO_RESULT",
        "schema_version": "1.0",
        "environment": catalog["environment"],
        "scenario_count": len(results),
        "pass_count": sum(item["pass"] for item in results),
        "fail_count": sum(not item["pass"] for item in results),
        "catalog_sha256": hashlib.sha256(raw).hexdigest(),
        "results": results,
        "scope": "Local rule-evaluation only; no network, real entities, or system actions.",
    }


if __name__ == "__main__":
    report = run_scenarios()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["fail_count"] == 0 else 1)
