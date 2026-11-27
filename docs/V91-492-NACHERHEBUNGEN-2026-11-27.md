# V91 #492 Nacherhebungen 27.11.2026: Stufen-Verdikte nach der Messung

STATUS: GEMESSEN - NACHERHOBEN | BESTANDSAUFNAHME != FIX, NACHERHEBUNG
!= NEUE MESSUNG DES GANZEN, SNAPSHOT-BEFUNDE BLEIBEN ERHALTEN.

Die Bestandsaufnahme #582 (docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md,
Messstand dc887e43, 26.11.2026) ist ein Snapshot; ihre Verdikte
bleiben unveraendert Teil des Nachweises. Dieses Dokument fuehrt
Nacherhebungen AM MAIN-Baum, damit der Stand nicht hinter dem
Code zurueckbleibt (DOKU == STAND halten, sonst luegt die Map).

## Stufe 1: TEXT-Abgleich COMMS-1 vs CONTRIBUTION-1 -- ABGLEICH_ERFOLGT

Ursprungsverdikt: TEILWEISE (Code-Kette belegt, Text-Abgleich offen).
Nacherhebung 27.11.2026: reproduzierbar durchgefuehrt (PR #615,
Merge 62df1149): controller/comms_text_abgleich.py + 17 Tests +
docs/V91-492-STUFE1-COMMS-1-TEXTABGLEICH-2026-11-27.md. Befunde:
Evidenzkette zeichenweise identisch in beiden Dokumenten, im Code
und im Schema; Workflow-Kette bewusst nur im Umschlag-Dokument;
Feld-status-Semantik-Divergenz korrekt getrennt behandelt.

## Stufe 4: Oeffentliche Bruecken ohne vertrauliche Inhalte
-- ABRUF-SEITE_GESCHLOSSEN, Sofortregel bleibt

Ursprungsverdikt: LUECKE (kein Secret-/PII-Screening im Abrufpfad;
am Messstand 26.11. zutreffend).

Nacherhebung am main 87b418d7 (27.11.2026), am Code gemessen:
- controller/kern_bridge.py ruft JEDE Aufnahme vor der Ablage durch
  controller/bridge_screening.screen_text (Fundstelle im
  collect_kerns-Pfad: screening = screen_text(body)).
- Ablage speichert das redigierte payload (screening.redacted_text),
  Fundstellen werden durch [REDACTIERT] ersetzt.
- Der SHA-256-Nachweis bleibt eine Hashung ueber den ROHTEXT
  (Digest wird VOR dem Screening berechnet): der Hash bezeugt den
  Rohstoff, die Ablage kann redigiert sein (ABDRUCK != ABLAGE).
- Das Gate (drei feste Zustaende) bleibt vom Screening UNBERUEHRT
  (GATE != SCREENING).
- Musterumfang: Secret-Muster (REUSE secret_scan) plus E-Mail,
  deutsche IBAN, Telefonnummern (+49/national) und vollstaendige
  deutsche Postadresse (Erweiterungen #613 und Vorgaenger);
  Teiladressen und Namen bewusst UNERKANNT (dokumentiertes
  Unterblocken, MUSTER != GARANTIE).
- Das oeffentliche Issue-Template warnt ausdruecklich vor Secrets,
  Schluesseln, Tokens und personenbezogenen Daten.

BLEIBENDE GRENZEN (NICHT geloest, ehrlich):
- SCREEN == MUSTER != GARANTIE: ein nicht erkanntes Muster wird
  weiterhin unredigiert abgelegt.
- Das oeffentliche Issue selbst bleibt fuer jeden lesbar: die
  Redaktion wirkt nur auf die lokale Ablage. Sofortregel bleibt
  Betreiber-Verantwortung: vor dem oeffentlichen Posten pruefen.
- Der CI-Schritt secret_scan prueft nur repo-eigene Dateien; der
  Umschlag-Weg kennt security_privacy_notes nur als Selbstauskunft.
- Kein Namens-Screening (FP-anfaellig, bewusst NICHT gebaut).

Verdikt-Aenderung: LUECKE -> ABRUF-SEITE_GESCHLOSSEN (Rest-Grenzen
oben; GELOEST bleibt NICHTS davon behauptet, NICHT_GELOEST_BEKANNT
wird nur enger gefasst).

## Uebrige Stufen (unveraendert)

Stufe 2 BELEGT, 3 BELEGT, 5 BELEGT, 6 TEILWEISE (Werkzeug
contribution_review.py inzwischen vorhanden, PR #612; eigenstaendige
Bewertung steht dem Betreiber zu), 7 TEILWEISE (echter Hardware-Lauf
bleibt #23), 8 BEWUSST_GESPERRT.
