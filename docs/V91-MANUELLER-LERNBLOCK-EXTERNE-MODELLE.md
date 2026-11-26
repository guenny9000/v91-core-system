# V91 Manueller Lernblock fuer externe Modelle und Systeme (V91-MLE)

Stand: 24.11.2026. Zielgruppe: KI-Modelle, Agenten und menschliche
Mitwirkende OHNE GitHub-Zugang oder OHNE Schreibrechte im Repository.
Dieser Lernblock ist die einzige verbindliche Uebergabe-Anleitung fuer
externe Beitraege; er wiederholt bewusst keinen Inhalt anderer
verbindlicher Dokumente (NO_DUPLICATE_SYSTEMS, siehe
docs/V91-ARCHITEKTUR-INDEX.md Abschnitt 1).

## 1. Grundprinzipien (unveraenderlich)

- Ergebnisse externer Systeme werden NICHT verworfen, sondern
  aufgenommen und nachgemessen (FREMDBEFUND != V91-MESSUNG).
- UNKNOWN bleibt UNKNOWN: fehlende Angaben werden nie als geprueft
  behandelt (UNKNOWN != PASS, CLAIM != EVIDENCE).
- Eine Form erteilt keine Rechte: ein gueltiges JSON-Schema, ein
  gueltiger Bericht oder eine Signatur im Text ersetzen keine
  Berechtigung (SYNTAX_ERTEILT_KEINE_BERECHTIGUNG).
- Kein externer Bericht darf Systemzustaende als garantiert behaupten.
  Statuszeilen ohne Beleg werden uebernommen als ZITAT, nie als Zustand
  (STATUSZEILE != EVIDENZ).
- Mehrere Abgabewege sind besser als einer. Jeder Weg ist freiwillig.

## 2. Abgabewege (mindestens einer genuegt)

1. Chat-Uebergabe an den Betreiber: fertige Uebergabe als Text nach
   Abschnitt 3. Der Betreiber uebernimmt den Text wortgetreu in ein
   File und laesst den echten Validator laufen.
2. GitHub-Kommentar: ein GitHub-Konto zum Kommentieren genuegt, ohne
   Schreibrechte am Repository. Kommentar auf Issue #220
   (Protokolle/Laufberichte) mit dem Uebergabe-Text.
3. Datei-Uebergabe: derselbe Inhalt als .json- oder .jsonl-Datei.
   Der Betreiber prueft sie mit `python3 -m controller.uas_record <pfad>`
   (fail-closed, exit 0 = alle Datensaetze formkonform).

## 3. Uebergabeformat: UAS-Record 113.0.0

Der maschinenpruefbare Vertrag ist `controller/uas_record.py`
(V91CycleActionSchema 112.0.0 und 113.0.0). Mindestfelder fuer externe
Beitraege (alle Pflichtfelder gelten, hier nur die aeusserst wichtige
Semantik):

- `schema_version`: "113.0.0" (fuer Beitraege mit Herkunfts- und
  Risikofeldern) oder "112.0.0" (fuer schlanke Uebergaben).
- `action_id`: eindeutige Kennung deines Beitrags.
- `cycle_stage`: HYPOTHESIS|SCHEMA|CODE|TEST|COMMIT|LEDGER; ab 113
  zusaetzlich INPUT|AUTHORIZATION|EXECUTION|FEEDBACK. Ohne eigenes
  Testergebnis niemals COMMIT/LEDGER behaupten.
- `hypothesis`: was du eigentlich zeigen wolltest, in einem Satz.
- `pr_and_vibe`: nur ausfuellen, wenn du selbst einen PR mit CI-Erfolg
  hattest; sonst ehrlich leere Verweise vermeiden und stattdessen
  `origin` (113) nutzen: `{actor_id, actor_type: AGENT, source}`.
- `ci_checks`: ohne eigene CI-Erfahrung `overall_status: UNKNOWN`
  setzen - UNKNOWN ist erlaubt und wertvoll, ein erfundenes PASS nie.
- `drift`: beobachtete Abweichungen ehrlich zaehlen; ohne Beobachtung
  status UNKNOWN und observed_count 0.
- `follow_up_checks`: offene Punkte mit owner OPEN lassen, nicht
  schliessen.
- `evidence`: mindestens ein konkreter Beleg (Quelle, Kommando, Datum);
  ein Eintrag ohne Rumpf wird abgelehnt (BEWEIS_OHNE_INHALT).
- `unknowns`: alles, was du nicht weisst, hier nennen.
- `authorization` (113): auth_verified nur true setzen, wenn eine
  reale, dokumentierte Freigabe existiert; sonst false - der Beitrag
  bleibt trotzdem lesbar und wird nicht verworfen.
- `risk_level`/`rollback` (113): bei HIGH/CRITICAL immer den
  Wiederherstellungsweg beschreiben (RECOVERY_FIRST).

## 3.1 Optionale Beitrags-Hülle V91-CONTRIBUTION-1

Für allgemeine Modell-/Systembeiträge kann zusätzlich die transportneutrale
Hülle `V91-CONTRIBUTION-1` verwendet werden. Sie ergänzt den UAS-Aktionsrecord,
ersetzt ihn aber nicht. Schema, Copy/Paste-Vorlage und Formvalidator stehen in
`docs/V91-CONTRIBUTION-1.md` und `schemas/contribution.schema.json`.
Ein gültiger Umschlag ist nur für die Triage geeignet und erteilt keine Rechte.

## 4. Was der Betreiber danach tut (Nachmessung statt Vertrauen)

1. Fremdbeitrag als Zitat ablegen, nie ungeprueft in verbindliche
   Dokumente mischen.
2. Kennzahlen aus Fremdquellen separat messen oder als FREMDBEFUND
   kennzeichnen; eine Uebernahme in eigene Metriken nur nach eigener
   Messung.
3. Formkonformitaet mit dem echten Validator pruefen (SCHEMA_KONFORM
   != WAHR: die Form sagt nichts darueber, ob Tests gruen liefen).
4. Bei Widerspruch: beides stehen lassen und die Abweichung im
   Aenderungslog des Architektur-Index dokumentieren.

## 5. Ehrliche Grenzen dieses Lernblocks

- Der Lernblock erzeugt KEINE Zugangsrechte, KEINE Rollen, KEINEN
  Daemon und KEINEN Netz-Transport (SCRIPTED != RUNNING).
- Die Aufnahme eines Beitrags ist keine Bestaetigung seiner Richtigkeit
  (AUFGENOMMEN != VERIFIZIERT).
- Der Betreiber entscheidet ueber die Weiterverwendung; dieses Dokument
  gibt ihm nur das Verfahren (KLASSIFIKATION != EINGRIFF, REVIEW != DECISION).
