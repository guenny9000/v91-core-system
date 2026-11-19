# V91-RUNBOOK: Mess-Pilot Alsfeld / Vogelsberg (Issue #101)

Status: ENTWURF / DOKUMENTIERT (19.11.2026) | Autor: Sebastian Guenter | Review: Vibe
(Knoten B)

Dieser Runbook-Entwurf ist Sebastians Konzept wortgetreu uebernommen und wird
als verbindliches Dokument gepflegt (#209/Regelwerk-Praxis wie #165/#14). Er
beschreibt den Mess-Piloten; er begruendet KEINE vollzogene Messung. SCRIPTED
!= INSTALLED, DOKUMENTIERT != GEMESSEN. V91 fuehrt keine Politik aus und
greift in keine fremden Systeme ein. Reviews-Anhang am Ende enthaelt den
ehrlichen main-Abgleich inklusive Ueberlappung mit messwerte_ingest (#200).

---

## V91-RUNBOOK-ENTWURF - Mess-Pilot Alsfeld / Vogelsberg (Issue #101)

Ausgelegt auf Determinismus, schmale lokale Ressourcen, saubere Trennung von
MESSUNG und DATASET sowie Fail-Closed-Verhalten.

### 1. Grundprinzipien des Mess-Piloten

- MESSUNG != DATASET: Jede Zeile in den Rohdaten dokumentiert einen
  tatsaechlichen lokalen Messvorgang inklusive Quellen- und Sensorstatus -
  niemals ein geschaetztes, interpoliertes oder aus Landesdaten uebertragenes
  Ersatzdatum.
- Determinismus & Reproduzierbarkeit: Feste Schemata, explizite Einheiten,
  UTC-Zeitstempel nach ISO-8601 (YYYY-MM-DDTHH:MM:SSZ) und klare Fehlercodes
  bei Ausfaellen.
- Ressourcenschonung & Autarkie: Schlanke, lokale Skripte ohne schwere
  Hintergrunddienste oder externe Cloud-Pflicht; Ausfaelle einzelner Sensoren
  oder Netzstrecken duerfen den Lauf nicht abbrechen, sondern muessen als
  UNKNOWN oder ERROR protokolliert werden.

### 2. Messpunkte & Zielbereiche (Alsfeld / Vogelsberg)

Die Messpunkte lassen sich modulweise aktivieren, je nachdem welche Sensoren,
Schnittstellen oder lokalen Pruefungen am Standort tatsächlich angebunden
sind:

| Messpunkt-ID | Saeule / Bereich | Was wird konkret gemessen? | Einheit / Format | Fail-Closed-Verhalten bei Ausfall |
| --- | --- | --- | --- | --- |
| VB-ENERGIE-01 | Energie | Lokale Erzeugungs- oder Zaehlerwerte (sofern lokal ausgelesen) | kW / kWh (Zahl) | Status UNKNOWN, kein Rueckgriff auf MaStR- oder Landeswerte |
| VB-NETZ-01 | Digitalisierung | Erreichbarkeit, Paketverlust und Latenz definierter lokaler/externer Ziele | ms / % / bool | Status DEGRADED oder OFFLINE mit exaktem Timeout-Grund |
| VB-SYS-01 | System / Betrieb | Lokale Knoten-Telemetrie (Speicher, CPU-/I/O-Auslastung, Laufzeit) | % / MB / s | Status ERROR bei Lesefehler, kein Schaetzwert |
| VB-UMWELT-01 | Wasser / Umwelt | Lokale Messwerte vorhandener Sensoren (z. B. Temperatur, Feuchte, Pegel) | Grad C / % / mm | Status UNKNOWN bei fehlendem Sensor-Handshake |

Wichtig: Nicht angebundene Messpunkte werden nicht simuliert oder durch
Durchschnittswerte ersetzt, sondern explizit als NOT_CONFIGURED oder
SENSOR_MISSING gefuehrt.

### 3. Rohdaten-Format & Integritaetskette

Fuer jedes Messintervall wird ein Datensatz im JSON Lines (.jsonl)-Format
append-only (nur anhaengend, kein Ueberschreiben bestehender Zeilen)
geschrieben:

```json
{
  "schema_version": "1.0",
  "pilot_id": "alsfeld-vogelsberg-issue-101",
  "seq": 1042,
  "timestamp_utc": "2026-11-19T20:15:00Z",
  "host_id": "local-node-01",
  "metric_id": "VB-NETZ-01",
  "status": "OK",
  "value": 18.4,
  "unit": "ms",
  "prev_hash": "sha256:8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
  "entry_hash": "sha256:4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
}
```

- seq: Streng monoton steigende Laufnummer je Log-Datei (hilft beim Erkennen
  fehlender oder doppelt geschriebener Eintraege).
- prev_hash & entry_hash: Verkettung ueber SHA-256 (entry_hash berechnet ueber
  den kanonisierten Datensatz inklusive prev_hash). Manipulationen oder
  abgeschnittene Zeilen fallen bei der Pruefung sofort auf.
- Trennung der Artefakte:
  - raw/ - Unveraenderliche .jsonl-Rohprotokolle.
  - verified/ - Pruefergebnisse und Validierungsberichte (Hash-Ketten-Check,
    Plausibilitaet).
  - derived/ - Optionale Aggregationen (streng getrennt, niemals als
    Rohmessung ausgegeben).

### 4. Fail-Closed-Regeln & Betriebsablauf

- Vor dem Schreiben (Pre-Check):
  - Pruefen, ob Zielverzeichnis beschreibbar ist und genuegend freier
    Speicher vorhanden ist.
  - Letzten entry_hash aus dem bestehenden Log lesen; falls die letzte Zeile
    korrupt ist, neuen Block mit markiertem Bruch (chain_break_detected: true)
    beginnen statt stillschweigend weiterzuketten.
- Waehrend der Messung:
  - Klare Timeouts setzen, damit haengende Abfragen den Zyklus nicht
    blockieren.
  - Werte gegen physikalische/logische Grenzen pruefen (z. B. negative Latenz
    oder unmoegliche Sensorwerte als OUT_OF_RANGE kennzeichnen).
- Nach dem Schreiben (Post-Check):
  - Verifizieren, dass die Zeile vollstaendig mit Zeilenumbruch geschrieben
    wurde und entry_hash reproduzierbar ist.
  - Bei Schreibfehlern (ENOSPC, Berechtigung, I/O-Fehler) sofort einen
    Fehlerzustand melden und den Lauf sauber beenden - kein stilles
    Verwerfen.
- Auswertung (PASS / REVIEW_REQUIRED / FAIL):
  - Ein Messlauf gilt nur dann als vollstaendig verifiziert, wenn Hash-Kette
    intakt ist und Messluecken (UNKNOWN / ERROR) offen ausgewiesen sind.
  - Offene Kriterien oder fehlende lokale Sensoren bleiben sichtbar
    (UNKNOWN != PASS).

### 5. Konkrete Checkliste fuer den Start des Pilotlaufs

- Messpunkte festlegen: Entscheiden, welche der 4 Messpunkt-IDs
  (VB-ENERGIE-01, VB-NETZ-01, VB-SYS-01, VB-UMWELT-01) im ersten Durchlauf
  wirklich aktiv sind.
- Verzeichnis- & Log-Struktur anlegen: raw/, verified/ und derived/ trennen
  und ein Test-Intervall (z. B. alle 5 oder 15 Minuten) fahren.
- Hash-Kette validieren: Nach den ersten 10-20 Eintraegen einmal die
  Verkettung (prev_hash -> entry_hash) und die seq-Reihenfolge pruefen.
- Abgrenzung zu PR #212 / #213 sichern: Im Dokumentations-Eintrag klar
  festhalten, welche Werte aus dem Pilotlauf stammen (MESSUNG) und welche
  aus Landes-/Bundesdaten (DATASET).

---

## Reviews-Anhang (Vibe, ehrlicher main-Abgleich, 19.11.2026)

Bausteine auf main, die diesen Runbook tragen bzw. ueberlappen (ehrlich):

- controller/messwerte_ingest.py (#200) implementiert bereits einen
  append-only-SHA-256-geketteten JSONL-Pfad mit fsync, streng monotonem seq,
  prev_hash/entry_hash, Tamper-Verweigerung und Evidenz-Referenz - und
  akzeptiert Einzelwerte NUR gegen einen validierten Indikator einer
  geprueften Messmatrix (R2-Reihe #194/#198/#199/#207/#208). NO_DUPLICATE_
  SYSTEMS-Konsequenz: Der Pilot erzeugt KEIN zweites Ingest-Modul. Rolle des
  Piloten ist die lokale Rohdatenerfassung (raw/);punkteeweise Aufnahme in
  die Messwerte-Reihe erfolgt ausschliesslich ueber messwerte_ingest gegen
  eine dafuer validierte Messmatrix. MESSUNG != DATASET bleibt gewahrt.
- controller/measurement_* (core/ingest/monitor/pipeline/quarantine/store)
  und der Alsfeld-Knoten-Runbook-Review in Issue #101 (v93/v95, Watchdog,
  Least-Privilege, Alarm-Pfad) sind der Betriebsrahmen am Standort; dessen
  kritische Korrekturen (sd_notify-Heartbeat, kein Default-root mit
  Nice=-10, Alert-Pfad ohne WORM-Behauptung) gelten unvermindert auch fuer
  diesen Mess-Piloten.
- controller/ledger.py (SHA-512-Kette) und worm_ledger bleiben getrennte
  Systeme; der Pilot baut keine vierte Kette-Kategorie.
- Hessen-Reihe (#211/#212/#213) bleibt DATASET: Ihre Werte sind keine
  Messwerte und wandern nie in raw/.

Was NICHT existiert (ehrlich, ohne Ausrede):

- Der Mess-Pilot ist ein ENTWURF: kein Sensor angebunden, kein Intervalllauf,
  keine Zeile in raw/. SCRIPTED != INSTALLED; der erste echte Lauf benoetigt
  einen kleinen, CI-geprueften Skript-PR und die physische Anbindung am
  Standort (nur Sebastian ausfuehrbar).
- Keine Messmatrix fuer VB-* : Fuer eine Aufnahme in messwerte_ingest muesste
  zunaechst eine Messmatrix mit Indikatoren VB-ENERGIE-01/VB-NETZ-01/
  VB-SYS-01/VB-UMWELT-01 validiert werden (R2-Praxis).
- Der JSON-Beispieldatensatz in Abschnitt 3 ist ILLUSTRATIV: Die
  Beispiel-Hashes sind keine tatsaechlich verketteten Werte, der Zeitstempel
  ist ein Beispiel. Wortgetreu-Anpassung transparent: Die im Operatortext
  deutschen Anfuehrungszeichen im JSON-Beispiel wurden fuer Maschinenlesbarkeit
  durch gerade Anfuehrungszeichen ersetzt; sonst ist der Text unveraendert.

Grenzen (dauerhaft):

- REVIEW != ENTSCHEIDUNG; UNKNOWN != PASS; Werte ohne lokalen Messvorgang
  bleiben UNKNOWN (kein Rueckgriff auf MaStR/Landeswerte, deckungsgleich
  mit Abschnitt 1).
- SAFETY > STABILITY; keine autonomen Gewalt- oder Zwangsmassnahmen; keine
  Eingriffe in fremde Systeme; demokratische Verfahren only.

Arbeitsauftrag daraus (naechste konkrete Schritte, CI-geprueft):

1. Messmatrix fuer die VB-*-Messpunkte als validiertes Dataset (R2-Praxis).
2. Schmaler Pilot-Skript-PR (Rohdaten-Writer mit Pre/Post-Check), lokal auf
   SOLAR-DESKTOP-01 von Sebastian testbar.
3. Erster Kurzlauf (10-20 Eintraege), danach Hash-Ketten-Validierung
   (Checkliste Abschnitt 5).
