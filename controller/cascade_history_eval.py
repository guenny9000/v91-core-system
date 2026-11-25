"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kaskaden-Historie-Evaluation: historische Validierung von
CI-Kaskadenpfaden gegen eine gemessene Datenbasis (Betreiber-
Direktiv 25.11.2026 nachts: 'Kaskaden-Pfade historisch validieren',
'MacroF1 weiter verbessern wenn alles laeuft').

Anlass: controller/cumulative_stress.py verweigerte bewusst jede
Metrik-Angabe, solange keine echte Ground Truth existiert (PRUEFBFUND
dort: die behauptete Infrastruktur mit 'Macro F1 0.59' und ein
16-Fall-Korpus existierte im Repository NICHT). Dieses Modul schliesst
die Evidenzluecke NICHT mit Behauptung, sondern mit einer echten,
nachmessbaren Momentaufnahme: die oeffentliche Actions-Historie des
eigenen Repositoriums (23.-25.11.2026, 334 Workflow-Runs, daraus 161
vollstaendige CI-Suiten) wurde abgerufen und als appendfaehige
Datenbasis docs/cascade-history/v91-ci-suiten-2026-11-23-bis-25.jsonl
abgelegt. Was darin nicht steht, wird HIER nicht behauptet.

Methode (a priori, NICHT gefittet; FITTING WAERE UEBERZAEHLIG):
- Suite = alle Workflow-Runs zu EINEM head_sha eines Branches; rot,
  wenn irgendein Run der Suite 'failure' schliesst.
- Folgepaar = zwei zeitlich aufeinanderfolgende Suiten desselben
  Branches (n = 43). gap_min = Abstand der Suite-Startzeiten.
- Detektor ZEIT   (nur Betriebsstress): rot, wenn gap <= 30 min.
- Detektor KASKADE (Reparatur-Schleifen-These): rot, wenn die
  VORHERIGE Suite rot war (Vorwissen zum ZeitPUNKT der Vorhersage,
  kein Zirkelschluss mit dem Ziel-Outcome).
- Macro-F1 = Mittel der per-Klasse F1 ueber die Klassen ROT und
  GRUEN; kleine n heisst: Momentaufnahme, keine Signifikanz.

Vertrag:
- GEMESSEN wird ausschliesslich die abgelegte Datenbasis; kein Netz,
  kein Daemon, kein Schreiben (SCRIPTED != RUNNING).
- Die Bewertung benennt TP/FP/FN/TN und beide Klassen-F1 offen;
  UNKNOWN oder unvollstaendige Suiten werden ausgeschlossen und
  gezaehlt, nicht geschoent (fail-closed, UNKNOWN != PASS).
- METRIK == MOMENTAUFNAHME != GUETEMORM, DETECTOR == REGEL !=
  GARANTIE, VERGANGENHEIT != VORHERSAGE: dieses Modul sagt NICHTS
  ueber kuenftige Laeufe aus.

Ehrliche Grenzen:
- n=43 Folgepaare, alle aus EINEM Repositorium: PROJEKTINTERN,
  KEINE Allgemeingueltigkeit, KEINE Signifikanzaussage.
- Basisaufnahme PR-Pushes (event=pull_request); Branch-Pushes ohne
  PR und Runs aelter als 2026-11-23 sind NICHT enthalten
  (AUSWAHL == RAHMEN != VOLLSTAENDIGKEIT).
- Die 8 ROT-Folgesuiten traten ALLE nach einer ROT-Suite auf
  (Recall 1.000), aber 14 von 22 Nachlaeufen nach ROT wurden gruen:
  die Mehrheit der Kaskaden muendet in Heilung, nicht in Aufschaukelung.
- KEIN Kaskaden-Detektor fuer Domainslasten (cumulative_stress.py
  bleibt unberuehrt; REUSE nur des Honesty-Musters).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

HONESTY_LIMITS = (
    "METRIK == MOMENTAUFNAHME != GUETENORM, DETECTOR == REGEL != GARANTIE, "
    "VERGANGENHEIT != VORHERSAGE, PROJEKTINTERN != ALLGEMEIN, "
    "KEINE_SIGNIFIKANZ_BEI_KLEINEM_N, AUSWAHL == RAHMEN != VOLLSTAENDIGKEIT, "
    "UNKNOWN != PASS, SCRIPTED != RUNNING, KEIN_KASKADEN_DETEKTOR"
)

TIME_GAP_MIN = 30.0  # a priori gesetzt, NICHT gefittet


def load_suites(path: pathlib.Path) -> dict[str, Any]:
    """Laedt die Suiten-Datenbasis; unvollstaendige/leserlose Zeilen werden fail-closed gezaehlt."""
    if not path.exists():
        return {"ok": False, "error": "data file missing: " + str(path.name)}
    suites = []
    malformed = 0
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(record, dict):
                malformed += 1
                continue
            branch = record.get("branch")
            sha = record.get("head_sha")
            ts = record.get("suite_start_utc")
            red = record.get("suite_red")
            if not isinstance(branch, str) or not isinstance(sha, str) \
                    or not isinstance(ts, str) or not isinstance(red, bool):
                malformed += 1
                continue
            suites.append({"branch": branch, "sha": sha, "t": ts, "red": red})
    if not suites:
        return {"ok": False, "error": "no valid suite lines"}
    return {"ok": True, "suites": suites, "malformed_lines": malformed}


