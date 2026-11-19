"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Wirkungs-Index: R5-Schritt der Global Impact Engine (Modul-Schritt 7).
Aggregiert deterministisch die R4-Wirkungs-Assessments ALLER Pilot-
Initiativen aus docs/messmatrix. Pro Messmatrix-Dataset wird das
Passende Messwert-Ledger gesucht (Standardpfad-Muster im ledger-dir,
Name aus initiative_id plus .jsonl) und ueber controller/
wirkungs_assessment.assess bewertet; gescheiterte oder ungeklaerte
Piloten werden ehrlich als CLOSED_GATES/UNKNOWN gefuehrt, niemals als
Erfolg (UNKNOWN != PASS). Ein fehlendes Ledger ist keine Abwertung der
Matrix, sondern der ehrliche Zustand R3-Offen.
Keine Zeitstempel, kein Zufall, keine Uhr: zwei Laeufe sind identisch
(aggregiert wird, nicht bewertet). INDEX != PRIORITAET;
AGGREGATION != URTEIL; WIRKUNG_BEOBACHTET != WIRKUNG_NACHGEWIESEN.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):  # direkter CLI-Aufruf: Pfade erweitern
    _ROOT = str(Path(__file__).resolve().parents[1])
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from wirkungs_assessment import WirkungsAssessmentError, assess
    from messwerte_ingest import MesswerteIngestError, load_dataset
else:
    from controller.wirkungs_assessment import (  # noqa: E402
        WirkungsAssessmentError,
        assess,
    )
    from controller.messwerte_ingest import (  # noqa: E402
        MesswerteIngestError,
        load_dataset,
    )

INDEX_VERSION = 1

WIRKUNG_STATUSES = (
    "WIRKUNG_UNKNOWN",
    "WIRKUNG_BEOBACHTET",
    "UNBEWERTET_GESCHLOSSENES_TOR",
)


def _ledger_candidates(ledger_dir: Path, initiative_id: str) -> List[Path]:
    """Moegliche Ledger-Pfade fuer eine Initiative (deterministisch)."""
    slug = initiative_id.strip().replace("/", "-")
    return [
        ledger_dir / f"{slug}.jsonl",
        ledger_dir / f"{slug}.json",
    ]


