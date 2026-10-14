"""Run isolated Global Guard scenarios and emit machine-readable results.

This runner evaluates policy decisions only; it deliberately never executes tools.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .policy import GuardPolicy, authorize_action


def run_scenarios(
    scenarios: Iterable[Mapping[str, Any]],
    policy: GuardPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or GuardPolicy()
    results: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios):
        name = str(scenario.get("name") or f"scenario-{index + 1}")
        request = scenario.get("request")
        expected = scenario.get("expected_allowed")
        if not isinstance(request, dict) or not isinstance(expected, bool):
            results.append({
                "name": name,
                "status": "INVALID_SCENARIO",
                "expected_allowed": expected,
                "actual_allowed": None,
                "reason": "request muss ein Objekt und expected_allowed ein Wahrheitswert sein.",
            })
            continue
        decision = authorize_action(request, policy)
        passed = decision.allowed is expected
        results.append({
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "expected_allowed": expected,
            "actual_allowed": decision.allowed,
            "decision_code": decision.code,
            "action_class": decision.action_class,
            "audit": dict(decision.audit),
        })
    valid = [item for item in results if item["status"] in {"PASS", "FAIL"}]
    passed = sum(item["status"] == "PASS" for item in valid)
    return {
        "schema_version": "1.0",
        "component": "V91_GLOBAL_GUARD",
        "execution_mode": "POLICY_EVALUATION_ONLY_NO_TOOLS_EXECUTED",
        "status": "PASS" if valid and passed == len(valid) and len(valid) == len(results) else "FAIL",
        "summary": {
            "total": len(results),
            "valid": len(valid),
            "passed": passed,
            "failed": sum(item["status"] == "FAIL" for item in results),
            "invalid": sum(item["status"] == "INVALID_SCENARIO" for item in results),
        },
        "results": results,
    }


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ungültiges JSON in Zeile {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Zeile {line_number} muss ein JSON-Objekt sein.")
            scenarios.append(item)
    return scenarios


def write_report(report: Mapping[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
