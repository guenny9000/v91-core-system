"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Kern-Bridge: Lese-Bruecke fuer externe Beitraege ohne GitHub-Schreib-
zugang in EINEN lokalen append-only Ledger (Lernblock Weg B).

Anlass ist der externe Uebergabe-Entwurf der siebten Welle
(Onboarding-Lernblock mit Bridge-Parser-Idee) vom 24.11.2026.
Tragfaehige Kernidee: externe Modelle oder der Betreiber legen
strukturierte Kerne in offenen GitHub-Issues mit Bridge-Label ab;
ein deterministisches, stdlib-only Skriptholt sie als ROHSTOFF ab,
praegt SHA-256-Nachweise und schreibt sie append-only weg - nichts
wird verworfen,alles wird nachmessbar abgelegt.

PRUEFBFUND vor dem Bau (CLAIM != EVIDENCE): Der Entwurf behauptet
Pruefung und Versiegelung fuer sich selbst; diese Angaben sind
hier NACHGEMESSEN worden, nicht uebernommen (FREMDBEFUND !=
V91-MESSUNG, STATUSANGABE != EVIDENZ). Verschlossene
Verbesserungen gegenueber dem Entwurf: Quarantaene-Inhalte werden
NICHT durch einen Platzhalter ersetzt (ISOLATE_NOT_DESTROY statt
Verlust - der Ledger speichert den Rohstoff mit Statuskennung,
Auswertung und Aktivierung bleiben beim Betreiber), der Netz-Abruf
ist injizierbar (Tests laufen ohne Netz), und das Gate kennt
drei feste Zustandsnamen statt einem Pass-Wort.

Vertrag:
- GATE-Zustaende (fix): ACCEPTED_ISOLATED [Marker vorhanden, kein
  Mustertreffer], BLOCKED_PATTERN [destruktives Muster erkannt,
  Inhalt bleibt gespeichert und isoliert], MISSING_HANDOVER_MARKER
  [Pflicht-Marker fehlt, Inhalt bleibt gespeichert].
- BLOCKLIST == MUSTER != GARANTIE: die Liste erkennt bekannte
  destruktive Formen, sie beweist NICHT die Unschaedlichkeit des
  Rests. Kein Makro-Scan, kein Sandbox-Run: dieses Modul evaluert
  KEINEN fremden Code und fuehrt ihn NIEMALS aus.
