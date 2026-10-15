"""Validated feedback records for reviewed, offline policy improvement.

Feedback is stored as data, never executed as code and never applied automatically
to production policy. A human/reviewer must approve any resulting policy change.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ALLOWED_LABELS = frozenset({
    "correct_allow",
    "correct_deny",
    "false_allow",
    "false_deny",
    "needs_review",
})


def make_feedback_record(
    *,
    case_id: str,
    request: Mapping[str, Any],
    decision_code: str,
    actual_allowed: bool,
    expected_allowed: bool | None,
    label: str,
    reviewer: str,
    note: str = "",
) -> dict[str, Any]:
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id muss eine nicht-leere Zeichenkette sein.")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer muss eine nicht-leere Zeichenkette sein.")
    if not isinstance(request, Mapping):
        raise ValueError("request muss ein Objekt sein.")
    if not isinstance(decision_code, str) or not decision_code.strip():
        raise ValueError("decision_code muss eine nicht-leere Zeichenkette sein.")
    if not isinstance(note, str):
        raise ValueError("note muss eine Zeichenkette sein.")
    if label not in ALLOWED_LABELS:
        raise ValueError(f"Unbekanntes Feedbacklabel: {label}")
    if not isinstance(actual_allowed, bool):
        raise ValueError("actual_allowed muss boolesch sein.")
    if expected_allowed is not None and not isinstance(expected_allowed, bool):
        raise ValueError("expected_allowed muss boolesch oder None sein.")
    if len(note) > 2000:
        raise ValueError("note darf höchstens 2000 Zeichen enthalten.")
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "request": dict(request),
        "decision_code": decision_code,
        "actual_allowed": actual_allowed,
        "expected_allowed": expected_allowed,
        "label": label,
        "reviewer": reviewer,
        "note": note,
        "policy_change_applied": False,
    }


def append_feedback(path: str | Path, record: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def summarize_feedback(path: str | Path) -> dict[str, Any]:
    counts = {label: 0 for label in sorted(ALLOWED_LABELS)}
    total = 0
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Ungültiger Feedbackdatensatz in Zeile {line_number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Feedbackdatensatz in Zeile {line_number} muss ein JSON-Objekt sein")
        label = record.get("label")
        if not isinstance(label, str) or label not in ALLOWED_LABELS:
            raise ValueError(f"Ungültiges Label in Zeile {line_number}")
        counts[label] += 1
        total += 1
    return {
        "schema_version": "1.0",
        "total_records": total,
        "label_counts": counts,
        "training_status": "DATASET_ONLY_NO_MODEL_TRAINED",
        "production_policy_changed": False,
    }
