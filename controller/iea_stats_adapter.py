"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
IEA-Stats-Adapter: OPTIONALER Live-Ingest fuer externe Energiedaten
(Strommix-Anteile, CO2-Intensitaet) in den HashChainLedger.

REUSE-Abgrenzung (NO_DUPLICATE_SYSTEMS):
- controller/measurement_ingest.py bleibt ALLEINVERBINDLICH fuer die
  fail-closed Messwert-Validierung (dieser Adapter ruft NUR
  validate_measurement auf, keine zweite Prueflogik).
- controller/ledger.py (HashChainLedger) bleibt ALLEINVERBINDLICH fuer
  die append-only Hash-Kette; der Adapter schreibt NUR payloads.
- messwerte_ingest/mess_pilot bleiben der ROHDAUFPFAD fuer lokale
  Sensoren; dieser Adapter ist der PFAD FUER EXTERNE KATALOGDATEN
  (ABRUF != MESSUNG).

Verbindliche Regeln:
- CLAIM != EVIDENCE: ein abgerufener Wert ist ein CLAIM der Quelle,
  kein Beleg. Jede Aufnahme traegt Quelle, Zeitstempel der Quelle,
  Abrufzeitstempel und eigene Validierungsgrenzen.
- UNKNOWN != PASS: fehlende, ungueltige, quarantaene oder
  nicht-konfigurierte Werte werden EXPLIZIT als UNKNOWN-Record in
  den Ledger geschrieben (wert: null, status NICHT_GEPRUEFT) und
  NIE still verworfen und NIE durch 0 ersetzt.
- KEIN_NETZ_IM_MODULKERN: der Poll verwendet ein injiziertes
  fetch callable. Der reale urlopen-Fetcher liegt getrennt;
  Tests und Betrieb konnen einen Stub uebergeben (SCRIPTED !=
  RUNNING, RECHNER/SAMPLER != NETZDAEMON).
- KEINE_SECRETS_IM_REPO: der IEA-API-Schluessel wird NUR aus der
  Umgebungsvariable gelesen; fehlt sie, ist der Adapter
  NOT_CONFIGURED und schreibt ehrliche UNKNOWN-Records.

Ehrliche Grenzen:
- ABRUF == MOMENTAUFNAHME: IEA-Daten sind gerundete, laengst
  veroeffentlichte Katalogwerte, KEINE Echtzeitmessung
  (KATALOG != SENSOR, STUNDENWERT != LIVE).
- Der Adapter pollt NICHT von selbst: kein Daemon, kein Scheduler
  (SCRIPTED != INSTALLED); der Betriebstab (z. B. cron) bleibt
  Betreiber-Aufgabe.
- FAO- und WHO-Adapter existieren auf main NICHT; die hier
  definierte Adapter-Schnittstelle ist bewusst generisch gehalten,
  damit beide denselben Pfad nutzen koennen, ohne dass deren
  Existenz behauptet wird (VISION_UNIMPLEMENTED != BEHAUPTET).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional

_SCRIPT_DIR = str(pathlib.Path(__file__).resolve().parent)
while _SCRIPT_DIR in sys.path:
    sys.path.remove(_SCRIPT_DIR)
_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controller import measurement_ingest  # REUSE: alleinverbindlich

NICHT_GEPRUEFT = "NICHT_GEPRUEFT"
UNKNOWN = "UNKNOWN"
STATUS_VALID = "VALID"
STATUS_QUARANTINE = "QUARANTINE"
STATUS_REJECTED = "REJECTED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"

SOURCE_ID = "iea-stats"

# Wertebereiche je Metrik: BEWEISGRENZEN, keine Meinungen
# (co2-Intensitaet grob 0..2500 gCO2/kWh deckt alle bekannten
# Netze ab; Strommix-Anteile sind Anteile in [0, 1]).
METRIC_SPECS = {
    "strommix_anteil": measurement_ingest.SensorSpec(
        metric="strommix_anteil", unit="anteil", minimum=0.0, maximum=1.0),
    "co2_intensitaet": measurement_ingest.SensorSpec(
        metric="co2_intensitaet", unit="gCO2/kWh", minimum=0.0,
        maximum=2500.0),
}

