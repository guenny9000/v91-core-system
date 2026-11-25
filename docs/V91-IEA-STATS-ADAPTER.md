# IEA-Stats-Adapter im Live-Ingestion-Layer (Entwurf UMGESETZT als Modul)

Antwort auf die Betreiber-Frage 25.11.2026: Wie kann ein vollstaendiger
IEA-Stats-API-Adapter integriert werden, der Energiedaten pollt, gegen
CLAIM != EVIDENCE validiert und fehlende Werte als UNKNOWN im
HashChainLedger protokolliert - inklusive FAO/WHO-Vergleich?

Status: SCRIPTED (Modul + Tests auf main), NICHT INSTALLED
(kein Cron, kein Daemon, kein API-Schluessel im Repo).

## 1. Architektur (alle Bausteine existieren, nichts doppelt)

- Neue Datei controller/iea_stats_adapter.py UND NUR SIE ist neu:
  * Validierung bleibt ALLEINVERBINDLICH in measurement_ingest.py
    (validate_measurement, REUSE: KEINE zweite Prueflogik).
  * Hash-Kette bleibt ALLEINVERBINDLICH in ledger.py
    (HashChainLedger.append; der Adapter schreibt nur payloads).
  * Poll_once ist der EINZIGE Einstieg: ein Abruf => GENAU EIN
    Ledger-Record (VALID oder UNKNOWN), nie ein stiller Verwurf.
- Metrik-Specs als BEWEISGRENZEN: strommix_anteil [0,1],
  co2_intensitaet [0,2500] gCO2/kWh.

## 2. CLAIM != EVIDENCE-Kette

1. ABRUF: fetch-callable injiziert (Stdlib-urllib-Fetcher liegt bereit,
   wird vom Betrieb gerufen, nie von Tests; Schluessel NUR aus
   Umgebungsvariable IEA_API_KEY, Header nicht URL).
2. PARSE: parse_iea_payload fail-closed; unbekannte Struktur =>
   leeres dict, NICHT raten.
3. VALIDIERUNG: echte validate_measurement mit Wertebereich,
   KNOWN_ERROR_VALUES-Sonden, Zeitzone-Zwang.
4. BUCHUNG: je Record quelle, quelle_ts, ablauf_ts_utc, Grenzen und
   honesty_limits; ein abgerufener Katalogwert bleibt CLAIM mit
   Herkunft, nie BEWEIS (KATALOG != SENSOR.

## 3. UNKNOWN != PASS im HashChainLedger

JEDE Stoerung fuehrt zu GENAU EINEM Record mit wert=null,
status=NICHT_GEPRUEFT, fehler_status und grund:
- NOT_CONFIGURED (kein API-Schluessel / kein Fetcher injiziert)
- QUARANTINE (Netz-/HTTP-Fehler, Wert ausserhalb Wertebereich)
- REJECTED (unbrauchbarer Typ usw.)
Test demonstriert das: drei schiefgegangene Abrufe => DREI
UNKNOWN-Records, Kette bleibt valid, NIEMALS 0 als Ersatzwert
(KEINE_STUMME_KORREKTUR).

## 4. Betrieb (bleibt Betreiber)

- Poll-Takt: z. B. cron alle 15 Minuten rufe NUR poll_once pro
  Metrik (Zeitfenster-Regeln aus dem Projekt gelten weiter).
- IEA-API-Schluessel als Umgebungsvariable des Runners, NICHT im
  Repo (KEINE_SECRETS).
- ABRUF == MOMENTAUFNAHME: IEA-Daten sind veroeffentlichte
  Katalogwerte in Monats-/Jahresaufloesung; ein 15-Minuten-Poll
  bringt KEINE neue Physik, nur aktualisierte Katalogwerte.

## 5. Vergleich mit FAO- und WHO-Adaptern (ehrlich)

- Auf main existieren WEDER ein FAO- NOCH ein WHO-Adapter; ihr Vorhanden
  wird NICHT behauptet (VISION_UNIMPLEMENTED != BEHAUPTET; Test
  verriegelt das mit Negativ-Sonden fao_poll/who_poll).
- Der IEA-Adapter formuliert das gemeinsame Protokoll
  (ADAPTER_PROTOCOL): poll_once + Metrik-Specs + UNKNOWN-Record +
  je Quelle ein eigener sensor_id-Namensraum. FAO (Ernaehrung/Land)
  und WHO (Gesundheit) wuerden denselben Pfad mit eigenen Specs und
  Quellen-Namensraeumen belegen - ein EIGENER abgeschlossener Bau
  bleibt ein eigener PR je Quelle, kein Phantom hier.

## 6. Ehrliche Grenzen

- SCRIPTED != INSTALLED, SAMPLE != BETRIEBSDAEMON.
- Zertifikate/Proxy-Eigenheiten des echten IEA-Endpunkts sind NICHT
  geprueft (KEINE ECHTEN Abrufe in diesem Lauf: Tests laufen ohne
  Netz mit Stub-Fetcher; der erste echte Abruf ist Teil der
  Betreiber-Inbetriebnahme, inklusive IEA-Lizenzpruefung).
- UNKNOWN-Records verlangsamen die Kette nicht, fuellen aber das
  Basin: eine Basin-Regel fuer UNKNOWN-Anteile bleibt offen.
