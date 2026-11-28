# V91 D2-Validierung 2026-11-28 (Vibe-Looplauf, ONE-SHOT verbraucht)

STATUS: NICHT_BESTANDEN (ehrlich). FN-Kriterium erfuellt, Macro-F1-Kriterium
verfehlt. KEIN_NACHFITTEN: Der One-Shot ist verbraucht, die Zahl bleibt
stehen. VALIDIERUNG != GUETEORM, VERGANGENHEIT != VORHERSAGE.

## Vorregistrierung (aus den Abschlussnotizen 25.-27.11.2026)

- Kriterium: Macro-F1 (Kaskade-Detektor, a priori, NICHT gefittet)
  >= 0.900 UND FN = 0 am reifen Fenster.
- Fenster: CI-Suiten ab 2026-11-27 15:48 UTC (Stichtag der
  Zurueckstellung).
- ONE-SHOT: genau EINE Auswertung; kein Nachfitten, kein zweiter
  Versuch auf demselben Fenster.

## Datenbasis (gemessen, oeffentliche Actions-API, kein Token)

- 137 Workflow-Runs seit 2026-11-27T15:48:00Z (28.11., ~06:30 UTC
  Abruf), daraus 44 vollstaendige CI-Suiten (Suite = alle Runs zu
  einem head_sha eines Branches; rot, wenn irgendein Run failure
  schliesst), 2 rote Suiten, 28 Folgepaare.
- Abgelegt als docs/cascade-history/v91-ci-suiten-2026-11-27-bis-28.jsonl
  (gleiches Format wie die Basis vom 23.-25.11.).
- Auswertung: controller/cascade_history_eval.py (REUSE, unveraendert).

## Ergebnis (Kaskade-Detektor, Vorwissen: vorherige Suite rot)

- Confusion: TP=1, FP=1, FN=0, TN=26.
- recall_red = 1.0, precision_red = 0.5, f1_red = 0.6667.
- f1_green = 0.9811, Macro-F1 = 0.8239.
- FN-Kriterium: ERFUELLT (0 verpasste ROT-Ziele; auch D2-Fenster:
  alle ROT-Ziele hatten eine rot vorherige Suite).
- Macro-F1-Kriterium: NICHT ERFUELLT (0.8239 < 0.900).
- Gesamturteil: D2 NICHT BESTANDEN.

Vergleichsfund (nur Kontext, KEINE Skala): Momentaufnahme 23.-25.11.
(n=43): Macro-F1 0.642, FN=0. Die Reparatur-Loop-These (ROT nach ROT
erkannt, muendet in Heilung) haelt auch im D2-Fenster; das
Praezisions-Problem (1 Fehlalarm) bleibt kleiner n und ist KEINE
Signifikanz.

## Ehrliche Grenzen

- n=28 Folgepaare, 1 rotes Ziel: KEINE_SIGNIFIKANZ_BEI_KLEINEM_N.
- Ein einzelner FP zieht Macro-F1 bei diesem n stark nach unten; das
  ist ein Befund der Momentaufnahme, kein Freibrief fuer Nachfittung.
- VERGANGENHEIT != VORHERSAGE, PROJEKTINTERN != ALLGEMEIN,
  SCRIPTED != RUNNING, UNKNOWN != PASS.
- Konsequenz: KEINE Produktionsfreigabe aus D2 (bleibt ohnehin an
  echte Messdaten #101/#103 gebunden). Eine D3-Vorregistrierung
  waere ein NEUER Beschluss (Betreiber oder naechster Lauf mit
  Begruendung), nicht eine Wiederholung von D2.

CLAIM != EVIDENCE: Jede Zahl hier stammt aus dem abgelegten JSONL
und ist mit dem Auswerter reproduzierbar (Tests pinnen sie).
