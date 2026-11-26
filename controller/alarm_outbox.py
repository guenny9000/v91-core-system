"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Alarm-Outbox (Issue #520): dauerhafter, autorisierungspflichtiger
Alarm-Versandpfad als ERGAENZUNG zur read-only Notversorgungs-Bewertung
(controller/emergency_supply.py, PR #519). Dies ist hier NUR der
lokale Outbox-Kern: Ereignis anlegen, entduplizieren, Zustands-
uebergaenge fuehren, begrenzte Versandaufraege planen.

Vertrag (fail-closed, Issue #520-Anforderungen):
- NEUE DATEI v91_alarm_outbox.jsonl; KEIN Mischen mit der
  v91_bridge_inbox.jsonl der kern_bridge (getrennte Schemata,
  ISOLATE_NOT_DESTROY).
- Append-only unter exclusive_ledger_lock (REUSE controller/
  ledger_lock.py, keine zweite Lock-Logik): kritischer Abschnitt
  ist LESEN + SCHREIBEN.
- Zustandsuebergaenge sind EIGENE Anhaenge (append), niemals
  Rueckreiben von Zeilen (Outbox bleibt append-only).
- Korrumpierte Historie: Zeilen bleiben unveraendert erhalten
  (korrupte Zeilen werden dokumentiert, NICHT geloescht), jede
  Zustands-/Erzeugungsoperation verweigert fail-closed.
- Begrenzte Versuche: Exponential-Backoff mit Jitter (rng
  injizierbar, deterministisch pruefbar), harte Deadline,
  Storno -> CANCELLED, ersch. Versuche -> DEAD_LETTER. NIE endlos.
- Versandausfuehrung: NICHT Teil dieses Moduls. Delivery ist
  standardmaessig DEAKTIVIERT und benoetigt eine explizite
  Betreiber-Allowlist (HTTPS-Pflicht, Redirect-Ablehnung)
  bereits fuer die PLANUNG eines Versands. Kein Webhook, kein
  MoWaS/Cell-Broadcast/Drittanbieter (REQUEST != AUTHORIZATION,
  DETECTION != AUTHORIZATION).
- Datenminimierung: Personenbezogene-/Medizinfeldnamen werden
  abgelehnt; Geheimnis-artige Schluessel im klaren Zustelltext
  werden redigiert (KEIN Secret-Transport im Klartext).

Ehrliche Grenzen (bewusst, keine Luecken):
- SCRIPTED != INSTALLED; kein Daemon, kein Timer, kein Netzwerk.
- Einzelrechner-Lock (siehe ledger_lock.py); netzweite Sperren
  bleiben controller/lease_lock.py.
- DEAD_LETTER != ERLEDIGT: ein toter Brief bleibt auditierbar
  liegen (ISOLATE_NOT_DESTROY).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:  # Paket-Import (Tests/CI starten ab Wurzel)
    from controller.ledger_lock import LedgerLockError, exclusive_ledger_lock
except ImportError:  # Skript-Modus
    from ledger_lock import LedgerLockError, exclusive_ledger_lock  # type: ignore

SCHEMA_EVENT = "v91.alarm_outbox.event.v1"
SCHEMA_TRANSITION = "v91.alarm_outbox.transition.v1"
DEFAULT_CAPACITY = 10000
DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_BACKOFF_SECONDS = 30.0
DEFAULT_MAX_BACKOFF_SECONDS = 3600.0
SECRET_KEY_PATTERN = re.compile(r"(passwort|password|secret|token|api[_-]?key|authorization|bearer)", re.IGNORECASE)
FORBIDDEN_FIELD_PATTERN = re.compile(r"(patient|medizin|medic|diagnos|gesundheit|health|kranken)", re.IGNORECASE)


class AlarmOutboxError(RuntimeError):
    """Outbox-Operation kann nicht ehrlich ausgefuehrt werden (fail-closed)."""


def _require_now(now: Any) -> datetime.datetime:
    if isinstance(now, str):
        try:
            now = datetime.datetime.fromisoformat(now)
        except ValueError as exc:
            raise AlarmOutboxError(f"now is not a valid ISO-8601 timestamp: {exc}") from exc
    if not isinstance(now, datetime.datetime):
        raise AlarmOutboxError("now must be a tz-aware datetime or ISO-8601 string")
    if now.tzinfo is None:
        raise AlarmOutboxError("now must be timezone-aware; naive timestamps are rejected")
    return now


def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).isoformat()


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in obj.items():
            if SECRET_KEY_PATTERN.search(str(key)):
                out[str(key)] = "[REDACTIERT]"
            else:
                out[str(key)] = _redact(value)
        return out
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _validate_event(alert: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(alert, dict):
        raise AlarmOutboxError("alert must be an object")
    def _check_keys(obj: Any, where: str) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if FORBIDDEN_FIELD_PATTERN.search(str(key)):
                    raise AlarmOutboxError(
                        f"personal or medical field {key!r} is not allowed in alert "
                        f"payloads ({where}; data minimization)"
                    )
                _check_keys(value, where)

    _check_keys(alert, "top level")
    _check_keys(alert.get("payload", {}), "payload")
    event_id = alert.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise AlarmOutboxError("event_id needs a non-empty string (stable event identity)")
    source_ref = alert.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise AlarmOutboxError("source_ref needs a non-empty string (evidence backlink)")
    severity = alert.get("severity")
    if severity not in ("INFO", "WARNUNG", "KRITISCH"):
        raise AlarmOutboxError("severity must be one of INFO/WARNUNG/KRITISCH")
    if not isinstance(alert.get("begruendung"), str) or not alert["begruendung"].strip():
        raise AlarmOutboxError("begruendung (severity rationale) needs a non-empty string")
    return dict(alert)


def event_id_from(source_ref: str, event_type: str, window_start: str) -> str:
    """Deterministische Event-ID (Replay/Dedup-Grundlage; KEIN Zufall)."""
    digest = hashlib.sha256(
        (source_ref.strip() + "\n" + event_type.strip() + "\n" + window_start.strip()).encode("utf-8")
    ).hexdigest()
    return "evt-" + digest[:16]


def _load_records_locked(path: pathlib.Path) -> List[Dict[str, Any]]:
    """Historie lesen; korrumpierte Zeilen bleiben erhalten, wirken fail-closed."""
    records: List[Dict[str, Any]] = []
    corrupt: List[int] = []
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            raw = line.rstrip("\n")
            if not raw:
                corrupt.append(lineno)
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                corrupt.append(lineno)
                continue
            if not isinstance(rec, dict) or "schema" not in rec or "event_id" not in rec:
                corrupt.append(lineno)
                continue
            records.append(rec)
    if corrupt:
        raise AlarmOutboxError(
            f"outbox history malformed (lines {corrupt[:5]} preserved, refusing append); "
            "ISOLATE_NOT_DESTROY: corrupt bytes are neither rewritten nor deleted"
        )
    return records


def _append_line(path: pathlib.Path, record: Dict[str, Any]) -> None:
    line = json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


def current_state(records: List[Dict[str, Any]], event_id: str) -> Optional[Dict[str, Any]]:
    """Letzter Zustand zu event_id aus Event-+Uebergangs-Zeilen."""
    latest: Optional[Dict[str, Any]] = None
    for rec in records:
        if rec.get("event_id") != event_id:
            continue
        kind = rec.get("schema")
        if kind == SCHEMA_EVENT:
            latest = dict(rec)
            latest["state"] = "ANGELEGT"
            latest["retry_count"] = 0
            latest["updated_at"] = rec.get("angelegt_am")
        elif kind == SCHEMA_TRANSITION and latest is not None:
            latest["state"] = rec.get("nach_stadium", latest.get("state"))
            latest["retry_count"] = rec.get("retry_count", latest.get("retry_count", 0))
            latest["updated_at"] = rec.get("zeitstempel")
    return latest


def create_event(
    outbox_path: Any,
    alert: Dict[str, Any],
    now: Any,
    capacity: int = DEFAULT_CAPACITY,
) -> Dict[str, Any]:
    """Ereignis anlegen (Dedup- und Kapazitaets-gedeckelt, unter Lock)."""
    now_dt = _require_now(now)
    if not isinstance(capacity, int) or capacity <= 0:
        raise AlarmOutboxError("capacity must be a positive integer")
    alert = _validate_event(alert)
    path = pathlib.Path(outbox_path)
    with exclusive_ledger_lock(path):
        records = _load_records_locked(path)
        known_event_ids = {r["event_id"] for r in records if r.get("schema") == SCHEMA_EVENT}
        if alert["event_id"] in known_event_ids:
            return {"status": "BEREITS_BEKANNT", "event_id": alert["event_id"], "neue_zeile": False}
        if len(known_event_ids) >= capacity:
            raise AlarmOutboxError(
                f"outbox exhausted: {len(known_event_ids)} events >= capacity {capacity}; "
                "existing alerts are never erased (ISOLATE_NOT_DESTROY)"
            )
        record = {
            "schema": SCHEMA_EVENT,
            "event_id": alert["event_id"].strip(),
            "source_ref": alert["source_ref"].strip(),
            "schweregrad": alert["severity"],
            "begruendung": alert["begruendung"].strip(),
            "payload": _redact(alert.get("payload", {})),
            "angelegt_am": _iso(now_dt),
            "retention_tage": int(alert.get("retention_tage", 365)),
            "delivery_stadium": "DEAKTIVIERT",
        }
        _append_line(path, record)
    return {"status": "ANGELEGT", "event_id": record["event_id"], "neue_zeile": True}


def plan_delivery(
    config: Dict[str, Any],
    event_id: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Versand-PLANUNG nur mit expliziter Betreiber-Allowlist (kein Netz)."""
    if not isinstance(config, dict):
        raise AlarmOutboxError("delivery config must be an object")
    allowlist = config.get("destination_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        raise AlarmOutboxError(
            "delivery is disabled by default: planning requires an explicit, "
            "operator-configured destination allowlist (REQUEST != AUTHORIZATION)"
        )
    ziel = config.get("ziel")
    if ziel not in allowlist:
        raise AlarmOutboxError(f"destination {ziel!r} is not in the operator allowlist")
    if not str(ziel).lower().startswith("https://"):
        raise AlarmOutboxError("only HTTPS destinations are plannable")
    state = current_state(records, event_id)
    if state is None:
        raise AlarmOutboxError(f"unknown event_id: {event_id}")
    if state.get("state") in ("DEAD_LETTER", "CANCELLED"):
        raise AlarmOutboxError(f"event {event_id} is terminal ({state.get('state')}); no delivery planning")
    return {
        "event_id": event_id,
        "ziel": ziel,
        "verwendung": "PLAN",
        "redirect_ablehnung": True,
        "timeout_s": 10,
        "payload_limit_bytes": 8192,
        "hinweis": "PLAN != VERSANDT: Ausfuehrung benoetigt einen getrennt geprueften Adapter",
    }


def next_backoff_seconds(
    retry_count: int,
    base: float = DEFAULT_BASE_BACKOFF_SECONDS,
    maximum: float = DEFAULT_MAX_BACKOFF_SECONDS,
    rng: Optional[Callable[[], float]] = None,
) -> float:
    """Exponentieller Backoff mit Jitter (rng injizierbar, deterministisch testbar)."""
    if retry_count < 0:
        raise AlarmOutboxError("retry_count must be >= 0")
    if base <= 0 or maximum <= 0 or base > maximum:
        raise AlarmOutboxError("backoff bounds invalid: 0 < base <= maximum")
    exponential = min(base * (2 ** retry_count), maximum)
    jitter = rng() if rng is not None else 0.5
    if not 0.0 <= jitter <= 1.0:
        raise AlarmOutboxError("jitter source must return values in [0, 1]")
    return round(exponential * (0.5 + 0.5 * jitter), 3)


def record_transition(
    outbox_path: Any,
    event_id: str,
    transition: str,
    now: Any,
    retry_count: int = 0,
    deadline: Any = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Dict[str, Any]:
    """Begrenzter Zustandsuebergang: RETRY_VERPLANT / CANCELLED / DEAD_LETTER."""
    now_dt = _require_now(now)
    path = pathlib.Path(outbox_path)
    with exclusive_ledger_lock(path):
        records = _load_records_locked(path)
        state = current_state(records, event_id)
        if state is None:
            raise AlarmOutboxError(f"unknown event_id: {event_id}")
        if state.get("state") in ("DEAD_LETTER", "CANCELLED"):
            raise AlarmOutboxError(f"terminal state {state.get('state')} cannot transition")
        if transition == "CANCELLED":
            nach = "CANCELLED"
        elif transition == "DEADLINE_VERSTRICHEN":
            nach = "DEAD_LETTER"
        elif transition == "RETRY_VERPLANT":
            if deadline is not None:
                deadline_dt = _require_now(deadline)
                if deadline_dt <= now_dt:
                    raise AlarmOutboxError("deadline must lie in the future")
            if retry_count > max_retries:
                nach = "DEAD_LETTER"
            else:
                nach = "RETRY_VERPLANT"
        else:
            raise AlarmOutboxError(f"unknown transition: {transition}")
        record = {
            "schema": SCHEMA_TRANSITION,
            "event_id": event_id,
            "uebergang": transition,
            "nach_stadium": nach,
            "retry_count": retry_count,
            "zeitstempel": _iso(now_dt),
            "deadline": _iso(_require_now(deadline)) if deadline is not None else None,
        }
        _append_line(path, record)
    return {"status": nach, "event_id": event_id, "retry_count": retry_count}


def read_state(outbox_path: Any, event_id: str) -> Dict[str, Any]:
    path = pathlib.Path(outbox_path)
    with exclusive_ledger_lock(path):
        records = _load_records_locked(path)
    state = current_state(records, event_id)
    if state is None:
        raise AlarmOutboxError(f"unknown event_id: {event_id}")
    return state


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="V91 Alarm-Outbox (Issue #520, local core, delivery DISABLED)")
    parser.add_argument("--self-check", action="store_true", help="synthetic fixture self-check (SYNTHETISCH != MESSUNG)")
    args = parser.parse_args(argv)
    if not args.self_check:
        print("usage: --self-check", file=sys.stderr)
        return 2
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "v91_alarm_outbox.jsonl"
        now = datetime.datetime(2026, 11, 26, 6, 0, 0, tzinfo=datetime.timezone.utc)
        eid = event_id_from("ledger::selfcheck", "versorgung", "2026-11-26T06:00:00Z")
        first = create_event(path, {
            "event_id": eid,
            "source_ref": "ledger::selfcheck",
            "severity": "WARNUNG",
            "begruendung": "synthetische Selbstpruefung",
            "payload": {"bereich": "energie", "api_key": "soll-redigiert-werden"},
        }, now)
        dup = create_event(path, {
            "event_id": eid,
            "source_ref": "ledger::selfcheck",
            "severity": "WARNUNG",
            "begruendung": "synthetische Selbstpruefung",
        }, now)
        state = read_state(path, eid)
        backoff = next_backoff_seconds(2, rng=lambda: 0.5)
        ok = (
            first["status"] == "ANGELEGT"
            and dup["status"] == "BEREITS_BEKANNT"
            and state["state"] == "ANGELEGT"
            and state["retry_count"] == 0
            and state["payload"]["api_key"] == "[REDACTIERT]"
            and backoff == 90.0  # 30*4 * (0.5+0.5*0.5)
        )
        print(json.dumps({
            "mechanismus": "getestet",
            "reale_auslieferung": "NICHT_GEPRUEFT",
            "self_check": "PASS" if ok else "FEHLER",
            "event_id": eid,
            "backoff_s_2": backoff,
        }, indent=2))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
