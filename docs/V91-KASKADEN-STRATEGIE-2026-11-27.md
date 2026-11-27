# V91 Kaskaden-Strategie 27.11.2026: Macro-F1 >= 0.900 (Weg, Negativfaelle, 12 Testfaelle)

STATUS: GEMESSEN - GEPLANT | IN-SAMPLE != VALIDIERT, HYPOTHESE != ZUSAGE,
VERGANGENHEIT != VORHERSAGE, FITTING WAERE UEBERZAHLIG.

Auftrag (Betreiber 27.11.2026): (1) Wie erreichen wir Macro-F1 >= 0.900?
(2) Negativ-Faelle und F1=0.000 erklaeren. (3) Naechste 12 Testfaelle
strategisch planen. Dieses Dokument beantwortet alle drei Punkte mit
Messung, nicht mit Behauptung.

## 1. Neue prospektive Datenbasis (25.-27.11.2026)

NEU abgelegt: docs/cascade-history/v91-ci-suiten-2026-11-25-bis-27.jsonl
(233 vollstaendige CI-Suiten, 29 rot, aus 661 Workflow-Runs seit dem
Messstand des ersten Fensters 25.11. ~01:30 UTC). Auswertung mit dem
UNVERAENDERTEN controller/cascade_history_eval.py (REUSE, kein
Zweitwerkzeug).

AUSWAHL-RAHMEN: dieses Fenster enthaelt ALLE Ereignistypen
(pull_request 437, push 218, schedule 6 Runs), das erste Fenster
enthielt nur pull_request. Vergleichbarkeit ist dadurch begrenzt
(RAHMEN != IDENTITAET). Anzahl abgeschlossener Suiten: 233.

## 2. Messergebnis neues Fenster (n=154 Folgepaare)

| Detektor | TP | FP | FN | TN | F1_rot | F1_gruen | MACRO F1 |
|---|---|---|---|---|---|---|---|
| ZEIT (gap<=30 min) | 13 | 116 | 0 | 25 | 0.183 | 0.301 | 0.2422 |
| KASKADE (vorher rot) | 13 | 16 | 0 | 125 | 0.619 | 0.940 | 0.7794 |
| KASKADE+GAP<=1.0 min | 13 | 5 | 0 | 136 | 0.839 | 0.982 | 0.9103 |

Kaskadenstruktur bleibt belegt: alle 13 ROT-Ziele folgten ROT (FN=0).
Heilungsquote nach ROT: 16/29 = 55.2 Prozent (erstes Fenster: 63.6).

## 3. Negativ-Faelle erklaert (Falsch-Alarme des Kaskaden-Detektors)

Die 16 Falsch-Alarme des Detektors KASKADE sind KEINE Detektor-Fehler
im Sinne blinden Rateverhaltens: der Detektor meldet ROT genau dann,
wenn die Vorgaenger-Suite rot war, und liegt damit in 13 von 29 Faellen
richtig (Precision 0.448). Die 16 Negativ-Faelle sind die HEILUNGEN:
Nach einer roten Suite wurde im naechsten Push der Fehler behoben und
die Suite gruen. Das ist der GEGENBEFUND aus Fenster 1 in Reinform:
Kaskaden muenden historisch ueberwiegend in Reparatur, nicht in
Aufschaukelung. Der Fehler-Masse des Detektors ist also genau die
Stelle, an der das System GESUND ist - ein Detektor, der Heilungen
nicht von Fortsetzung des Bruchs unterscheiden kann, muss falsch
liegen, solange beide Konstellationen real vorkommen.

Abhilfe ist NICHT Nachfitting am selben Fenster, sondern ein
zusaetzliches Merkmal, das Heilung von Fortsetzung trennt. Gemessen:
die GAP-Verteilung der 13 echten Kaskaden liegt zwischen 0.15 und
0.72 min (Median 0.38), die der 16 Heilungen zwischen 0.65 und 8.05
min (Median 1.28). Mechanistische Lesart: Fortsetzungs-Paare sind
ueblicherweise erneute Laeufe auf benachbarten Micro-Pushes des
laufenden Reparaturzyklus; Heilungen brauchen bewusste Commits. Diese
Lesart ist HYPOTHESE, kein Beweis.

## 4. F1 = 0.000 erklaert (Metrik-Mechanik)

Macro-F1 mittelt die F1-Werte der Klassen ROT und GRUEN. F1 einer
Klasse wird 0.000 in drei Faellen (Implementierung _safe_div im
Auswertungsmodul, nachlesbar):

1. TP=0 und FP>0 (Klasse nie richtig erkannt, aber oft behauptet):
   Precision 0, Recall 0 -> F1 0.000. Beispiel Negativkontrolle
   IMMER-ROT: prophezeit jede Suite rot; F1_gruen = 0.000, weil keine
   Suite als gruen durchgeht (siehe Testsonde).
2. TP=0 und FP=0 (Klasse nie vorhergesagt): _safe_div(0,0) = 0.0 ->
   F1 0.000. Beispiel: ein Detektor, der IMMER gruen prophezeit, hat
   F1_rot = 0.000 (und zeigt zugleich, dass Recall 1.000 auf der
   gruenen Klasse ihn NICHT brauchbar macht).
3. Klasse im Fenster gar nicht vertreten (kein ROT-Ziel): die
   Konvention zaehlt sie als F1 0.000 mit. Das ist eine ehrliche
   Metrik-GRENZE: Macro-F1 ueber unausgewogenen Fenstern ist
   empfindlich gegen leere Klassen (KEINE_SIGNIFIKANZ_BEI_KLEINEM_N).

