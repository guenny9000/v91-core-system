# V91-LINGUA-SICHERHEITS-ANHANG (Betreiber-Leitlinie 26.11.2026)

Status: ANHANG zu docs/V91-LINGUA-KERN.md (#571). KEIN zweiter
Sprachkern, kein Parser, kein Workflow. Der KERN #571 bleibt
alleinverbindlich. DOKUMENTIERT != IMPLEMENTIERT: Der Parser-Bau
bleibt OFFEN und NUR mit Betreiber-Autorisierung (Stufe 3).

Provenienz: Betreiber-Feinabnahme 26.11.2026, 00:39 Berlin, nach
Merge von #571 (alle drei CI-Workflows am exakten Merge-Commit
vom Betreiber nachgeprueft; die 13 Tests pruefen die
Dokumentationsregeln, NICHT einen Parser). Auftrag: sechs
Sicherheitsanforderungen VOR der Parser-Entwicklung verankern.

## 1. Betreiber-Ueberregel (steht ueber allem)

SICHERHEIT IST VORAUSSETZUNG.
EFFIZIENZ IST EIN OPTIMIERUNGSZIEL.
MENSCHLICHER NUTZEN IST DER ZWECK.

## 2. Epistemische Korrektur: zwei Ebenen trennen

NICHT BELEGT BEDEUTET NICHT FALSCH. Eine Aussage kann wahr sein,
obwohl uns noch kein Beweis vorliegt. Zwei Ebenen sind zu
trennen:

- WIRKLICHKEIT: Eine Aussage ist wahr oder falsch.
- ERKENNTNISSTAND: BELEGT, NICHT BELEGT, UNBEKANNT oder
  WIDERSPRUECHLICH. (Bindung: WIDERSPRUECHLICH = DISPUTED (#569).)

Ein fehlender Beleg ist ein Zustand des ERKENNTNISSTANDES, kein
Urteil ueber die Wirklichkeit. Der Denkfehler "unbelegt heisst
unwahr" ist VERBOTEN. Subordination: UNKNOWN != PASS und HALB
VERIFIZIERT IST UNVERIFIZIERT (#569/#570/#571).

## 3. Sechs Sicherheitsanforderungen (vor Parser-Entwicklung)

| Anforderung | Zweck |
| VERSIONSKENNUNG | unterschiedliche Sprachversionen erkennen |
| ABSENDERIDENTITAET | Herkunft einer Nachricht pruefen |
| EMPFAENGERKENNUNG | Nachrichten eindeutig zuordnen |
| SIGNATUR | Manipulation und gefaelschte Herkunft erkennen |
| ABLAUFZEIT + NACHRICHTEN-ID | Wiederholungsangriffe verhindern |
| BERECHTIGUNGSPRUEFUNG | Nachricht niemals mit einer Autorisierung verwechseln |

Die BERECHTIGUNGSPRUEFUNG verriegelt R6 des KERNs (#571):
SPRACHE SCHAFFT KEINE BEFUGNIS.

## 4. Zielarchitektur: fuenf Ebenen

- Ebene 1 NACHRICHTENKERN: Aufgabe, Absender, Empfaenger,
  Version, Zeit, Nachrichten-ID.
- Ebene 2 ERKENNTNIS: CLAIM, OBS, MEAS, VER, UNK, DISPUTED, REV.
- Ebene 3 ZUSAMMENARBEIT: DET, ACT, SAFE, HOLD, REC, COOP, EFF.
- Ebene 4 SICHERHEITSPRUEFUNG: Identitaet, Signatur,
  Berechtigung, Wiederholungsschutz, Vollstaendigkeit.
- Ebene 5 ERGEBNIS UND BELEGE: Handlung, Pruefergebnis,
  Wirkung, Provenienz, Revision.

Entscheidende Eigenschaft: Ein Modell kann eine Aufgabe erkennen,
eine Loesung anbieten und einen Beitrag liefern, ohne dadurch
automatisch Zugriff auf fremde Systeme zu erhalten.

## 5. Stufe 3 in vier kontrollierten Arbeitsschritten

1. GRAMMATIK: vollstaendige, eindeutige Sprachdefinition.
2. PARSER: kleiner, sicherer Referenzparser.
3. MODELLTESTS: verschiedene KI-Modelle muessen dieselben
   Nachrichten identisch interpretieren.
4. KOOPERATION: erst nach bestandenen Sicherheitstests echte
   Modelluebergaben.

NEGATIVE TESTS SIND PFLICHT: absichtlich beschaedigte,
unvollstaendige, gefaelschte und widerspruechliche Nachrichten
muessen ZUVERLAESSIG SCHEITERN. Geschwindigkeit wird erst danach
gemessen (Effizienz ist ein Optimierungsziel, keine
Voraussetzung).

## 6. Strategische Ziele (langfristig, drei Faehigkeiten)

- GEMEINSAME ERKENNTNIS: Modelle tauschen Wissen und Belege aus.
- GEMEINSAME ARBEIT: Faehigkeiten ergaenzen sich ohne
  unnoetige Doppelarbeit.
- GEMEINSAME KONTROLLE: unabhaengige Pruefung, gegenseitige
  Fehlerkennung.

KEIN EINZELNES MODELL IST DAS ZENTRUM. Auch V91 selbst darf nicht
von einem einzigen Anbieter abhaengig werden (KEINE ZENTRALE
ABHAENGIGKEIT).

## 7. Grenzen

Dieser Anhang ist kein Parser, keine Norm und keine Befugnis.
Reale Eingriffe bleiben allowlist-pflichtig je Aktion. UNBEKANNT
bleibt UNBEKANNT. DOKUMENTIERT != IMPLEMENTIERT, ENTWURF != NORM,
SCRIPTED != INSTALLED.
