"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Vorlage für neue controller/-Module: ehrlich, fail-closed, ohne
Interpolation und ohne Wirkung über den eigenen Rechner hinaus.
Richtlinie: docs/AXIOM_HEADER.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class VerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AuditResult:
    state: VerificationState
    evidence: str


def evaluate_sensor_input(raw_value: float | None) -> AuditResult:
    """Ehrliche, fail-closed Prüfroutine ohne Interpolation.

    None bleibt UNKNOWN (nie HEALTHY), unplausible Werte sind ERROR,
    nur echte Messwerte sind VERIFIED - und auch dann nur lokal.
    """
    if raw_value is None:
        return AuditResult(
            state=VerificationState.UNKNOWN,
            evidence="Keine physischen Messdaten vorhanden (UNKNOWN != HEALTHY).",
        )
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        return AuditResult(
            state=VerificationState.ERROR,
            evidence="Messwert ist nicht numerisch.",
        )
    if raw_value < 0:
        return AuditResult(
            state=VerificationState.ERROR,
            evidence=f"Unplausibler negativer Messwert erkannt: {raw_value}",
        )
    return AuditResult(
        state=VerificationState.VERIFIED,
        evidence=f"Messwert lokal gemessen: {raw_value}",
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Template module: honest, fail-closed, local-only")
    parser.add_argument("--value", type=float, default=None)
    args = parser.parse_args(argv)
    result = evaluate_sensor_input(args.value)
    print(json.dumps({"state": result.state.value, "evidence": result.evidence}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
