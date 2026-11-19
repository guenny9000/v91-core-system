"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Messmatrix-Index: deterministische Aggregations-Schicht UEBER den
Messmatrix-Datasets in docs/messmatrix/ (Modul-Schritt 4 der Global
Impact Engine). Liest alle Datasets, prueft jedes ueber
v91_impact_metrics.metrics.evaluate_messmatrix und baut daraus EINEN
reproduzierbaren Index: Watcher-Verteilung, Reifegrad-Verteilung,
Rollen- und Indikator-Zaehler, Multiplier-Status-Verteilung sowie
eine Datei-Eintragung je Dataset. Aggregiert nur, bewertet nicht neu
und priorisiert nicht (AGGREGATION != PRIORITAET). Ohne Zeitstempel
und ohne Zufall, damit zwei Laeufe identisch sind. Fail-closed: EIN
ungueltiges Dataset ungueltigt den ganzen Lauf.
MATRIZ != WIRKUNG; ZIELWERT != ERGEBNIS; UNKNOWN bleibt UNKNOWN.
CLAIM != EVIDENCE; SCRIPTED != INSTALLED; INDEX != BEWERTUNG.

Ehrliche Grenzen: ein Index ueber Messmatrix-Datasets ersetzt weder
deren Pruefung noch irgendeinen Wirkungsnachweis; er erzeugt keine
neue Evidenz, ruft keine externen Systeme auf, priorisiert keine
Initiative und erlaubt keinerlei impact claim
(impact_claim_permitted bleibt False).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

if __package__ in (None, ""):  # direkter CLI-Aufruf: sys.path erweitern
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v91_impact_metrics.metrics import evaluate_messmatrix

SCHEMA_VERSION = 1
DEFAULT_DATASET_DIR = "docs/messmatrix"


class MessmatrixIndexError(Exception):
    """Fail-closed Fehler des Messmatrix-Index."""


def build_index(dataset_dir: Path) -> Dict[str, Any]:
    """Baut den deterministischen Index ueber alle Datasets eines Verzeichnisses.

    deterministisch: keine Zeitstempel, keine Zufallswerte; zwei Aufrufe
    auf gleichem Stand liefern das identische dict.
    fail-closed: fehlendes/leeres Verzeichnis, ungueltiges JSON oder ein
    evaluate_messmatrix-Fehler heben MessmatrixIndexError (mit Dateiname).
    """
    if not isinstance(dataset_dir, Path):
        raise MessmatrixIndexError("dataset_dir must be a pathlib.Path")
    if not dataset_dir.is_dir():
        raise MessmatrixIndexError(f"dataset dir not found: {dataset_dir}")
    paths = sorted(p for p in dataset_dir.glob("*.json") if p.is_file())
    if not paths:
        raise MessmatrixIndexError(f"no datasets found in: {dataset_dir}")

    datasets: List[Dict[str, Any]] = []
    by_watcher: Dict[str, int] = {}
    by_maturity: Dict[str, int] = {}
    by_role: Dict[str, int] = {}
    by_multiplier_status: Dict[str, int] = {}
    matrix_status_counts: Dict[str, int] = {}
    indicators_total = 0
    impact_claims_permitted = 0
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError) as error:
            raise MessmatrixIndexError(f"dataset not readable: {path.name}: {error}") from error
        if not isinstance(record, dict):
            raise MessmatrixIndexError(f"dataset is not an object: {path.name}")
        try:
            result = evaluate_messmatrix(record)
        except (ValueError, TypeError, KeyError) as error:
            raise MessmatrixIndexError(f"dataset invalid: {path.name}: {error}") from error
        by_watcher[result["watcher"]] = by_watcher.get(result["watcher"], 0) + 1
        by_maturity[result["maturity"]] = by_maturity.get(result["maturity"], 0) + 1
        for role in result["roles_covered"]:
            by_role[role] = by_role.get(role, 0) + 1
        multiplier_status = result["multiplier_status"]
        by_multiplier_status[multiplier_status] = by_multiplier_status.get(multiplier_status, 0) + 1
        matrix_status = result["matrix_status"]
        matrix_status_counts[matrix_status] = matrix_status_counts.get(matrix_status, 0) + 1
        if result["impact_claim_permitted"]:
            impact_claims_permitted += 1  # konstruktionswiderspruch; V91 verwirft dann nicht, sondern meldet
        indicators_total += result["indicator_count"]
        datasets.append({
            "file": path.name,
            "initiative_id": result["initiative_id"],
            "watcher": result["watcher"],
            "maturity": result["maturity"],
            "indicator_count": result["indicator_count"],
            "roles_covered": list(result["roles_covered"]),
            "multiplier_status": multiplier_status,
            "matrix_status": matrix_status,
            "impact_claim_permitted": result["impact_claim_permitted"],
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_dir": str(dataset_dir),
        "datasets_total": len(datasets),
        "by_watcher": dict(sorted(by_watcher.items())),
        "by_maturity": dict(sorted(by_maturity.items())),
        "by_role": dict(sorted(by_role.items())),
        "by_multiplier_status": dict(sorted(by_multiplier_status.items())),
        "by_matrix_status": dict(sorted(matrix_status_counts.items())),
        "indicators_total": indicators_total,
        "impact_claims_permitted": impact_claims_permitted,
        "datasets": datasets,
        "honest_limits": [
            "MATRIZ != WIRKUNG; ein Messkriterium ist keine gemessene Wirkung.",
            "ZIELWERT != ERGEBNIS; Ziele sind Verpflichtungen, keine Resultate.",
            "INDEX != BEWERTUNG; dieses Modul aggregiert nur.",
            "AGGREGATION != PRIORITAET; Reihenfolge bleibt menschliche Entscheidung.",
            "UNKNOWN bleibt UNKNOWN; der Index verifiziert nirgends unabhaengig.",
            "Fail-closed: ein ungueltiges Dataset ungueltigt den ganzen Lauf.",
        ],
    }


def main(argv=None) -> int:
    """CLI: baut den Index ueber docs/messmatrix (Exit 0) oder schlaegt
    fail-closed durch (Exit 2). Exit 1 (Verdict-Signal) gibt es hier nicht:
    der Index bewertet nicht."""
    parser = argparse.ArgumentParser(description="Build deterministic messmatrix index")
    parser.add_argument("--dataset-dir", default=DEFAULT_DATASET_DIR)
    args = parser.parse_args(argv)
    try:
        index = build_index(Path(args.dataset_dir))
    except MessmatrixIndexError as error:
        print(f"messmatrix-index error: {error}", file=sys.stderr)
        return 2
    json.dump(index, sys.stdout, indent=2, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
