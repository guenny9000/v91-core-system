"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schoepfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kreislauf-Status fuer Initiativen (VIBE-LXX).

Umsetzung des MONITORING-Schritts aus dem verbindlichen Dokument
docs/V91-MAX-BEST-KREISLAUF-ENTSCHEIDUNGSFILTER.md (PR #361):
Kreislauf MOEGLICHKEIT -> PRUEFUNG -> NACHWEIS -> NUTZEN ->
MONITORING -> VERBESSERUNG -> ERNEUTE PRUEFUNG.

Dieses Modul ordnet EINE Initiative (Messmatrix-Dataset nach
docs/messmatrix-Schema, PR #215 ff.) strikt datengestuetzt den
Kreislauf-Phasen zu. Phase ist nur BELEGT, wenn die passende
Evidenz in den GELIEFERTEN Dateien steht, sonst NICHT_GEPRUEFT
(UNKNOWN != PASS, BEHAUPTUNG != BELEGT).

Ehrliche Grenzen dieses Moduls:
- STATUS != FORTSCHRITT: dieses Modul zaehlt Phasen-Evidenz, es
  bewertet NICHT, ob gemessene Wirkung 'gut' ist (VALUES != URTEIL).
- KETTE_UNGEPRUEFT: die SHA-256-Kette des R3-Ledgers wird hier
  NICHT nachgerechnet (das bleibt controller.messwerte_ingest;
  SIGNATUR != WAHRHEIT, STRUKTUR != KETTE). Eintragsexistenz ist
  Lesen, kein Kettennachweis (GELESEN != VERIFIZIERT).
- TREND != URSACHE: die VERBESSERUNG-Phase prueft einen gerichteten
  Zahlenverlauf, nie eine Ursache-Wirkung.
- KEIN ZWEIT-REGISTER (NO_DUPLICATE_SYSTEMS): dieses Modul erzeugt
  keine truth-Dateien; der Report ist FIFO-Ausgabe, keine Instanz.
- SCRIPTED != INSTALLED: kein Daemon, kein Taskplaner, kein Netz,
  keine Credentials, reine Standardbibliothek.
- REVIEW != ENTSCHEIDUNG: der Status autorisiert nichts.

Datengrundlage (fail-closed):
- Dataset: JSON mit initiative_id und nicht-leerer indicators-Liste
  (role/name/baseline/target, period darf je Indikator fehlen: die
  PRUEFUNG-Phase meldet dann ehrlich NICHT_GEPRUEFT).
- Ledger: JSONL nach docs/ledgers/README.md; jede Zeile initiative_id,
  indicator, value, measured_at, source (notwendige Pflicht-
  felder). Kaputte Zeilen sind INPUT_ERROR, niemals still ueber-
  lesen (KEINE_STUMME_KORREKTUR).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BELEGT = "BELEGT"
NICHT_GEPRUEFT = "NICHT_GEPRUEFT"

PHASEN = [
    "MOEGLICHKEIT",
    "PRUEFUNG",
    "NACHWEIS",
    "NUTZEN",
    "MONITORING",
    "VERBESSERUNG",
]

INDICATOR_FIELDS = ("role", "name", "baseline", "target")
PRUEFUNG_FIELDS = ("method", "verifier", "period")

EXIT_ALLE_BELEGT, EXIT_OFFENE_PHASEN, EXIT_INPUT_ERROR = 0, 1, 3

class KreislaufInputError(ValueError):
    """Fail-closed fuer unbrauchbare Eingabedaten (SCRIPTED != GELESEN)."""

def load_dataset(path: Path) -> Dict[str, Any]:
    """Laedt ein Messmatrix-Dataset; strikt fail-closed."""
    if not path.is_file():
        raise KreislaufInputError("dataset fehlt: %s" % path)
    try:
        with path.open("r", encoding="ascii") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise KreislaufInputError("dataset kein gueltiges JSON: %s" % exc) from exc
    for field in ("initiative_id", "indicators"):
        if field not in data:
            raise KreislaufInputError("dataset fehlt feld %r" % field)
    if not isinstance(data["indicators"], list) or not data["indicators"]:
        raise KreislaufInputError(
            "dataset indicators leer: KEIN_INDIKATOR != MESSUNG_ERZWINGEN")
    for idx, ind in enumerate(data["indicators"]):
        if not isinstance(ind, dict):
            raise KreislaufInputError("indikator %d ist kein objekt" % idx)
    return data

def load_ledger(path: Optional[Path],
                initiative_id: str) -> List[Dict[str, Any]]:
    """Laedt Ledger-Eintraege EINER Initiative; kaputte Zeilen sind
    Fehler, nie stille Korrektur (KEINE_STUMME_KORREKTUR)."""
    if path is None:
        return []
    if not path.is_file():
        raise KreislaufInputError("ledger fehlt: %s" % path)
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="ascii") as handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise KreislaufInputError(
                    "ledger zeile %d kaputt: %s" % (lineno, exc)) from exc
            if not isinstance(entry, dict):
                raise KreislaufInputError(
                    "ledger zeile %d ist kein objekt" % lineno)
            for field in ("initiative_id", "indicator", "value",
                          "measured_at", "source"):
                if field not in entry:
                    raise KreislaufInputError(
                        "ledger zeile %d fehlt pflichtfeld %r" % (lineno, field))
            if entry["initiative_id"] != initiative_id:
                continue
            entries.append(entry)
    return entries

def assess(dataset: Dict[str, Any],
           ledger_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phasen-Verdict je Initiative, rein aus gelieferten Daten."""
    indicators = dataset["indicators"]
    phases: Dict[str, Dict[str, Any]] = {}

    # --- MOEGLICHKEIT: definierte Indikatoren existieren ----------------
    phases["MOEGLICHKEIT"] = {
        "verdict": BELEGT,
        "indikatorzahl": len(indicators),
        "grund": "dataset definiert %d indikatoren (R2-Messmatrix)"
                 % len(indicators),
    }

    # --- PRUEFUNG: je Indikator methode/verifier/zeitfenster komplett ---
    incomplete = [
        ind.get("name", "<ohne name>")
        for ind in indicators
        if not all(f in ind and ind[f] not in (None, "", {})
                   for f in INDICATOR_FIELDS + PRUEFUNG_FIELDS)
    ]
    phases["PRUEFUNG"] = {
        "verdict": BELEGT if not incomplete else NICHT_GEPRUEFT,
        "unvollstaendige_indikatoren": incomplete,
        "grund": ("alle indikatoren mit method/verifier/period komplett"
                  if not incomplete else
                  "%d indikatoren ohne vollstaendige pruefmethodik"
                  % len(incomplete)),
    }

    # --- NACHWEIS: mind. ein Ledger-Eintrag zu einem echten Indikator ---
    names = {ind.get("name") for ind in indicators}
    matched = [e for e in ledger_entries if e["indicator"] in names]
    fremd = sorted({e["indicator"] for e in ledger_entries
                    if e["indicator"] not in names})
    phases["NACHWEIS"] = {
        "verdict": BELEGT if matched else NICHT_GEPRUEFT,
        "eintraege_passend": len(matched),
        "fremdindikatoren": fremd,
        "kette_ungeprueft": True,
        "grund": ("%d ledger-eintraege zu definierten indikatoren"
                  % len(matched)) if matched else
                 "kein ledger-eintrag zu einem definierten indikator",
    }

    # --- NUTZEN: mind. ein WIRKUNG-Wert ueber baseline ------------------
    wirkungs_indikatoren = [
        ind for ind in indicators if str(ind.get("role", "")).upper() == "WIRKUNG"
    ]
    nutzen_werte: List[float] = []
    for ind in wirkungs_indikatoren:
        baseline = ind.get("baseline", 0.0)
        for e in matched:
            if e["indicator"] == ind["name"]:
                try:
                    wert = float(e["value"])
                except (TypeError, ValueError):
                    continue
                if wert > float(baseline):
                    nutzen_werte.append(wert)
    phases["NUTZEN"] = {
        "verdict": BELEGT if nutzen_werte else NICHT_GEPRUEFT,
        "werte_ueber_baseline": len(nutzen_werte),
        "grund": ("mind. ein WIRKUNG-wert ueber baseline beobachtet"
                  if nutzen_werte else
                  "kein WIRKUNG-wert ueber baseline (OBSERVED != ERFOLG)"),
    }

    # --- MONITORING: wiederholte Messung desselben Indikators -----------
    je_indikator_zeiten: Dict[str, set] = {}
    for e in matched:
        je_indikator_zeiten.setdefault(e["indicator"], set()).add(
            str(e["measured_at"]))
    monitoring = [
        name for name, zeiten in je_indikator_zeiten.items()
        if len(zeiten) >= 2
    ]
    phases["MONITORING"] = {
        "verdict": BELEGT if monitoring else NICHT_GEPRUEFT,
        "indikatoren_wiederholt": monitoring,
        "grund": ("%d indikatoren mit mind. 2 messzeitpunkten"
                  % len(monitoring)) if monitoring else
                 "kein indikator mit wiederholter messung",
    }

    # --- VERBESSERUNG: gerichteter Verlauf WIRKUNG/RESILIENZ ------------
    verbesserung = False
    verlauf_name: Optional[str] = None
    for ind in indicators:
        if str(ind.get("role", "")).upper() not in ("WIRKUNG", "RESILIENZ"):
            continue
        werte: List[float] = []
        for e in matched:
            if e["indicator"] != ind["name"]:
                continue
            try:
                werte.append(float(e["value"]))
            except (TypeError, ValueError):
                continue
        if len(werte) >= 2 and werte[-1] > werte[0]:
            verbesserung = True
            verlauf_name = ind["name"]
            break
    phases["VERBESSERUNG"] = {
        "verdict": BELEGT if verbesserung else NICHT_GEPRUEFT,
        "verlauf_indikator": verlauf_name,
        "grund": ("gerichteter anstieg bei %s (TREND != URSACHE)"
                  % verlauf_name) if verbesserung else
                 "kein gerichteter verlauf beobachtet (LERNEN > DOGMA: "
                 "ausbleiben ist kein scheitern des kreislaufs)",
    }

    offene = [p for p in PHASEN if phases[p]["verdict"] != BELEGT]
    return {
        "initiative_id": dataset.get("initiative_id"),
        "phasen": {p: phases[p] for p in PHASEN},
        "offene_phasen": offene,
        "erneute_pruefung": "PFLICHT nach jedem MERGE von neuer Evidenz",
        "grenzen": "STATUS != FORTSCHRITT; GELESEN != VERIFIZIERT "
                   "(KETTE_UNGEPRUEFT); TREND != URSACHE; REVIEW != "
                   "ENTSCHEIDUNG; SCRIPTED != INSTALLED",
    }

def format_text_report(report: Dict[str, Any]) -> str:
    """Lesbarer, ASCII-purer, deterministischer Bericht."""
    lines = [
        "V91 Kreislauf-Status (Kreislauf-Dokument PR #361)",
        "initiative : %s" % report["initiative_id"],
        "",
    ]
    for phase in PHASEN:
        block = report["phasen"][phase]
        lines.append("%-12s: %s" % (phase, block["verdict"]))
        lines.append("              %s" % block["grund"])
    lines.append("")
    lines.append("offene phasen  : %s"
                 % (", ".join(report["offene_phasen"]) or "keine"))
    lines.append("grenze        : %s" % report["grenzen"])
    return "\n".join(lines) + "\n"

def _write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = str(report["initiative_id"])
    (out_dir / ("kreislauf_%s.txt" % stem)).write_text(
        format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=True) + "\n"
    (out_dir / ("kreislauf_%s.json" % stem)).write_text(
        payload, encoding="ascii")

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Kreislauf-Status je Initiative (advisory, REPORT != ENTSCHEIDUNG)")
    parser.add_argument("dataset", help="Messmatrix-Dataset (JSON)")
    parser.add_argument("--ledger", default=None,
                        help="R3-Ledger der Initiative (JSONL, optional)")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(Path(args.dataset))
        eintraege = load_ledger(
            Path(args.ledger) if args.ledger else None,
            dataset["initiative_id"])
        report = assess(dataset, eintraege)
    except KreislaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    if report["offene_phasen"]:
        return EXIT_OFFENE_PHASEN
    return EXIT_ALLE_BELEGT


if __name__ == "__main__":
    sys.exit(main())
