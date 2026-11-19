"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Review-Index: deterministische Aggregations-Schicht UEBER den
Struktur-Review-Datasets in docs/structure-reviews/ (Modul-Schritt
der Struktur-Review-Serie). Liest alle Datasets, prueft jedes ueber
controller.structure_review.evaluate_structure und baut daraus EINEN
reproduzierbaren Index: Verdict-Verteilung, Problem-Zaehler je
Kriterium, NICHT_GEPRUEFT-Zaehler je Kriterium sowie eine
Datei-Eintragung je Dataset. Aggregiert nur, bewertet nicht neu und
priorisiert nicht (AGGREGATION != PRIORITAET). Ohne Zeitstempel und
ohne Zufall, damit zwei Laeufe identisch sind. Fail-closed: EIN
ungueltiges Dataset ungueltigt den ganzen Lauf.
CLAIM != EVIDENCE; SCRIPTED != INSTALLED; REVIEW != ENTSCHEIDUNG.

Ehrliche Grenzen: ein Index ueber Datasets ist kein Ersatz fuer deren
Pruefung; er erbt deren Verify-Stand, erstellt keine neue Evidenz,
ruft keine externen Systeme auf und trifft keine Entscheidungen
(REQUEST != BEFEHL). Zahlen sollte niemand als Prioritaeten lesen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

if __package__ in (None, ""):  # direkter CLI-Aufruf: sys.path erweitern
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controller.structure_review import StructureReviewError, evaluate_structure

SCHEMA_VERSION = 1
DEFAULT_DATASET_DIR = "docs/structure-reviews"


class ReviewIndexError(Exception):
    """Fail-closed Fehler des Review-Index."""


def build_index(dataset_dir: Path) -> Dict[str, Any]:
    """Baut den deterministischen Index ueber alle Datasets eines Verzeichnisses.

    deterministisch: keine Zeitstempel, keine Zufallswerte; zwei Aufrufe
    auf gleichem Stand liefern das identische dict.
    fail-closed: fehlendes/leeres Verzeichnis, ungueltiges JSON oder ein
    evaluate_structure-Fehlerheben ReviewIndexError (mit Dateiname)."""
    if not isinstance(dataset_dir, Path):
        raise ReviewIndexError("dataset_dir must be a pathlib.Path")
    if not dataset_dir.is_dir():
        raise ReviewIndexError(f"dataset dir not found: {dataset_dir}")
    paths = sorted(p for p in dataset_dir.glob("*.json") if p.is_file())
    if not paths:
        raise ReviewIndexError(f"no datasets found in: {dataset_dir}")

    datasets: list = []
    by_verdict: Dict[str, int] = {}
    problems_by_criterion: Dict[str, int] = {}
    ungeprueft_by_criterion: Dict[str, int] = {}
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                review = json.load(handle)
        except (OSError, ValueError) as error:
            raise ReviewIndexError(f"dataset not readable: {path.name}: {error}") from error
        if not isinstance(review, dict):
            raise ReviewIndexError(f"dataset is not an object: {path.name}")
        try:
            result = evaluate_structure(review)
        except StructureReviewError as error:
            raise ReviewIndexError(f"dataset invalid: {path.name}: {error}") from error
        verdict = result["verdict"]
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        for criterion in result["problems"]:
            problems_by_criterion[criterion] = problems_by_criterion.get(criterion, 0) + 1
        for criterion in result["ungeprueft"]:
            ungeprueft_by_criterion[criterion] = ungeprueft_by_criterion.get(criterion, 0) + 1
        datasets.append({
            "file": path.name,
            "structure_id": result["structure_id"],
            "verdict": verdict,
            "criteria_belegt": result["criteria_belegt"],
            "criteria_problem_belegt": result["criteria_problem_belegt"],
            "criteria_ungeprueft": result["criteria_ungeprueft"],
            "problems": list(result["problems"]),
            "ungeprueft": list(result["ungeprueft"]),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_dir": str(dataset_dir),
        "datasets_total": len(datasets),
        "by_verdict": dict(sorted(by_verdict.items())),
        "problems_by_criterion": dict(sorted(
            item for item in problems_by_criterion.items() if item[1] > 0
        )),
        "ungeprueft_by_criterion": dict(sorted(
            item for item in ungeprueft_by_criterion.items() if item[1] > 0
        )),
        "datasets": datasets,
        "honest_limits": [
            "INDEX != BEWERTUNG; dieses Modul aggregiert nur.",
            "AGGREGATION != PRIORITAET; Reihenfolge bleibt menschliche Entscheidung.",
            "Fail-closed: ein ungueltiges Dataset ungueltigt den ganzen Lauf.",
        ],
    }


def main(argv=None) -> int:
    """CLI: baut den Index ueber docs/structure-reviews (Exit 0) oder schlaegt
    fail-closed durch (Exit 2). Exit 1 (Verdict-Signal) gibt es hier nicht:
    der Index bewertet nicht."""
    parser = argparse.ArgumentParser(description="Build deterministic review index")
    parser.add_argument("--dataset-dir", default=DEFAULT_DATASET_DIR)
    args = parser.parse_args(argv)
    try:
        index = build_index(Path(args.dataset_dir))
    except ReviewIndexError as error:
        print(f"review-index error: {error}", file=sys.stderr)
        return 2
    json.dump(index, sys.stdout, indent=2, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