def build_index(dataset_dir: Path,
                ledger_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregiert alle Pilot-Assessments, fail-closed, deterministisch."""
    if not isinstance(dataset_dir, Path):
        raise WirkungsAssessmentError("dataset_dir must be a Path")
    if ledger_dir is not None and not isinstance(ledger_dir, Path):
        raise WirkungsAssessmentError("ledger_dir must be a Path or None")
    if not dataset_dir.is_dir():
        raise WirkungsAssessmentError(f"dataset dir not found: {dataset_dir}")
    if ledger_dir is not None and not ledger_dir.is_dir():
        raise WirkungsAssessmentError(f"ledger dir not found: {ledger_dir}")

    entries: List[Dict[str, Any]] = []
    by_watcher: Dict[str, int] = {}
    by_wirkung: Dict[str, int] = {status: 0 for status in WIRKUNG_STATUSES}
    by_gates_open: Dict[str, int] = {"true": 0, "false": 0}
    indicators_total = 0
    indicators_observed = 0
    indicators_unknown = 0
    indicators_target_reached = 0
    ledgers_found = 0

    for path in sorted(dataset_dir.glob("*.json")):
        initiative_id = path.stem
        try:
            record = load_dataset(path)
        except (MesswerteIngestError, OSError) as error:
            raise WirkungsAssessmentError(
                f"dataset invalid ({path.name}): {error}") from error
        rid = record.get("initiative_id")
        if not isinstance(rid, str) or not rid.strip():
            raise WirkungsAssessmentError(
                f"dataset without initiative_id: {path.name}")
        candidates: List[Path] = (
            _ledger_candidates(ledger_dir, rid) if ledger_dir is not None else [])
        ledger_path = next((c for c in candidates if c.is_file()), None)
        if ledger_path is None:
            assessment = None
            wirkung = "WIRKUNG_UNKNOWN"
            gates_open = True
            reason = "ledger_missing_R3_offen"
        else:
            ledgers_found += 1
            try:
                assessment = assess(path, ledger_path)
            except (MesswerteIngestError, WirkungsAssessmentError,
                    ValueError, OSError) as error:
                assessment = None
                wirkung = "UNBEWERTET_GESCHLOSSENES_TOR"
                gates_open = False
                reason = f"assess_failed: {error}"
            else:
                wirkung = assessment.get("wirkung_status", "WIRKUNG_UNKNOWN")
                gates_open = bool(assessment.get("all_gates_open"))
                reason = "; ".join(assessment.get("closed_reasons", [])) or None

        if wirkung not in by_wirkung:
            by_wirkung[wirkung] = 0
        by_wirkung[wirkung] += 1
        by_gates_open["true" if gates_open else "false"] += 1
        watcher = record.get("watcher")
        if not isinstance(watcher, str) or not watcher.strip():
            raise WirkungsAssessmentError(
                f"dataset without watcher: {path.name}")
        by_watcher[watcher] = by_watcher.get(watcher, 0) + 1

        per_indicator: Dict[str, Any] = {}
        if assessment is not None:
            for name, slot in sorted(
                    assessment.get("indicators", {}).items()):
                state = slot.get("status", "UNKNOWN")
                per_indicator[name] = state
                indicators_total += 1
                if state == "UNKNOWN":
                    indicators_unknown += 1
                else:
                    indicators_observed += 1
                if slot.get("target_reached"):
                    indicators_target_reached += 1
        else:
            definitions = record.get("indicators", [])
            if not isinstance(definitions, list):
                raise WirkungsAssessmentError(
                    f"indicators not a list: {path.name}")
            for definition in definitions:
                if not isinstance(definition, dict) or \
                        not isinstance(definition.get("name"), str):
                    raise WirkungsAssessmentError(
                        f"indicator without name: {path.name}")
            per_indicator = {definition["name"]: "UNKNOWN"
                             for definition in definitions}
            indicators_total += len(definitions)
            indicators_unknown += len(definitions)

        entries.append({
            "matrix_filename": path.name,
            "initiative_id": rid,
            "watcher": watcher,
            "maturity": record.get("maturity"),
            "ledger_found": ledger_path is not None,
            "all_gates_open": gates_open,
            "wirkung_status": wirkung,
            "closed_reason": reason,
            "indicators": per_indicator,
        })

    return {
        "index_version": INDEX_VERSION,
        "pilots_total": len(entries),
        "ledgers_found": ledgers_found,
        "ledgers_missing": len(entries) - ledgers_found,
        "pilots_gates_open": by_gates_open["true"],
        "pilots_gates_closed": by_gates_open["false"],
        "by_watcher": dict(sorted(by_watcher.items())),
        "by_wirkung_status": {status: by_wirkung.get(status, 0)
                              for status in WIRKUNG_STATUSES},
        "indicators_total": indicators_total,
        "indicators_observed": indicators_observed,
        "indicators_unknown": indicators_unknown,
        "indicators_target_reached": indicators_target_reached,
        "entries": entries,
        "honest_limits": [
            "INDEX != PRIORITAET; Aggregation bewertet nicht.",
            "Fehlende Ledger sind R3-offen, kein Misserfolg (UNKNOWN != PASS).",
            "WIRKUNG_BEOBACHTET ist nie WIRKUNG_NACHGEWIESEN.",
            "Gescheiterte Assessments bleiben UNBEWERTET_GESCHLOSSENES_TOR.",
        ],
    }


def main(argv=None) -> int:
    """CLI: build-index --dataset-dir [--ledger-dir]. Exit 0/2."""
    parser = argparse.ArgumentParser(description="Wirkungs-Index (R5)")
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--ledger-dir", default=None)
    args = parser.parse_args(argv)
    try:
        result = build_index(Path(args.dataset_dir),
                             Path(args.ledger_dir) if args.ledger_dir else None)
    except (MesswerteIngestError, WirkungsAssessmentError, ValueError,
            OSError) as error:
        print(f"wirkungs-index: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2, sort_keys=True, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
