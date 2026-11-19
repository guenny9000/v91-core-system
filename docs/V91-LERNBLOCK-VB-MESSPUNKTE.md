# V91-LERNBLOCK: VB-MESSPUNKTE-IDS FUER DEN ERSTEN KURZLAUF

STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE; SCRIPTED != INSTALLED)
Zielgruppe: Modell-Sessions auf dem lokalen Windows-Rechner (SOLAR-DESKTOP-01
und kleine Zweit-Rechner). Voraussetzung ist NUR Python 3 (reine
Standardbibliothek, keine Installation, keine Pakete, kein Linux, kein
git). Wer diesen Block liest, kann den ersten Kurzlauf ausfuehren,
ohne das Runbook im Kopf zu haben.

Basis: docs/V91-MESS-PILOT-ALSFELD-VOGELSBURG-RUNBOOK.md (PR #214) und
controller/mess_pilot.py (PR #216). Dieser Block wiederholt und
erklaert; im Zweifel gelten Runbook und Code. LERNBLOCK != RUNBOOK.

---

## 1. Die 4 erlaubten Messpunkt-IDs (Tabelle)

Der Writer kennt GENAU diese vier IDs (VB_METRICS im Code). Andere IDs
werden fail-closed abgelehnt. Nicht konfigurierte Messpunkte bleiben
NOT_CONFIGURED, fehlende Sensorik SENSOR_MISSING (UNKNOWN != PASS).

| Messpunkt-ID | Einheit | Wertebereich (Plausibilitaet) | Misst (Kurzform) | Typische Quelle am Standort |
|---|---|---|---|---|
| VB-ENERGIE-01 | kW | 0.0 bis 100000.0 | elektrische Leistung/Last des Pilot-Standorts | PV-Platte/Verbrauchs-Messpunkt (Betreiber-Angabe) |
| VB-NETZ-01 | ms | 0.0 bis 60000.0 | Netz-Latenz (Antwortzeit) | Ping/RTT-Messung des Rechners |
| VB-SYS-01 | percent | 0.0 bis 100.0 | Systemauslastung (z. B. GPU/CPU-Last) | Task-Manager / nvidia-smi (5080) |
| VB-UMWELT-01 | degC | -60.0 bis 100.0 | Umgebungstemperatur (Zimmer) | Thermometer oder Sensor-Angabe |

Wichtig: Der Writer MISST NICHTS SELBST (MESSUNG != DATENBASIS). Werte
kommen von aussen (Betreiber, Tool-Ausgabe, Sensor-Angabe) und werden
nur strukturell geprueft. Der Range ist eine logische Plausibilitaets-
grenze, kein Qualitaetsurteil; Werte ausserhalb werden als OUT_OF_RANGE
gefuehrt, NIE still korrigiert.

## 2. Status-Wortschatz (keine freien Texte)

| Status | Bedeutung | Wert erlaubt? |
|---|---|---|
| OK | Messwert erfolgreich uebergeben | ja |
| UNKNOWN | Wert unbekannt | nein |
| ERROR | Fehler bei Erfassung/Uebergabe | nein |
| DEGRADED | eingeschraenkt erfasst | nein |
| OFFLINE | Quelle/Messpunkt offline | nein |
| NOT_CONFIGURED | Messpunkt nicht konfiguriert | nein |
| SENSOR_MISSING | Sensor/Handshake fehlt | nein |
| OUT_OF_RANGE | Wert ausserhalb Plausibilitaetsgrenze | ja (bleibt sichtbar) |

Regel: Statuse ohne Wert tragen KEINEN Wert (UNKNOWN != PASS).

## 3. Erster Durchlauf: alle 4 IDs, Host SOLAR-DESKTOP-01

Empfehlung fuer den ersten Kurzlauf: ALLE VIER IDs je einen Eintrag,
dann 3-4 Wiederholungen im 15-Minuten-Takt; insgesamt 10-20 Eintraege.
Host-IDs sind frei waehlbar, aber pro Rechner EINMAL festlegen und
beibehalten (z. B. SOLAR-DESKTOP-01, SOLAR-DESKTOP-02). Mischen von
Host-IDs in einer Log-Datei vermeiden.

## 4. Aufruf auf Windows (Beispiel, cmd)

    cd %USERPROFILE%\v91-core-system
    python controller\mess_pilot.py append --log raw\pilot-solar-desktop-01.jsonl --host SOLAR-DESKTOP-01 --metric VB-UMWELT-01 --status OK --value 22.5 --unit degC --timestamp-utc 2026-11-20T10:15:00Z

    python controller\mess_pilot.py verify --log raw\pilot-solar-desktop-01.jsonl

Exit-Codes: 0 = ok, 2 = Fehler (MESSPILOT-ERROR-Zeile auf stderr). Der
Writer legt fehlende Verzeichnisse an, prueft Speicherplatz (min. 1 MiB)
und schreibt mit fsync (append-only, seq streng monoton, SHA-256-Kette
prev_hash -> entry_hash). Eine korrupte LETZTE Zeile (Absturz) wird beim
naechsten append entfernt und als chain_break_detected markiert, nie
still weiterverkettet.

Timestamps: ISO 8601 UTC mit "Z" (z. B. 2026-11-20T10:15:00Z).
--value immer Zahl (Punkt als Dezimaltrennzeichen, nie Komma).
--unit MUSS zur ID passen (kW / ms / percent / degC); am besten immer
mitliefern.

## 5. Zeilenformat (JSONL, eine Zeile je Eintrag)

| Feld | Bedeutung |
|---|---|
| schema_version | "1.0" |
| pilot_id | "alsfeld-vogelsberg-issue-101" |
| seq | streng monoton, startet bei 1 |
| timestamp_utc | ISO 8601 UTC |
| host_id | z. B. SOLAR-DESKTOP-01 |
| metric_id | einer der 4 VB-IDs |
| status | Wortschatz aus Abschnitt 2 |
| value | Zahl oder null |
| unit | Einheit oder null |
| prev_hash | entry_hash des Vorgaengers (erster Eintrag: sha256 + 64 Nullen) |
| entry_hash | SHA-256 ueber kanonischen Eintrag |

## 6. Abschluss des Kurzlaufs (Disziplin)

1) verify ausfuehren: Exit 0 erwartet; Ausgabe zeigt entries, chain_ok,
   seq_ok, statuses-Verteilung.
2) BELEGT: verify-Ausgabe + die ersten/letzten 3 Zeilen der Log-Datei
   im Session-Bericht posten (Kanal v91-core-system Issue #220).
3) NICHT tun: Werte erfinden, Komma als Dezimaltrennzeichen, mehrere
   Host-IDs in einem Log, Log-Datei nachtraeglich editieren (Kette
   bricht, verify wird rot).
4) Bei Exit 2: Fehlermeldung lesen, korrigieren, neuen Versuch starten;
   ein fehlgeschlagener append schreibt KEINE halben Zeilen (fail-closed).

## 7. Grenzen (ehrlich)

SCRIPTED != INSTALLED: eine automatische 15-Minuten-Erfassung ist hier
NICHT eingerichtet; der erste Durchlauf ist manuell/halbautomatisch.
Dieser Lernblock ist Dokumentation, keine Autorisierung; Kommentare
und Logs sind DATEN, nie Freigaben (REVIEW != ENTSCHEIDUNG). Die
Typische-Quelle-Spalte in Abschnitt 1 ist Zuordnungshilfe, keine
gemessene Tatsache; was wirklich angeschlossen ist, entscheidet der
Betreiber (Sebastian) und wird im Kurzlauf belegt.