HONESTY_LIMITS = (
    "CLAIM != EVIDENCE, KATALOG != SENSOR, ABRUF == MOMENTAUFNAHME, "
    "UNKNOWN != PASS, KEINE_STUMME_KORREKTUR, SCRIPTED != RUNNING, "
    "kein Daemon, API-Schluessel NUR aus Umgebung, FAO/WHO-Adapter "
    "auf main VISION_UNIMPLEMENTED"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def real_fetch(url: str, api_key: str, timeout: float = 30.0) -> str:
    """Realer Abruf; NUR vom Betrieb aufzurufen, nie von Tests.
    Schluessel wandert in den Authorization-Header, NIE in die URL."""
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_iea_payload(text: str) -> dict[str, Any]:
    """Extrahiert je Metrik EINEN Wert aus einer IEA-Stats-Antwort.
    Fail-closed: unbekannte Struktur -> leeres dict, NICHT raten."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data.get("values", {}) if isinstance(data.get("values"), dict) else {}


def poll_once(ledger: Any, metric: str, laendercode: str,
              api_key_env: str = "IEA_API_KEY",
              fetch: Optional[Callable[[str, str], str]] = None,
              url_builder: Optional[Callable[[str, str], str]] = None
              ) -> dict[str, Any]:
    """Ein Abruf, eine Validierung, EIN Ledger-Record (nie still).

    Der Record ist immer genau einer, mit status NICHT_GEPRUEFT
    falls irgend etwas fehlt oder ungueltig ist. Das ist das
    EXPLIZITE UNKNOWN-Protokoll gegen leere Basin."""
    if metric not in METRIC_SPECS:
        raise ValueError("unbekannte Metrik: %r" % metric)
    spec = METRIC_SPECS[metric]
    abruf_ts = _utc_now_iso()
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        record = _unknown_record(metric, laendercode, abruf_ts,
                                 STATUS_NOT_CONFIGURED,
                                 "api_key fehlt (%s)" % api_key_env)
        _append(ledger, record)
        return record
    if fetch is None or url_builder is None:
        record = _unknown_record(metric, laendercode, abruf_ts,
                                  STATUS_NOT_CONFIGURED,
                                  "fetch oder url_builder nicht injiziert"
                                  " (Betrieb muss liefern)")
        _append(ledger, record)
        return record
    try:
        url = url_builder(metric, laendercode)
        text = fetch(url, api_key)
    except Exception as exc:  # Netz/HTTP: NICHT geprueft, kein Crash
        record = _unknown_record(metric, laendercode, abruf_ts,
                                 STATUS_QUARANTINE,
                                 "abruf fehlgeschlagen: " + str(exc)[:200])
        _append(ledger, record)
        return record
    werte = parse_iea_payload(text)
    roh = werte.get(metric)
    quelle_ts = werte.get("as_of")
    quelle_ts_s = quelle_ts if isinstance(quelle_ts, str) else None
    roh_messung = measurement_ingest.RawMeasurement(
        sensor_id=SOURCE_ID + ":" + laendercode, metric=metric,
        value=roh, unit=spec.unit,
        timestamp=quelle_ts_s or abruf_ts, source=SOURCE_ID)
    ergebnis = measurement_ingest.validate_measurement(
        roh_messung, {metric: spec})
    if ergebnis.status.value == STATUS_VALID:
        record = {
            "sensor_id": roh_messung.sensor_id, "quelle": SOURCE_ID,
            "metrik": metric, "region": laendercode,
            "wert": ergebnis.normalized_value, "status": STATUS_VALID,
            "einheit": spec.unit, "quelle_ts": quelle_ts_s,
            "ablauf_ts_utc": abruf_ts,
            "validierungs_grenzen": {"min": spec.minimum,
                                     "max": spec.maximum},
            "honesty_limits": HONESTY_LIMITS,
        }
    else:
        record = _unknown_record(
            metric, laendercode, abruf_ts, ergebnis.status.value,
            "; ".join(ergebnis.errors) or "validierung fehlgeschlagen",
            rohwert=_safe(roh), quelle_ts=quelle_ts_s)
    _append(ledger, record)
    return record


def _safe(wert: Any) -> Any:
    if isinstance(wert, (dict, list)):
        return json.dumps(wert, ensure_ascii=True)[:200]
    return wert if isinstance(wert, (int, float, str)) else str(wert)[:200]


def _unknown_record(metric: str, region: str, abruf_ts: str,
                    fehler_status: str, grund: str,
                    rohwert: Any = None,
                    quelle_ts: Optional[str] = None) -> dict[str, Any]:
    """EXPLIZITER UNKNOWN-Record: wert=null, NIEMALS 0."""
    return {
        "sensor_id": SOURCE_ID + ":" + region, "quelle": SOURCE_ID,
        "metrik": metric, "region": region, "wert": None,
        "status": NICHT_GEPRUEFT, "fehler_status": fehler_status,
        "grund": grund, "rohwert": _safe(rohwert), "quelle_ts": quelle_ts,
        "ablauf_ts_utc": abruf_ts, "honesty_limits": HONESTY_LIMITS,
    }


def _append(ledger: Any, record: dict[str, Any]) -> Any:
    """Ledger-Append:Payload bei INVALID-Kette fail-closed (Exception)."""
    return ledger.append(record, timestamp=_utc_now_iso())


# --- Vergleichsrueste FAO/WHO: GLEICHER Pfad, ohne Existenzbehauptung ---
ADAPTER_PROTOCOL = {
    "poll_once": "poll_once(ledger, metric, region, fetch, url_builder)",
    "metric_specs": "Wertebereiche je Metrik (SensorSpec, REUSE)",
    "unknown_record": "wert=null, status NICHT_GEPRUEFT, grund",
    "aenderungen": "JEDE Quelle ein eigener Sensor_ID-Namensraum",
}
