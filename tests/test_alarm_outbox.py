"""Tests fuer controller/alarm_outbox.py (Issue #520, self-contained, nur tempfile)."""
import datetime
import json
import pathlib

import pytest

from controller.alarm_outbox import (
    AlarmOutboxError,
    SCHEMA_EVENT,
    SCHEMA_TRANSITION,
    create_event,
    current_state,
    event_id_from,
    next_backoff_seconds,
    MAX_PAYLOAD_BYTES,
    plan_delivery,
    read_state,
    record_transition,
)

NOW = datetime.datetime(2026, 11, 26, 6, 0, 0, tzinfo=datetime.timezone.utc)
LATER = NOW + datetime.timedelta(hours=1)


def _alert(event_id="evt-a", severity="WARNUNG", payload=None):
    return {
        "event_id": event_id,
        "source_ref": "ledger::test-001",
        "severity": severity,
        "begruendung": "Versorgungszustand aus Bewertung synthetisch",
        "payload": payload if payload is not None else {"bereich": "energie"},
    }


def _eid(nr):
    return event_id_from("ledger::test-001", "versorgung", f"2026-11-26T0{nr}:00:00Z")


def test_event_id_deterministisch_unterscheidbar():
    a = event_id_from("ledger::s", "typ", "fenster-1")
    b = event_id_from("ledger::s", "typ", "fenster-2")
    assert a == event_id_from("ledger::s", "typ", "fenster-1")
    assert a != b
    assert a.startswith("evt-") and len(a) == 20