- Ledger: append-only JSONL, eine Zeile pro Kern, sha256 ueber den
  Rohtext, Dedup gegen vorhandene SHA-Werte, fsync nach jedem
  Schreiben. Schreibfehler brechen fail-closed ab. Dedup-Lesen UND Append stehen gemeinsam unter dem exklusiven Datei-Lock aus controller/ledger_lock.py (REUSE aus #529, der dort ehrlich offen dokumentierte Rest); der Netz-Abruf bleibt bewusst AUSSERHALB des Locks (kein Netz im kritischen Abschnitt). LOCK != BEWEIS: der Lock verhindert Interleaving, die Verifikation bleibt Massstab.
- KEIN Daemon, KEIN Timer, KEIN automatischer Lauf: der Abruf ist
  ein geplanter Schritt des Betreibers (SCRIPTED != RUNNING).
- Stufe-4-Screening (Bestandsaufnahme #492 nannte die fehlende
  Secret-/PII-Pruefung im Abrufpfad als LUECKE am Messstand
  26.11.2026; diese Erweiterung schliesst die Abruf-Seite): JEDE
  Aufnahme wird vor der Ablage durch controller/bridge_screening
  auf vertrauliche Muster geprueft (REUSE der Secret-Muster aus
  controller/secret_scan.py plus E-Mail/IBAN-Formen); Fundstellen
  werden im abgelegten Text durch [REDACTIERT] ersetzt, der
  SHA-256-Nachweis bleibt eine Hashung ueber den ROHTEXT, und das
  Gate (drei feste Zustaende) bleibt davon UNBERUEHRT (GATE !=
  SCREENING: ein Secret ist kein destruktives Muster und umgekehrt).
  Details und Grenzen: docs/V91-BRIDGE-SECRET-SCREENING-2026-11-26.md.

Ehrliche Grenzen:
- ABGEHOLT != GEPRUEFT: der Ledger beweist nur Aufnahme und Hash,
  niemals Korrektheit, Lauffaehigkeit oder Wahrheit des Inhalts
  (AUFGENOMMEN != VERIFIZIERT).
- Auf Systemen ohne fcntl/msvcrt gilt wie beim Lock-Baustein der
  prozesslokale schwache Fallback (ehrlich dokumentiert, KEIN stiller Erfolg).
- Der GitHub-Abruf selbst liegt ausserhalb dieser Messung: er
  liefert, was die API liefert; Ausfaelle brechen fail-closed ab
  (UNKNOWN != PASS).
- Herzustellende Integration: das Issue-Template
  .github/ISSUE_TEMPLATE/kern-bridge.md passt zu den Markern hier;
  Template und Skript ändern KEINE Rechte (Feld erteilt keine
  Berechtigung), Leerraum-Antwort ohne Marker bleibt abgelegt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from controller.ledger_lock import exclusive_ledger_lock
from controller.bridge_screening import (
    SCREENING_HONESTY_LIMITS,
    SCREENING_STATUS_CLEAN,
    SCREENING_STATUS_REDACTED,
    screen_text,
)

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DEFAULT_REPO = "guenny9000/v91-core-system"
BRIDGE_LABEL = "v91-bridge"
LEDGER_FILENAME = "v91_bridge_inbox.jsonl"

# Pflicht-Marker des Uebergabe-Formats (Template-kompatibel).
HANDOVER_MARKER = "UEBERGABE_KERN_START"
HANDOVER_END_MARKER = "UEBERGABE_KERN_ENDE"

# Bekannte destruktive Muster (BLOCKLIST == MUSTER != GARANTIE).
BLOCKLIST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rm_dash_rf", re.compile(r"\brm\s+-rf\b")),
    ("shutil_rmtree", re.compile(r"\bshutil\s*\.\s*rmtree\b")),
    ("os_system", re.compile(r"\bos\s*\.\s*system\b")),
    ("subprocess", re.compile(r"\bsubprocess\b")),
    ("eval_call", re.compile(r"\beval\s*\(")),
    ("exec_call", re.compile(r"\bexec\s*\(")),
    ("dunder_import", re.compile(r"__import__")),
)

GATE_ACCEPTED = "ACCEPTED_ISOLATED"
GATE_BLOCKED = "BLOCKED_PATTERN"
GATE_MISSING_MARKER = "MISSING_HANDOVER_MARKER"

HONESTY_LIMITS = (
    "ABGEHOLT != GEPRUEFT, AUFGENOMMEN != VERIFIZIERT, "
    "BLOCKLIST == MUSTER != GARANTIE, KEIN Code-Ausfuehrung, "
    "KEIN Daemon, KEIN Timer, SCRIPTED != RUNNING, "
    "FELD_ERTEILT_KEINE_BERECHTIGUNG, ISOLATE_NOT_DESTROY, "
    "GATE != SCREENING, " + SCREENING_HONESTY_LIMITS
)

FetchFn = Callable[[str, str], list[dict[str, Any]]]


