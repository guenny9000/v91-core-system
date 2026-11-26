"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Alarm-Outbox RESTORE-DRILL (Issue #520-Rest): geplanter, ehrlicher
Nachweis, dass eine wiederhergestellte v91_alarm_outbox.jsonl ihre
Semantik behaelt. Der Drill liest die echte Outbox NUR lesend und
arbeitet ausschliesslich auf Kopien im Arbeitsverzeichnis.

Was der Drill misst (alle Sonden an Kopien, nie an der Quelle):
- KOPIE: Byteweise Kopie wiederherstellen (Datei-Restore-Simulation).
- ZUSTAND: Je bekannter event_id bleibt der Zustand (state/retry_count)
  nach dem Restore identisch zur Quelle.
- DEDUP: Das erneute Anlegen eines bekannten Ereignisses bleibt
  BEREITS_BEKANNT (kein Doppelversand-Pfad durch Restore).
- APPEND: Die wiederhergestellte Outbox bleibt append-faehig; ein
  Uebergang haengt GENAU EINE Zeile an (append-only bleibt intakt).
- FAIL-CLOSED: Eine veraenderte/truncierte Kopie wird abgelehnt
  (DETECTION != BEHEBUNG; korrupte Bytes bleiben KOPIE-lokal erhalten).

Vertrag (fail-closed, REUSE, KEINE zweite Logik):
- Alle Operationen via controller/alarm_outbox.py (create_event,
  record_transition, read_state, event_id_from) und deren
  _load_records_locked-Fehler; KEIN zweiter Parser, KEIN zweiter Lock.
- Die QUELL-Outbox wird niemals geschrieben (read-only).
- VERDICT = PASS nur wenn ALLE Sonden bestehen; sonst FAIL mit Gruenden.
- Screening: payload-inhalte bleiben vom alarm_outbox-Redakteur gedeckt.

Ehrliche Grenzen (bewusst, keine Luecken):
- DRILL != ECHTER BETRIEBS-RESTORE: file copy ohne Kompression/
  Verschluesselung/FS-Snapshot; Betreiber-Hardware NICHT_GEPRUEFT.
- SCRIPTED != INSTALLED: kein Daemon, kein Timer, kein Netz.
- DEAD_LETTER/CANCELLED bleiben auditierbar liegen (ISOLATE_NOT_DESTROY).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:  # Paket-Import (Tests/CI starten ab Wurzel)
    from controller.alarm_outbox import (
        AlarmOutboxError,
        create_event,
        event_id_from,
        read_state,
        record_transition,
    )
except ImportError:  # Direkt-Import (Aufruf aus controller/)
    from alarm_outbox import (  # type: ignore[no-redef]
        AlarmOutboxError,
        create_event,
        event_id_from,
        read_state,
        record_transition,
    )

SCHEMA_RESULT = "v91.alarm_outbox_restore_drill.result.v1"


def _require_now(now: Any) -> datetime.datetime:
    if isinstance(now, str):
        try:
            parsed = datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AlarmOutboxError("now must be an ISO-8601 string or datetime") from exc
    elif isinstance(now, datetime.datetime):
        parsed = now
    else:
        raise AlarmOutboxError("now must be an ISO-8601 string or datetime")
    if parsed.tzinfo is None:
        raise AlarmOutboxError("now must be timezone-aware")
    return parsed


def _line_count(path: pathlib.Path) -> int:
    """Zeilenzahl mit sauber geschlossenem Handle (KEIN ResourceWarning)."""
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _known_event_ids(path: pathlib.Path) -> List[str]:
    """Bekannte event_ids aus Event-Zeilen (nur lesend, REUSE des Parsers-Formats)."""
    ids: List[str] = []
    if not path.exists():
        return ids
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            if rec.get("schema") == "v91.alarm_outbox.event.v1" and rec.get("event_id") not in ids:
                ids.append(rec["event_id"])
    return ids