F1=0.000 ist also KEIN Bug, sondern die haerte Grenze der Metrik:
sie benennt Klassen ohne einen einzigen echten Treffer. Der Wert 0.188
des ZEIT-Detektors im ersten Fenster war nahe daran: F1_gruen 0.056,
weil der billige Zeitdiskriminator fast alles als ROT prophezeit
(116 Falsch-Alarme im neuen Fenster).

## 5. Weg zu Macro-F1 >= 0.900 (ehrlich, prospektiv)

Der Wert 0.9103 fuer KASKADE+GAP<=1.0 ist AM GLEICHEN FENSTER
entstanden, das die Hypothese lieferte: IN-SAMPLE, KEINE VALIDIERUNG.
Ehrlicher Weg ist die Vorregistrierung vor dem naechsten Fenster:

- D1 KASKADE (vorher rot): Baseline, erwartetes Niveau ~0.78.
- D2 KASKADE+GAP<=1.0 min: Hauptkandidat (runde Schwelle, mechanistisch
  begruendet, NICHT an die gemessene 0.72/0.95-Trennschaefe gefittet).
- D3 KASKADE+GAP<=0.5 min: robustere Variante (im Sample: FN=4,
  Macro 0.902; zeigt die Precision/Recall-Spanne).
- D4 ZEIT: Negativkontrolle.

ERFOLGSKRITERIUM (vorregistriert): D2 erreicht Macro-F1 >= 0.900 im
NAECHSTEN Fenster (Suiten nach 27.11.2026, gleiche Suite-Definition,
gleiche Auswertung) bei FN=0. VERFEHLT D2, gilt ONE-SHOT: KEIN
Nachjustieren der Schwelle am selben Fenster (waere UEBERZAHLIG),
Ergebnis wird offen dokumentiert. 0.900 ist Zielwert, kein Beweis
irgendeiner Guete (ZIELWERT != ERREICHUNG).

## 6. Naechste 12 Testfaelle (strategischer Plan, vorregistriert)

Jeder Fall benennt Konstellation, erwartete Detektorzelle und Zweck.
Sie werden im naechsten Fenster gezaehlt (real, nicht synthetisch):

1. ROT->ROT, GAP<=0.5 min: Kern-Kaskade. Erwartung: TP fuer D1-D3.
   Zweck: bestaetigt Fortsetzungsthese.
2. ROT->ROT, GAP 0.5-1.0 min: Randzone der Schwelle. Erwartung: TP
   fuer D2/D3-Kritik. Zweck: belastet die runde Schwelle.
3. ROT->GRUEN, GAP<=1.0 min: Schnellheilung. Erwartung: FP fuer D2.
   Zweck: misst Precision-Risiko der GAP-Regel (5 solcher Faelle im
   aktuellen Fenster).
4. ROT->GRUEN, GAP 1-10 min: bewusste Reparatur. Erwartung: FP fuer
   D1, korrekt GRUEN fuer D2. Zweck: Trenngewinn der GAP-Regel.
5. ROT->GRUEN, GAP>60 min: Overnight-Heilung. Erwartung: TN fuer D2.
   Zweck: Stabilitaet bei langen Pausen.
6. GRUEN->ROT ohne Vorbelastung: frischer Bug. Erwartung: FN-Risiko
   fuer ALLE Detektoren (D1 sagt GRUEN). Zweck: belastet die FN=0-These;
   ein einziger Fall kann F1_rot brechen.
7. GRUEN->GRUEN Normalfall: TN-Masse. Zweck: Baseline-Stabilitaet und
   Green-Klasse-F1.
8. ROT als LETZTE Suite im Branch: kein Paar. Zweck: zaehlt
   Ausschluss-Regel (kein Zaehler-Shift durch Randeffekte).
9. Abgebrochene/unvollstaendige Suite (UNKNOWN): ausgeschlossen und
   gezaehlt. Zweck: UNKNOWN != PASS bleibt messbar.
10. Multifehler-Suite (>=2 Jobs rot) mit Nachfolger: prueft, ob
    Mehrfachbrueche andere GAP-Struktur zeigen (Fallpraegung #529).
11. Fenstergrenz-Paar (Vorgaenger vor, Ziel nach Fensterbeginn):
    vorregistrierte Regel: Paar zaehlt nur, wenn BEIDE Suiten im
    Fenster liegen. Zweck: reproduzierbare Fenstertechnik.
12. Negativkontrolle IMMER-ROT als Detektor-Variante (METRIK-SONDE,
    KEINE Empfehlung): F1_gruen=0.000 nach Abschnitt 4. Zweck: die
   Metrik-Mechanik bleibt gegen Zufalls-Hochwerte gesperrt.

Faelle 1-5 laden die D2-Validierung direkt, Fall 6 ist die wichtigste
Falsch-These (FN), Faelles 8-11 sichern Messtechnik, Fall 12 sichert
die Metrik. Synthetische Faelle werden NICHT gebaut: die Basis ist
die echte Actions-Historie des eigenen Repos.

## 7. Ehrliche Grenzen

- IN-SAMPLE != VALIDIERT: 0.9103 ist am Hypothesen-Fenster gemessen.
- n=154 Paare, EIN Repositorium, zwei Workflows, Momentaufnahme.
- GAP-Merkmal ist korreliert mit Arbeitsstil des Betreibers/der
  Agenten (Reparatur-Rhythmus), NICHT mit einer Naturkonstante.
- 0.900 ist ein Zielwert auf dieser Metrik, kein Qualitaetsgesetz;
  die Heilungs-Mehrheit ist der GEGENBEFUND, der jede rein
  Kaskaden-basierte ROC-Optimierung begrenzt.
- Kein Kaskaden-Detektor fuer Domainslasten (cumulative_stress.py
  bleibt unberuehrt); kein Netz im Auswertungsmodul.