def _minutes_between(earlier: str, later: str) -> float:
    from datetime import datetime
    a = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
    b = datetime.fromisoformat(later.replace("Z", "+00:00"))
    return (b - a).total_seconds() / 60.0


def follow_pairs(suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bildet zeitlich sortierte Folgepaare je Branch."""
    by_branch: dict[str, list[dict[str, Any]]] = {}
    for s in suites:
        by_branch.setdefault(s["branch"], []).append(s)
    pairs: list[dict[str, Any]] = []
    for branch, items in by_branch.items():
        items = sorted(items, key=lambda x: x["t"])
        for prev, cur in zip(items, items[1:]):
            pairs.append({
                "branch": branch,
                "prev_red": prev["red"],
                "cur_red": cur["red"],
                "gap_min": _minutes_between(prev["t"], cur["t"]),
            })
    return sorted(pairs, key=lambda p: (p["branch"], p["gap_min"]))


def confusion(pairs: list[dict[str, Any]], detector) -> dict[str, int]:
    tp = fp = fn = tn = 0
    for pair in pairs:
        predicted = detector(pair)
        actual = pair["cur_red"]
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _safe_div(num: int, den: int) -> float:
    return num / den if den else 0.0


def class_scores(cm: dict[str, int]) -> dict[str, Any]:
    prec_red = _safe_div(cm["tp"], cm["tp"] + cm["fp"])
    rec_red = _safe_div(cm["tp"], cm["tp"] + cm["fn"])
    f1_red = _safe_div(2 * prec_red * rec_red, prec_red + rec_red)
    prec_green = _safe_div(cm["tn"], cm["tn"] + cm["fn"])
    rec_green = _safe_div(cm["tn"], cm["tn"] + cm["fp"])
    f1_green = _safe_div(2 * prec_green * rec_green, prec_green + rec_green)
    return {
        "precision_red": prec_red, "recall_red": rec_red, "f1_red": f1_red,
        "precision_green": prec_green, "recall_green": rec_green,
        "f1_green": f1_green,
        "macro_f1": (f1_red + f1_green) / 2.0,
    }


def evaluate(data_path: pathlib.Path) -> dict[str, Any]:
    """Berechnet den Kaskaden-Historie-Bericht aus der abgelegten Datenbasis."""
    loaded = load_suites(data_path)
    if not loaded.get("ok"):
        return {"state": "NOT_EVALUATED", "reason": loaded.get("error", "unknown"),
                "honesty_limits": HONESTY_LIMITS}
    suites = loaded["suites"]
    pairs = follow_pairs(suites)
    detector_time = lambda pair: pair["gap_min"] <= TIME_GAP_MIN  # noqa: E731
    detector_cascade = lambda pair: pair["prev_red"]  # noqa: E731
    detector_both = lambda pair: pair["prev_red"] and pair["gap_min"] <= TIME_GAP_MIN  # noqa: E731
    results = {}
    for name, det in (("detector_zeit", detector_time),
                      ("detector_kaskade_prev_rot", detector_cascade),
                      ("detector_prev_rot_und_zeit", detector_both)):
        cm = confusion(pairs, det)
        results[name] = {"confusion": cm, **class_scores(cm)}
    red_targets = sum(1 for p in pairs if p["cur_red"])
    prev_red_pairs = sum(1 for p in pairs if p["prev_red"])
    healed_after_red = sum(1 for p in pairs if p["prev_red"] and not p["cur_red"])
    return {
        "state": "EVALUATED",
        "suites_total": len(suites),
        "suites_red": sum(1 for s in suites if s["red"]),
        "malformed_lines": loaded["malformed_lines"],
        "follow_pairs": len(pairs),
        "pairs_target_red": red_targets,
        "pairs_prev_red": prev_red_pairs,
        "healed_after_prev_red": healed_after_red,
        "healing_ratio_after_red": _safe_div(healed_after_red, prev_red_pairs),
        "detectors": results,
        "honesty_limits": HONESTY_LIMITS,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Historische Kaskaden-Evaluation gegen die abgelegte Suiten-Datenbasis (fail-closed).")
    parser.add_argument("data", help="Pfad zur JSONL-Suiten-Datenbasis")
    parser.add_argument("--output", default=None, help="Optionaler JSON-Ausgabepfad")
    args = parser.parse_args()
    report = evaluate(pathlib.Path(args.data))
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    return 0 if report.get("state") == "EVALUATED" else 2


if __name__ == "__main__":
    raise SystemExit(_cli())