def test_create_event_angelegt_und_dedup(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    first = create_event(path, _alert("evt-a"), NOW)
    dup = create_event(path, _alert("evt-a"), LATER)
    assert first == {"status": "ANGELEGT", "event_id": "evt-a", "neue_zeile": True}
    assert dup["status"] == "BEREITS_BEKANNT" and dup["neue_zeile"] is False
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["schema"] == SCHEMA_EVENT
    assert create_event(path, _alert("evt-b"), NOW)["status"] == "ANGELEGT"


def test_offline_anlage_und_auditierbarkeit(tmp_path):
    # Kein Netz im Modulkern: Anlage funktioniert ohne jede Konfiguration.
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    state = read_state(path, "evt-a")
    assert state["state"] == "ANGELEGT"
    assert state["delivery_stadium"] == "DEAKTIVIERT"
    assert state["schweregrad"] == "WARNUNG"


def test_kapazitaet_fail_closed_ohne_loeschung(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW, capacity=1)
    with pytest.raises(AlarmOutboxError, match="exhausted"):
        create_event(path, _alert("evt-b"), NOW, capacity=1)
    # Bestand bleibt unangetastet (ISOLATE_NOT_DESTROY).
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 and "evt-a" in lines[0]
    with pytest.raises(AlarmOutboxError):
        create_event(path, {"event_id": "x"}, NOW, capacity=0)


def test_korrumpierte_historie_erhalten_und_fail_closed(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"schema": "kein-schema,')  # torn/corrupt tail
    with pytest.raises(AlarmOutboxError, match="malformed"):
        create_event(path, _alert("evt-b"), LATER)
    raw = path.read_text(encoding="utf-8")
    assert "kein-schema," in raw  # korrupte Bytes bleiben erhalten
    assert "evt-a" in raw  # intakte Historie bleibt erhalten


def test_secrets_redigiert_medizinfelder_abgelehnt(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a", payload={"bereich": "netz", "api_key": "geheim", "nested": {"passwort": "x"}}), NOW)
    state = read_state(path, "evt-a")
    assert state["payload"]["api_key"] == "[REDACTIERT]"
    assert state["payload"]["nested"]["passwort"] == "[REDACTIERT]"
    assert "geheim" not in path.read_text(encoding="utf-8")
    with pytest.raises(AlarmOutboxError, match="minimization"):
        create_event(path, _alert("evt-m", payload={"patient_name": "x"}), NOW)


def test_invalid_eingaben_fail_closed(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    with pytest.raises(AlarmOutboxError):
        create_event(path, {"event_id": "e"}, NOW)
    with pytest.raises(AlarmOutboxError, match="timezone-aware"):
        create_event(path, _alert("evt-n"), datetime.datetime(2026, 11, 26, 6, 0, 0))
    with pytest.raises(AlarmOutboxError):
        create_event(path, _alert("evt-s", severity="PANIK"), NOW)


def test_bounded_retry_backoff_deterministisch():
    assert next_backoff_seconds(0, rng=lambda: 0.0) == 15.0  # 30 * (0.5 + 0.5*0)
    assert next_backoff_seconds(2, rng=lambda: 1.0) == 120.0  # 30*4 * 1.0
    assert next_backoff_seconds(20, rng=lambda: 1.0) == 3600.0  # Deckelung
    with pytest.raises(AlarmOutboxError):
        next_backoff_seconds(0, base=100, maximum=10)
    with pytest.raises(AlarmOutboxError):
        next_backoff_seconds(-1)
    with pytest.raises(AlarmOutboxError):
        next_backoff_seconds(0, rng=lambda: 2.0)  # Jitter ausserhalb [0,1]


def test_uebergaenge_retry_cancel_deadline_dead_letter(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    deadline = NOW + datetime.timedelta(hours=2)
    r1 = record_transition(path, "evt-a", "RETRY_VERPLANT", LATER, retry_count=1, deadline=deadline)
    assert r1["status"] == "RETRY_VERPLANT"
    assert read_state(path, "evt-a")["state"] == "RETRY_VERPLANT"
    assert read_state(path, "evt-a")["retry_count"] == 1
    record_transition(path, "evt-a", "DEADLINE_VERSTRICHEN", deadline + datetime.timedelta(minutes=1))
    assert read_state(path, "evt-a")["state"] == "DEAD_LETTER"
    with pytest.raises(AlarmOutboxError, match="terminal"):
        record_transition(path, "evt-a", "RETRY_VERPLANT", deadline + datetime.timedelta(minutes=2))
    create_event(path, _alert("evt-b"), NOW)
    record_transition(path, "evt-b", "CANCELLED", LATER)
    assert read_state(path, "evt-b")["state"] == "CANCELLED"
    with pytest.raises(AlarmOutboxError, match="terminal"):
        record_transition(path, "evt-b", "RETRY_VERPLANT", LATER + datetime.timedelta(minutes=1))


def test_retry_begrenzung_dead_letter(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    for i in range(1, 6):
        record_transition(path, "evt-a", "RETRY_VERPLANT", NOW + datetime.timedelta(minutes=i), retry_count=i)
    assert read_state(path, "evt-a")["state"] == "RETRY_VERPLANT"
    result = record_transition(path, "evt-a", "RETRY_VERPLANT", LATER, retry_count=6, max_retries=5)
    assert result["status"] == "DEAD_LETTER"  # NIE endlos: 6 > 5


def test_vergangene_deadline_abgelehnt(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    with pytest.raises(AlarmOutboxError, match="deadline"):
        record_transition(path, "evt-a", "RETRY_VERPLANT", LATER, deadline=NOW)


def test_unbekannte_transition_und_unbekanntes_event_fail_closed(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    with pytest.raises(AlarmOutboxError, match="unknown transition"):
        record_transition(path, "evt-a", "EXPLODE", LATER)
    with pytest.raises(AlarmOutboxError, match="unknown event_id"):
        record_transition(path, "evt-nix", "CANCELLED", LATER)
    with pytest.raises(AlarmOutboxError, match="unknown event_id"):
        read_state(path, "evt-nix")


def test_delivery_standardmaessig_deaktiviert(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    with open(path, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    with pytest.raises(AlarmOutboxError, match="disabled by default"):
        plan_delivery({}, "evt-a", records)
    with pytest.raises(AlarmOutboxError, match="allowlist"):
        plan_delivery({"ziel": "https://ops.example"}, "evt-a", records)
    with pytest.raises(AlarmOutboxError, match="HTTPS"):
        plan_delivery({"ziel": "http://ops.example", "destination_allowlist": ["http://ops.example"]}, "evt-a", records)
    with pytest.raises(AlarmOutboxError, match="not in the operator allowlist"):
        plan_delivery({"ziel": "https://boese.example", "destination_allowlist": ["https://ops.example"]}, "evt-a", records)
    plan = plan_delivery({"ziel": "https://ops.example", "destination_allowlist": ["https://ops.example"]}, "evt-a", records)
    assert plan["verwendung"] == "PLAN" and plan["redirect_ablehnung"] is True


def test_plan_kein_versand_fuer_terminal(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    record_transition(path, "evt-a", "CANCELLED", LATER)
    with open(path, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    allowlist = {"ziel": "https://ops.example", "destination_allowlist": ["https://ops.example"]}
    with pytest.raises(AlarmOutboxError, match="terminal"):
        plan_delivery(allowlist, "evt-a", records)


def test_konkurrenz_dedup_unter_lock(tmp_path):
    import threading

    path = tmp_path / "v91_alarm_outbox.jsonl"
    results = []
    lock = threading.Lock()

    def worker():
        res = create_event(path, _alert("evt-a"), NOW)
        with lock:
            results.append(res)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r["status"] == "ANGELEGT") == 1
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # kein Interleaving, kein Duplikat
    assert all(json.loads(line)["schema"] == SCHEMA_EVENT for line in lines)


def test_transition_nach_event_und_current_state(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-a"), NOW)
    record_transition(path, "evt-a", "RETRY_VERPLANT", LATER, retry_count=2)
    with open(path, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    assert records[1]["schema"] == SCHEMA_TRANSITION
    state = current_state(records, "evt-a")
    assert state["retry_count"] == 2 and state["updated_at"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("")  # leerer Append bleibt ohne Wirkung


def test_self_check_cli_bestanden():
    import subprocess
    import sys

    proc = subprocess.run([sys.executable, "-m", "controller.alarm_outbox", "--self-check"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["self_check"] == "PASS"
    assert out["mechanismus"] == "getestet"
    assert out["reale_auslieferung"] == "NICHT_GEPRUEFT"  # NICHT_GEPRUEFT, nie Behauptung


def test_gebiete_keine_netzwerkfaehigkeit_im_modul():
    # Modulkern importiert nur stdlib: kein socket/requests/http.client.
    import controller.alarm_outbox as mod

    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for banned in ("import socket", "import requests", "import http.client", "urllib.request"):
        assert banned not in src


def test_payload_is_object_json_safe_and_bounded(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    with pytest.raises(AlarmOutboxError, match="payload must be an object"):
        create_event(path, _alert("evt-list", payload=["not", "an", "object"]), NOW)
    with pytest.raises(AlarmOutboxError, match="JSON-compatible"):
        create_event(path, _alert("evt-object", payload={"bad": object()}), NOW)
    with pytest.raises(AlarmOutboxError, match="byte limit"):
        create_event(
            path,
            _alert("evt-large", payload={"data": "x" * MAX_PAYLOAD_BYTES}),
            NOW,
        )


def test_nested_sensitive_fields_inside_lists_are_rejected(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    payload = {"items": [{"health_record": "must not be stored"}]}
    with pytest.raises(AlarmOutboxError, match="data minimization"):
        create_event(path, _alert("evt-health", payload=payload), NOW)


def test_unknown_event_fields_are_rejected(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    alert = _alert("evt-extra")
    alert["operator_override"] = True
    with pytest.raises(AlarmOutboxError, match="unknown alert fields"):
        create_event(path, alert, NOW)


def test_retention_is_a_bounded_positive_integer(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    for value in (0, -1, True, 1.5, "365", 3651):
        alert = _alert(f"evt-retention-{value}")
        alert["retention_tage"] = value
        with pytest.raises(AlarmOutboxError, match="retention_tage"):
            create_event(path, alert, NOW)


def test_secret_assignments_in_reference_or_reason_are_rejected(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    alert = _alert("evt-secret-ref")
    alert["source_ref"] = "https://example.invalid/?api_key=do-not-store"
    with pytest.raises(AlarmOutboxError, match="secret"):
        create_event(path, alert, NOW)

    alert = _alert("evt-secret-reason")
    alert["begruendung"] = "token=do-not-store"
    with pytest.raises(AlarmOutboxError, match="secret"):
        create_event(path, alert, NOW)


def test_retry_parameters_must_be_non_negative_integers(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, _alert("evt-retry"), NOW)
    for value in (-1, True, 1.5, "1"):
        with pytest.raises(AlarmOutboxError, match="retry_count"):
            record_transition(path, "evt-retry", "RETRY_VERPLANT", LATER, retry_count=value)
        with pytest.raises(AlarmOutboxError, match="max_retries"):
            record_transition(path, "evt-retry", "RETRY_VERPLANT", LATER, max_retries=value)
