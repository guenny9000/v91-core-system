"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
FAO-Stats-Adapter: OPTIONALER Live-Ingest fuer externe Agrar- und
Ernaehrungs-Katalogdaten (FAOSTAT-Sicht) in den HashChainLedger.

REUSE-Abgrenzung (NO_DUPLICATE_SYSTEMS):
- controller/measurement_ingest.py bleibt ALLEINVERBINDLICH fuer die
  fail-closed Messwert-Validierung; dieser Adapter ruft NUR
  validate_measurement auf (keine zweite Prueflogik).
- controller/ledger.py (HashChainLedger) bleibt ALLEINVERBINDLICH fuer
  die append-only Hash-Kette; der Adapter schreibt NUR payloads.
- controller/iea_stats_adapter.py bleibt der Referenz-Implementierung
  des Adapter-Protokolls (gleicher Pfad, eigene Metriken, eigener
  Sensor-ID-Namensraum; CODE-STRUKTUR parallel, KEINE gemeinsame
  versteckte Logik).

Verbindliche Regeln:
- CLAIM != EVIDENCE: ein abgerufener Wert ist ein CLAIM der Quelle,
  kein Beleg. Jede Aufnahme traegt Quelle, Zeitstempel der Quelle,
  Abrufzeitstempel und eigene Validierungsgrenzen.
- UNKNOWN != PASS: fehlende, ungueltige oder quarantaene Werte werden
  EXPLIZIT als UNKNOWN-Record in den Ledger geschrieben (wert: null,
  status NICHT_GEPRUEFT) und NIE still verworfen, NIE durch 0 ersetzt.
- KEIN_NETZ_IM_MODULKERN: der Poll verwendet ein injiziertes fetch
  callable; der reale urlopen-Fetcher liegt getrennt (SCRIPTED !=
  RUNNING, KATALOGDEAMON != NETZDAEMON). Der Adapter pollt NICHT von
  selbst: kein Daemon, kein Scheduler.
- KEINE_SECRETS_IM_REPO: ein eventuell noetiger API-Schluessel wird
  NUR aus der Umgebungsvariable gelesen (nie im Repo, nie in der
  URL). FAO-Endpunkte sind teilweise offen; ein Abruf OHNE
  konfigurierten Key bleibt NUR zulaessig, wenn require_api_key
  explizit False gesetzt ist (OFFENER_ABRUF == KONFIGENTSCHEID,
  KEIN BEWEIS), und der Record weist das aus (abruf_ohne_key).
  KEY_VORHANDEN != BELEG: auch mit Key bleibt jeder Katalogwert ein
  CLAIM der Quelle.

Ehrliche Grenzen:
- ABRUF == MOMENTAUFNAHME: FAOSTAT-Werte sind gerundete, laengst
  veroeffentlichte Katalogwerte, KEINE Echtzeitmessung
  (KATALOG != SENSOR, JAHRWERT != LIVE).
- FICTION_GRENZE: Metrik-Namen und Wertebereiche hier sind
  ADAPTER-VERTRAG (was dieser Adapter ZULAESST). NICHT behauptet
  wird, dass je eine echte FAO-Abfrage stattfand; der reale Abrufweg
  (url_builder) bleibt Betreiber-Aufgabe.
- Der Betriebstab (cron/Aufruf) bleibt Betreiber-Aufgabe.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import sys
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
STATUS_VALID = "VALID"
STATUS_QUARANTINE = "QUARANTINE"
STATUS_REJECTED = "REJECTED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"

SOURCE_ID = "fao-stats"

# Wertebereiche je Metrik: BEWEISGRENZEN, keine Meinungen.
# Ernteertraege weltweit grob 0..400 t/ha (Zuckerrohr-Spitzenwerte
# eingeschlossen); Duengeleinsatz 0..2000 kg/ha; FAO-Preisindex-
# Historie grob 90..160 Punkte, Beweisgrenze grosszuegig 0..500.
METRIC_SPECS = {
    "ernteertrag_t_ha": measurement_ingest.SensorSpec(
        metric="ernteertrag_t_ha", unit="t_ha", minimum=0.0,
        maximum=400.0),
    "duengereinsatz_kg_ha": measurement_ingest.SensorSpec(
        metric="duengereinsatz_kg_ha", unit="kg_ha", minimum=0.0,
        maximum=2000.0),
    "lebensmittelpreisindex_pkt": measurement_ingest.SensorSpec(
        metric="lebensmittelpreisindex_pkt", unit="pkt", minimum=0.0,
        maximum=500.0),
}

