#!/usr/bin/env python3
"""
V91 Stewardship Gate (advisory only).

Scores a proposal with a fixed, transparent weighted index and records the
DECISION in the hash-chain ledger. It never shuts anything down: execution
needs a separate, explicitly authorised interface (REQUEST != AUTHORIZATION).

Hard ethics rule: if human_impact is at or above HUMAN_IMPACT_VETO the proposal
is rejected regardless of the score (ISOLATE_NOT_DESTROY).
"""

import math
import time
from typing import Any

from ledger import HashChainLedger

WEIGHTS = {"resource_util": 0.35, "entropy": 0.35, "environment": 0.30}
HUMAN_IMPACT_VETO = 0.5
TRIGGER_HIGH = 0.70
TRIGGER_LOW = 0.50


class StewardshipGate:
    def __init__(self, ledger_path: str = "v91_stewardship_ledger.jsonl") -> None:
        self.ledger = HashChainLedger(ledger_path)
        self._active = False

    @staticmethod
    def _validate(payload: dict[str, Any]) -> None:
        for key in (*WEIGHTS, "human_impact"):
            value = payload.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number in [0, 1]")
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{key} must be a number in [0, 1]")

    def evaluate(self, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a decision: APPROVED_ADVISORY, HOLD, IDLE or REJECTED_HUMAN_IMPACT."""
        self._validate(payload)
        score = sum(WEIGHTS[k] * float(payload[k]) for k in WEIGHTS)

        if payload["human_impact"] >= HUMAN_IMPACT_VETO:
            decision = "REJECTED_HUMAN_IMPACT"
            self._active = False
        elif score > TRIGGER_HIGH or (self._active and score >= TRIGGER_LOW):
            decision = "APPROVED_ADVISORY"
            self._active = True
        else:
            decision = "IDLE"
            self._active = False

        record = self.ledger.append(
            {
                "target": target,
                "input": {k: payload[k] for k in (*WEIGHTS, "human_impact")},
                "score": round(score, 6),
                "decision": decision,
                "executed": False,
            },
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        return {"decision": decision, "score": score, "hash": record["hash"]}
