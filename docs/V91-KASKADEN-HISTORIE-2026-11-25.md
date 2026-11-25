# V91 Kaskaden-Historie 23.-25.11.2026 (Historische Validierung, MAX-BEST)

Status: GEMESSENE MOMENTAUFNAHME, KEINE Vorhersagevertrag
Betreiber-Direktiv 25.11.2026 nachts: "Kaskaden-Pfade historisch
validieren" und "MacroF1 weiter verbessern wenn alles laeuft".
Dieses Dokument ist der Nachweis beider Auftraege.

## 1. Vorher-Nachher (CLAIM != EVIDENCE)

Vorher: controller/cumulative_stress.py verweigerte bewusst jede
Metrik (sein Pruefbund: die behauptete Infrastruktur mit "Macro F1
0.59" und 16-Fall-Korpus existierte im Repository NICHT, 0 Treffer).


Nachher: Es existiert eine ECHTE Ground Truth kleiner Reichweite:
die oeffentliche Actions-Historie des eigenen Repositoriums
(23.-25.11.2026), abgerufen am 25.11.2026 gegen 01:30 UTC,
abgelegt als appendfaehige Datenbasis in
docs/cascade-history/v91-ci-suiten-2026-11-23-bis-25.jsonl
(161 vollstaendige CI-Suiten aus 334 Workflow-Runs, 24 rot).
Ausgewertet durch controller/cascade_history_eval.py, verriegelt
durch tests/test_cascade_history_eval.py (15 Tests, Rechenpruefung
gegen die Basis, weicht die Basis, schlagen die Tests bewusst aus)


## 2. Messergebnis (nativ ausgewertet, keine Glattung)

- 161 Suiten, 24 davon rot; 43 Folgepaare (zeitlich aufeinander-
  folgende Suiten desselben Branchs), davon 22 mit vorheriger
  ROT-Suite und 8 mit ROT-Ziel.
- Kaskadenbefund (alle 8 ROT-Ziele folgten einer ROT-Suite,
  kein einziges ROT entstand nach GRUEN): Failure-Clustering ist
  belegt, FN=0 beim Kaskaden-Detektor.
- Gegenbefund (Heilung ueberwiegt): 14 von 22 Nachlaeufen nach
  ROT wurden GRUEN (63.6%). Kaskaden munden historisch
  ueberwiegend in Reparatur, NICHT in Aufschaukelung.


### Detektoren (a priori gesetzt, NICHT gefittet)

| Detektor | Regel | P_rot | R_rot | F1_rot | F1_gruen | MACRO F1 |
|---|---|---|---|---|---|---|
| ZEIT | gap <= 30 min | 0.190 | 1.000 | 0.320 | 0.056 | 0.188 |
| KASKADE | vorherige Suite ROT | 0.364 | 1.000 | 0.533 | 0.750 | 0.642 |
| KASKADE+ZEIT | beides | 0.364 | 1.000 | 0.533 | 0.750 | 0.642 |

MACRO F1 0.642 ist der GEMESSENE Wert der Kaskadenregel auf dieser
Basis. Er ist KEIN Vergleichswert gegen irgendwelche behauptete
0.59 (die existierte nie), und KEINE Verbesserungszusage fuer
andere Daten: n=43, EIN Repositorium, Momentaufnahme.


## 3. Kaskadenpfad-Urteil (historisch)

1. ROT clustert NACH ROT (8/8): der dominierende Kaskadenpfad ist
   die Reparatur-Schleife, nicht das Gleichzeit-Muster aus
   mehreren unabhaengigen Spannungen.
2. Der Multistanzen-Fallpraegung #529 (zwei UNGEHOERIG
   gleichzeitige Fehler: AGATHON-Pflichtzeile + Test-Bug) war der
   Ausnahme-Simultansfall, beide wurden in EINEM fixenden Zweig
   gemeinsam geheilt: Single-Process-Wirkung belegt, Chain-Wirkung
   NICHT beobachtbar auf dieser Basis.
3. Zeitaehe ist LATENT (34 von 43 Paaren < 30 min): der naive
   Stressdiskriminator ist zu preiswert, um nuetzlich zu sein
   (Macro F1 0.188).


## 4. Ehrliche Grenzen

- AUSWAHL == RAHMEN: PR-Pushes 23.-25.11.2026, zwei Workflows,
  ein Repo. Keine Aussage ueber andere Zeitraeume, andere Systeme
  oder kuenftige Laeufe (VERGANGENHEIT != VORHERSAGE).
- KEINE_SIGNIFIKANZ_BEI_KLEINEM_N: n=43 Paare, Vertrauensintervalle
  wurden bewusst NICHT gerechnet (waere Scheingenauigkeit).
- METRIK == MOMENTAUFNAHME != GUETENORM: "MacroF1 weiter
  verbessern" durch nachtraegliches Fitten waere UEBERZAEHLIG und
  wird abgelehnt; detektoren wurden als Hypothesen VOR der
  Auswertung festgelegt.
- KEIN_KASKADEN_DETEKTOR: dieses Modul bewertet CI-Suiten, keine
  Domainlasten; cumulative_stress.py bleibt unberuehrt.


## 5. Verkabelung

- controller/cascade_history_eval.py (stdlib-only, kein Netz,
  CLI exit 0/1/2)
- tests/test_cascade_history_eval.py (15 Tests, alle gegen die
  abgelegte Basis, lokal 15/15)
- docs/cascade-history/v91-ci-suiten-2026-11-23-bis-25.jsonl
  (Datenbasis, 161 Suiten)