HONESTY_LIMITS = (
    "CLAIM != EVIDENCE, KATALOG != SENSOR, ABRUF == MOMENTAUFNAHME, "
    "UNKNOWN != PASS, KEINE_STUMME_KORREKTUR, SCRIPTED != RUNNING, "
    "kein Daemon, API-Schluessel NUR aus Umgebung, OFFENER_ABRUF "
    "ohne Key NUR bei require_api_key=False und IMMER im Record "
    "ausgewiesen (abruf_ohne_key)"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def real_fetch(url: str, api_key: str = "", timeout: float = 30.0) -> str:
    """Realer Abruf; NUR vom Betrieb aufzurufen, nie von Tests.
    Ein konfigurierter Schluessel wandert in den Authorization-Header,
    NIE in die URL; ein leerer Schluessel bedeutet offenen Abruf."""
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def parse_fao_payload(text: str) -> dict[str, Any]:
    """Extrahiert je Metrik EINEN Wert aus einer FAO-Antwort.
    Fail-closed: unbekannte Struktur -> leeres dict, NICHT raten."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    werte = data.get("values")
    return werte if isinstance(werte, dict) else {}


def poll_once(ledger: Any, metric: str, laendercode: str,
              api_key_env: str = "FAO_API_KEY",
              require_api_key: bool = False,
              fetch: Optional[Callable[..., str]] = None,
              url_builder: Optional[Callable[[str, str], str]] = None
              ) -> dict[str, Any]:
    """Ein Abruf, eine Validierung, EIN Ledger-Record (nie still)."""
    if metric not in METRIC_SPECS:
        raise ValueError("unbekannte Metrik: %r" % metric)
    spec = METRIC_SPECS[metric]
    abruf_ts = _utc_now_iso()
    api_key = os.environ.get(api_key_env, "").strip()
    abruf_ohne_key = not api_key
    if abruf_ohne_key and require_api_key:
        record = _unknown_record(
            metric, laendercode, abruf_ts, STATUS_NOT_CONFIGURED,
            "api_key fehlt (%s, require_api_key=True)" % api_key_env,
            abruf_ohne_key=True)
        _append(ledger, record)
        return record
    if fetch is None or url_builder is None:
        record = _unknown_record(
            metric, laendercode, abruf_ts, STATUS_NOT_CONFIGURED,
            "fetch oder url_builder nicht injiziert"
            " (Betrieb muss liefern)", abruf_ohne_key=abruf_ohne_key)
        _append(ledger, record)
        return record
    try:
        url = url_builder(metric, laendercode)
        text = fetch(url, api_key) if api_key else fetch(url)
    except Exception as exc:  # Netz/HTTP: NICHT geprueft, kein Crash
        record = _unknown_record(
            metric, laendercode, abruf_ts, STATUS_QUARANTINE,
            "abruf fehlgeschlagen: " + str(exc)[:200],
            abruf_ohne_key=abruf_ohne_key)
        _append(ledger, record)
        return record
    werte = parse_fao_payload(text)
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
            "ablauf_ts_utc": abruf_ts, "abruf_ohne_key": abruf_ohne_key,
            "validierungs_grenzen": {"min": spec.minimum,
                                     "max": spec.maximum},
            "honesty_limits": HONESTY_LIMITS,
        }
    else:
        record = _unknown_record(
            metric, laendercode, abruf_ts, ergebnis.status.value,
            "; ".join(ergebnis.errors) or "validierung fehlgeschlagen",
            rohwert=_safe(roh), quelle_ts=quelle_ts_s,
            abruf_ohne_key=abruf_ohne_key)
    _append(ledger, record)
    return record


def _safe(wert: Any) -> Any:
    if isinstance(wert, (dict, list)):
        return json.dumps(wert, ensure_ascii=True)[:200]
    return wert if isinstance(wert, (int, float, str)) else str(wert)[:200]


def _unknown_record(metric: str, region: str, abruf_ts: str,
                    fehler_status: str, grund: str,
                    rohwert: Any = None,
                    quelle_ts: Optional[str] = None,
                    abruf_ohne_key: bool = False) -> dict[str, Any]:
    """EXPLIZITER UNKNOWN-Record: wert=null, NIEMALS 0."""
    return {
        "sensor_id": SOURCE_ID + ":" + region, "quelle": SOURCE_ID,
        "metrik": metric, "region": region, "wert": None,
        "status": NICHT_GEPRUEFT, "fehler_status": fehler_status,
        "grund": grund, "rohwert": _safe(rohwert), "quelle_ts": quelle_ts,
        "ablauf_ts_utc": abruf_ts, "abruf_ohne_key": abruf_ohne_key,
        "honesty_limits": HONESTY_LIMITS,
    }


def _append(ledger: Any, record: dict[str, Any]) -> Any:
    """Ledger-Append:Payload bei INVALID-Kette fail-closed (Exception)."""
    return ledger.append(record, timestamp=_utc_now_iso())


def poll_batch(ledger: Any, metrics: list, region: str,
               **kwargs: Any) -> list:
    """Pollt MEHRERE Metriken SEQUENZIELL (reproduzierbare
    Ledger-Reihenfolge, KEIN Parallelismus ohne Mehrwert).
    Je Metrik GENAU EIN Record (poll_once-Regel unveraendert)."""
    ergebnisse = []
    for metric in metrics:
        ergebnisse.append(poll_once(ledger, metric, region, **kwargs))
    return ergebnisse
