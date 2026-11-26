"""Tests fuer controller/alarm_delivery_guard.py + alarm_outbox-Guard-Verdrahtung (Issue #520-Rest)."""
import datetime
import json
import pathlib
import subprocess
import sys

import pytest

from controller.alarm_delivery_guard import (
    DeliveryGuardError,
    bewerte_aufloesung,
    bewerte_plan,
    pruefe_adressen,
    pruefe_grenzen,
    pruefe_ziel,
)
from controller.alarm_outbox import create_event, plan_delivery, read_state

NOW = datetime.datetime(2026, 11, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
ALLOW = ["https://ops.example/warnungen"]


def _plan_config(**extra):
    base = {"ziel": "https://ops.example/warnungen", "destination_allowlist": ALLOW}
    base.update(extra)
    return base


def test_ziel_https_allowlist_userinfo():
    assert pruefe_ziel("https://ops.example/warnungen", ALLOW) == "https://ops.example/warnungen"
    with pytest.raises(DeliveryGuardError, match="https"):
        pruefe_ziel("http://ops.example/warnungen", ALLOW)
    with pytest.raises(DeliveryGuardError, match="userinfo"):
        pruefe_ziel("https://user:pass@ops.example/warnungen", ALLOW)
    with pytest.raises(DeliveryGuardError, match="allowlist"):
        pruefe_ziel("https://boese.example/x", ALLOW)
    with pytest.raises(DeliveryGuardError, match="allowlist"):
        pruefe_ziel("https://ops.example/warnungen", [])
    with pytest.raises(DeliveryGuardError, match="non-empty"):
        pruefe_ziel("   ", ALLOW)


def test_ssrf_adressen_fail_closed():
    gut = pruefe_adressen(["93.184.216.34", "2606:2800:220:1:248:1893:25c8:19e6"])
    assert gut == ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:19e6"]
    for boese in ["127.0.0.1", "10.0.0.1", "192.168.1.5", "169.254.1.1", "0.0.0.0",
                  "::1", "fc00::1", "fe80::1", "ff02::1", "100.64.0.1", "keine-ip"]:
        with pytest.raises(DeliveryGuardError):
            pruefe_adressen(["93.184.216.34", boese])  # Rebinding: EINE boese Adresse verwirft ALLES
    with pytest.raises(DeliveryGuardError, match="non-empty"):
        pruefe_adressen([])
    with pytest.raises(DeliveryGuardError, match="non-empty"):
        pruefe_adressen([None])


def test_grenzen_strikt():
    g = pruefe_grenzen({})
    assert g == {"redirect_ablehnung": True, "timeout_s": 10, "payload_limit_bytes": 8192}
    for bad in [{"redirect_ablehnung": False}, {"redirect_ablehnung": None},
                {"timeout_s": 0}, {"timeout_s": 31}, {"timeout_s": "10"}, {"timeout_s": True},
                {"payload_limit_bytes": 0}, {"payload_limit_bytes": 8193}, {"payload_limit_bytes": "x"}]:
        with pytest.raises(DeliveryGuardError):
            pruefe_grenzen(bad)
    assert pruefe_grenzen({"timeout_s": 30, "payload_limit_bytes": 1})["timeout_s"] == 30


def test_aufloesung_injiziert_nicht_geprueft():
    oh = bewerte_aufloesung(_plan_config())
    assert oh["aufloesung"] == "NICHT_GEPRUEFT" and oh["adressen"] == []
    mit = bewerte_aufloesung(_plan_config(), resolve_fn=lambda host: ["93.184.216.34"])
    assert mit["aufloesung"] == "PRUEFUNG_BESTANDEN" and mit["adressen"] == ["93.184.216.34"]
    # Resolver-Fehler ist fail-closed (NICHT_AUFGELOEST != BESTANDEN)
    with pytest.raises(DeliveryGuardError, match="fail-closed"):
        bewerte_aufloesung(_plan_config(), resolve_fn=lambda host: (_ for _ in ()).throw(OSError("dns down")))
    with pytest.raises(DeliveryGuardError, match="rebinding"):
        bewerte_aufloesung(_plan_config(), resolve_fn=lambda host: ["93.184.216.34", "10.0.0.9"])


def test_bewerte_plan_vollstaendig():
    plan = bewerte_plan(_plan_config(timeout_s=5, payload_limit_bytes=4096),
                        resolve_fn=lambda host: ["93.184.216.34"])
    assert plan["verwendung"] == "PLAN"
    assert plan["aufloesung"] == "PRUEFUNG_BESTANDEN"
    assert plan["timeout_s"] == 5 and plan["payload_limit_bytes"] == 4096
    assert plan["redirect_ablehnung"] is True
    assert "PLAN != VERSANDT" in plan["hinweis"]


def test_outbox_verdrahtung_guard_nachrichten(tmp_path):
    path = tmp_path / "v91_alarm_outbox.jsonl"
    create_event(path, {"event_id": "evt-a", "source_ref": "ledger::t", "severity": "WARNUNG",
                        "begruendung": "synthetisch"}, NOW)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").strip().splitlines()]
    cfg = {"ziel": "https://ops.example/warnungen", "destination_allowlist": ALLOW}
    # Ohne Aufloesung: UNKNOWN bleibt UNKNOWN (NICHT_GEPRUEFT, niemals PASS)
    plan = plan_delivery({**cfg, "aufloesung": None}, "evt-a", records)
    assert plan["aufloesung"] == "NICHT_GEPRUEFT" and plan["adressen"] == []
    # Gueltige Aufloesung: PRUEFUNG_BESTANDEN
    plan = plan_delivery({**cfg, "aufloesung": ["93.184.216.34"]}, "evt-a", records)
    assert plan["aufloesung"] == "PRUEFUNG_BESTANDEN" and plan["adressen"] == ["93.184.216.34"]
    # Rebinding-Aufloesung: fail-closed ueber AlarmOutboxError
    from controller.alarm_outbox import AlarmOutboxError
    with pytest.raises(AlarmOutboxError, match="delivery guard"):
        plan_delivery({**cfg, "aufloesung": ["93.184.216.34", "192.168.0.5"]}, "evt-a", records)
    # Ungueltige Grenzen: fail-closed
    with pytest.raises(AlarmOutboxError, match="delivery guard"):
        plan_delivery({**cfg, "timeout_s": 300}, "evt-a", records)
    with pytest.raises(AlarmOutboxError, match="delivery guard"):
        plan_delivery({**cfg, "redirect_ablehnung": False}, "evt-a", records)
    # Bestehendes Verhalten bleibt: Defaults
    plan = plan_delivery(cfg, "evt-a", records)
    assert plan["payload_limit_bytes"] == 8192 and plan["timeout_s"] == 10 and plan["redirect_ablehnung"] is True


def test_self_check_cli():
    proc = subprocess.run([sys.executable, "-m", "controller.alarm_delivery_guard", "--self-check"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["self_check"] == "PASS"
    assert out["rebinding_abgewiesen"] is True
    assert out["reale_auslieferung"] == "NICHT_GEPRUEFT"


def test_kein_netz_im_guard_kern():
    import controller.alarm_delivery_guard as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for banned in ("import socket", "import requests", "import http.client", "urllib.request"):
        assert banned not in src
    # urllib.parse ist erlaubt (URL-Zerlegung), NICHT urlopen
    assert "urlopen" not in src