def _default_fetch(repo: str, label: str) -> list[dict[str, Any]]:
    """Echter Abruf offener Bridge-Issues (nur fuer Betreiber-Laefe)."""
    url = "https://api.github.com/repos/" + repo + "/issues?labels=" + label + "&state=open"
    req = urllib.request.Request(url, headers={"User-Agent": "V91-kern-bridge/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("GitHub-API-Antwort ist keine Liste (UNKNOWN != PASS)")
    return payload


def gate_payload(body: str) -> str:
    """Klassifiziert EINEN Rohtext; gibt EINEN festen GATE-Zustand zurueck."""
    if not isinstance(body, str):
        return GATE_MISSING_MARKER
    for name, pattern in BLOCKLIST_PATTERNS:
        if pattern.search(body):
            return GATE_BLOCKED
    if HANDOVER_MARKER not in body:
        return GATE_MISSING_MARKER
    return GATE_ACCEPTED


def _existing_hashes(ledger: pathlib.Path) -> set[str]:
    hashes: set[str] = set()
    if not ledger.exists():
        return hashes
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        digest = record.get("sha256")
        if isinstance(digest, str) and digest:
            hashes.add(digest)
    return hashes


def collect_kerns(
    ledger_path: pathlib.Path,
    repo: str = DEFAULT_REPO,
    label: str = BRIDGE_LABEL,
    fetch: FetchFn | None = None,
) -> dict[str, Any]:
    """Holt Bridge-Issues einmal ab und schreibt neue Kerne append-only.

    Return-Bericht enthaelt Zaehlungen; Ausnahmen (Netz, Schreiben)
    brechen ab - fail-closed, kein Teil-Erfolg.
    """
    fetch_fn = fetch if fetch is not None else _default_fetch
    issues = fetch_fn(repo, label)
    if not isinstance(issues, list):
        raise ValueError("Abruf-Ergebnis ist keine Liste (FAIL-CLOSED)")

    report: dict[str, Any] = {
        "repo": repo,
        "label": label,
        "issues_seen": len(issues),
        "records_new": 0,
        "records_known": 0,
        "gate_counts": {GATE_ACCEPTED: 0, GATE_BLOCKED: 0, GATE_MISSING_MARKER: 0},
        "screening_counts": {SCREENING_STATUS_CLEAN: 0, SCREENING_STATUS_REDACTED: 0},
        "honesty_limits": HONESTY_LIMITS,
    }

    # Dedup-Lesen und Append bilden EINEN kritischen Abschnitt unter dem
    # exklusiven Datei-Lock (REUSE controller/ledger_lock.py; der in #529
    # ehrlich offen dokumentierte Rest ist damit geschlossen). Der
    # Netz-Abruf bleibt bewusst AUSSERHALB des Locks.
    with exclusive_ledger_lock(ledger_path):
        known = _existing_hashes(ledger_path)
        new_records: list[dict[str, Any]] = []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            body = issue.get("body")
            body = body if isinstance(body, str) else ""
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if digest in known:
                report["records_known"] += 1
                continue
            known.add(digest)
            status = gate_payload(body)
            screening = screen_text(body)
            new_records.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "issue_number": issue.get("number"),
                "title": issue.get("title"),
                "repo": repo,
                "sha256": digest,
                "gate_status": status,
                "screening_status": screening["status"],
                "screening_findings": screening["findings"],
                "payload": screening["redacted_text"],
            })
            report["gate_counts"][status] = report["gate_counts"].get(status, 0) + 1
            report["screening_counts"][screening["status"]] = (
                report["screening_counts"].get(screening["status"], 0) + 1
            )

        if new_records:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(ledger_path, "a", encoding="utf-8") as handle:
                for record in new_records:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                    import os as _os
                    _os.fsync(handle.fileno())
    report["records_new"] = len(new_records)
    return report


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Kern-Bridge: holt externe Beitraege (Issues mit Bridge-Label) in einen append-only Ledger (Weg B des Lernblocks), fail-closed.")
    parser.add_argument("ledger", help="Pfad zur JSONL-Ledger-Datei (append-only)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Repository (owner/name)")
    parser.add_argument("--label", default=BRIDGE_LABEL, help="Bridge-Label der Issues")
    parser.add_argument("--output", default=None, help="Optionaler JSON-Bericht-Ausgabepfad")
    args = parser.parse_args()

    try:
        report = collect_kerns(pathlib.Path(args.ledger), args.repo, args.label)
    except Exception as exc:  # Netz-, API- oder Schreibfehler: fail-closed
        print("KERN-BRIDGE FEHLER (fail-closed): " + str(exc))
        return 2
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    # exit 0: Lauf durchgefuehrt (Aufnahme ist KEINE Verifikation);
    # exit 2: Abruf oder Schreiben abgebrochen. Kein Teil-Erfolg.
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