def run_restore_drill(
    outbox_path: Any,
    now: Any,
    workdir: Optional[Any] = None,
) -> Dict[str, Any]:
    """Restore-Drill ueber Kopien; Quelle bleibt unveraendert (read-only)."""
    now_dt = _require_now(now)
    source = pathlib.Path(outbox_path)
    if not source.exists():
        raise AlarmOutboxError("outbox path does not exist; nothing to restore-check")

    own_tmp = False
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="v91_outbox_restore_drill_")
        own_tmp = True
    work = pathlib.Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    reasons: List[str] = []
    counts: Dict[str, int] = {"events_geprueft": 0, "sonden_ok": 0, "sonden_gesamt": 4}

    # SONDE 1: ZUSTANDS-TREUE nach Restore (Byte-Kopie).
    restored = work / "restored_v91_alarm_outbox.jsonl"
    shutil.copyfile(source, restored)
    state_ok = source_ok = True
    for event_id in _known_event_ids(source):
        counts["events_geprueft"] += 1
        try:
            vor = read_state(source, event_id)
            nach = read_state(restored, event_id)
        except AlarmOutboxError:
            state_ok = False
            reasons.append(f"zustand: read_state schlug fehl fuer {event_id}")
            continue
        if (vor.get("state"), vor.get("retry_count")) != (nach.get("state"), nach.get("retry_count")):
            state_ok = False
            reasons.append(f"zustand: abweichend nach Restore fuer {event_id}")
    source_ok = state_ok
    if state_ok:
        counts["sonden_ok"] += 1
    else:
        reasons.append("sonde zustandstreue: FEHLER")

    # SONDE 2: DEDUP bleibt wirksam nach Restore (kein Doppelversand-Pfad).
    dedup_ok = True
    for event_id in _known_event_ids(source):
        try:
            result = create_event(
                restored,
                {
                    "event_id": event_id,
                    "source_ref": "restore-drill::dedup-probe",
                    "severity": "INFO",
                    "begruendung": "Restore-Drill Dedup-Sonde",
                },
                now_dt,
            )
        except AlarmOutboxError as exc:
            # Kapazitaet/Ablehnung ist KEIN Dedup-Nachweis-Versagen,
            # aber ein unerwarteter Fehler zaehlt ehrlich als FEHLER.
            reasons.append(f"dedup: unerwarteter Fehler fuer {event_id}: {exc}")
            dedup_ok = False
            break
        if result.get("status") != "BEREITS_BEKANNT":
            dedup_ok = False
            reasons.append(f"dedup: {event_id} waere nach Restore neu angelegt worden")
            break
    if dedup_ok and counts["events_geprueft"] > 0:
        counts["sonden_ok"] += 1
    elif counts["events_geprueft"] == 0:
        reasons.append("dedup: keine Events vorhanden, Sonde ohne Aussage")

    # SONDE 3: APPEND bleibt moeglich, haengt GENAU EINE Zeile an.
    append_ok = False
    try:
        lines_before = _line_count(restored)
        first_id = _known_event_ids(source)[0] if _known_event_ids(source) else None
        if first_id is not None:
            record_transition(restored, first_id, "RETRY_VERPLANT", now_dt, retry_count=1)
            lines_after = _line_count(restored)
            append_ok = lines_after == lines_before + 1
            if not append_ok:
                reasons.append("append: zeilenzahl veraenderte sich um != 1")
        else:
            reasons.append("append: keine Events vorhanden, Sonde ohne Aussage")
    except AlarmOutboxError as exc:
        reasons.append(f"append: fehlgeschlagen: {exc}")
    if append_ok:
        counts["sonden_ok"] += 1

    # SONDE 4: FAIL-CLOSED gegenveraenderte Kopie (truncierter letzter Datensatz).
    corrupt_ok = False
    try:
        corrupt = work / "corrupt_v91_alarm_outbox.jsonl"
        data = source.read_bytes()
        if data:
            first_break = data.find(b"\n")
            last_break = data.rfind(b"\n")
            if 0 <= first_break < last_break:
                cut = first_break + 11  # mitten in die 2. Zeile
            else:
                cut = max(1, len(data) // 2)  # einzige Zeile, Mitte
            corrupt.write_bytes(data[:cut])
            try:
                read_state(corrupt, _known_event_ids(source)[0])
                reasons.append("fail-closed: truncierte Kopie wurde NICHT abgelehnt")
            except AlarmOutboxError:
                corrupt_ok = True
            except (IndexError, json.JSONDecodeError) as exc:
                reasons.append(f"fail-closed: unpassender Fehler: {exc!r}")
        else:
            reasons.append("fail-closed: leere Quelle, Sonde ohne Aussage")
    except OSError as exc:
        reasons.append(f"fail-closed: kopie-fehler: {exc}")
    if corrupt_ok:
        counts["sonden_ok"] += 1

    verdict = "PASS" if counts["sonden_ok"] == counts["sonden_gesamt"] else "FAIL"
    result: Dict[str, Any] = {
        "schema": SCHEMA_RESULT,
        "verdict": verdict,
        "quelle": str(source),
        "quelle_read_only": True,
        "events_geprueft": counts["events_geprueft"],
        "sonden": {
            "zustandstreue": "PASS" if state_ok else "FAIL",
            "dedup": "PASS" if dedup_ok and counts["events_geprueft"] > 0 else ("OHNE_AUSSAGE" if counts["events_geprueft"] == 0 else "FAIL"),
            "append": "PASS" if append_ok else "FAIL",
            "fail_closed": "PASS" if corrupt_ok else "FAIL",
        },
        "quell_zeilen_nach_drill": _line_count(source),
        "grenzen": {
            "drill": "DRILL != ECHTER BETRIEBS-RESTORE (file copy, ohne Kompression/Verschluesselung)",
            "hardware": "NICHT_GEPRUEFT (kein Betrieb auf Betreiber-Hardware in diesem Lauf)",
            "scripted_vs_installed": "SCRIPTED != INSTALLED",
        },
        "gruende": reasons,
        "zeitstempel": now_dt.isoformat(),
    }
    if own_tmp:
        shutil.rmtree(work, ignore_errors=True)
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="V91 Alarm-Outbox Restore-Drill (Issue #520-Rest; Quelle read-only)"
    )
    parser.add_argument("--self-check", action="store_true", help="synthetischer Selbsttest (SYNTHETISCH != MESSUNG)")
    parser.add_argument("--outbox", help="pfad zur echten v91_alarm_outbox.jsonl (read-only)")
    args = parser.parse_args(argv)
    if args.self_check:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "v91_alarm_outbox.jsonl"
            now = datetime.datetime(2026, 11, 26, 7, 0, 0, tzinfo=datetime.timezone.utc)
            eid = event_id_from("ledger::selfcheck", "versorgung", "2026-11-26T07:00:00Z")
            create_event(path, {
                "event_id": eid,
                "source_ref": "ledger::selfcheck",
                "severity": "WARNUNG",
                "begruendung": "synthetische Selbstpruefung Restore-Drill",
            }, now)
            result = run_restore_drill(path, now, workdir=pathlib.Path(tmp) / "drill")
            ok = result["verdict"] == "PASS" and result["events_geprueft"] == 1
            print(json.dumps({
                "mechanismus": "getestet",
                "echter_betriebs_restore": "NICHT_GEPRUEFT",
                "self_check": "PASS" if ok else "FEHLER",
                "verdict": result["verdict"],
                "sonden": result["sonden"],
            }, indent=2))
            return 0 if ok else 1
    if args.outbox:
        result = run_restore_drill(
            args.outbox, datetime.datetime.now(datetime.timezone.utc)
        )
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0 if result["verdict"] == "PASS" else 1
    print("usage: --self-check | --outbox PFAD", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
