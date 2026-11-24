# V91 / MAX-BEST: Rechenbeispiele zum Mathematischen Kern

Version 1.0 | 24.11.2026 | Passt zu docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md
und dessen ausfuehrbarer Form controller/max_best_rechner.py
(ausfuehrbar; die CLI lautet: python3 -m controller.max_best_rechner eingabe.json).

STATUS: RECHNENBEISPIELE mit ANNAHMEN | ANNAHME != MESSUNG,
EINGABE == ANGABE != BEWEIS, RECHNEN != ENTSCHEIDEN. Jede Zahl in
diesen Beispielen ist eine ANNAHME zur Vorfuehrung der Formelwirkung,
kein V91-Messwert. Echte Messwerte entstehen nur in den Mess- und
Pruefmodulen des Controllers und landen im Ledger.

## Beispiel 1: Gesamtnutzen zweier Varianten (Abschnitt-1-Regel)

    max U = Nutzen - Schaden - Aufwand
    Variante A:  U = 80 - 5 - 15 = 60     -> groesser
    Variante B:  U = 90 - 8 - 30 = 52

    {"gesamtnutzen": {"nutzen": 80, "schaden": 5, "aufwand": 15}}

WICHTIG: 60 > 52 empfiehlt A NICHT automatisch: Menschenwuerde,
Sicherheit und Rechte stehen lexikographisch VOR der Rechnung und
sind nicht teilbar oder handelbar. Der Rechner entscheidet nichts
(RECHNEN != ENTSCHEIDEN); dies bleibt Betreiber-/Policy-Pruefung.

## Beispiel 2: Risiko und Restrisiko (Abschnitt-2-Formeln)

    Risiko        R = p x S
    Restrisiko    R' = R x (1 - w)
    Annahme: p = 0.1, S = 100  ->  R = 10
    Annahme: w = 0.8            ->  R' = 2
    w = 1.0 ist erlaubt und ergibt R' = 0 (vollstaendige
    Wirksamkeit ist eine ANNAHME, die in der Realitaet zu Beweisen
    waere - ein behauptetes w = 1 bleibt eine Behauptung).

Eingabe:  {"risiko": {"wahrscheinlichkeit": 0.1, "schadenshoehe": 100},
          "restrisiko": {"risiko": 10, "wirksamkeit": 0.8}}

## Beispiel 3: UNKNOWN-Ausbreitung (Kern-Abschnitt 6)

    {'risiko': {'wahrscheinlichkeit': null, 'schadenshoehe': 100}}
    -> {'wert': null, 'status': 'NICHT_GEPRUEFT'}

Eine fehlende Wahrscheinlichkeit macht das Risiko NICHT_GEPRUEFT -
niemals 0, niemals geraten. bilanz.nicht_geprueft zaehlt ehrlich mit;
die CLI meldet exit 1 (sichtbar, KEIN Scheitern), exit 0 nur wenn
jede Formel berechenbar ist, exit 2 bei Struktur-/Domainfehler
(fail-closed, KEIN stilles Clampen: p = 1.5 ist ein Fehler, wird
nicht heimlich auf 1 gesetzt).

## Beispiel 4: Effizienz und Vertrauen

    Effizienz = Nutzenleistung / Aufwand (0-Aufwand: NICHT_GEPRUEFT,
                 KEIN Unendlich-Ergebnis)
    Vertrauen = Evidenz x Integritaet x Kontrollierbarkeit, je [0, 1]
    Annahme: Effizienz 80/100 = 0.8; Vertrauen 0.9 x 0.5 x 0.5 = 0.225

Ein Faktor von 0.5 in einem Faktor haelt das Produkt klein: Vertrauen
wird vom schwachen Glied begrenzt (Evidenz-Pflege allein hilft nicht).

## Beispiel 5: Wo echte Messwerte herkommen (VERWEIS statt Erfindung)

- controller/impact.py: compute_impact aus echten CSV-Messreihen
  (DQI-datenqualitaet, Evidenz-Referenzen, Hash-Kette im Ledger)
- controller/legacy_coverage.py + legacy_radar.py: inventarbasierte
  Kennzahlen aus dem echten Node-Inventar
- controller/max_best_rechner.py: rechnet mit den Messwerten, sobald
  sie vorliegen; bis dahin bleibt alles, was fehlt, NICHT_GEPRUEFT

## Grenzen

Diese Beispiele binden KEINE Entscheidung und setzen KEINEN Modul-
betrieb voraus. Die Nebenbedingungen (Menschenwuerde > Sicherheit >
Rechte > Stabilitaet > Optimierung) gelten vor und ueber jedem
Ergebnis dieser Formeln und sind in keiner Zahl enthalten.
