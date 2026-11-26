# V91-LINGUA-GRAMMATIK (Stufe 3, Schritt 1: Sprachdefinition)

Status: NORM-KANDIDAT der Stufe 3 unter Subordination zu
docs/V91-LINGUA-KERN.md (#571) und
docs/V91-LINGUA-SICHERHEITS-ANHANG.md (#572). Der KERN bleibt
alleinverbindlich fuer Vokabular und Regelwerk R1-R7; dieses
Dokument VOLLSTAENDIGT die Sprachdefinition (Anhang #572,
Schritt 1) und wird durch den Referenzparser
controller/lingua_parser.py umgesetzt (Schritt 2, gleiche PR).
DEFINIERT != ANGEWENDET: Solange die Schritte 3.3 (MODELLTESTS)
und 3.4 (KOOPERATION) nicht bestanden sind, ist LINGUA im
Betrieb NICHT verpflichtend. SPRACHE SCHAFFT KEINE BEFUGNIS (R6).

Provenienz: Betreiber-Go 26.11.2026, ausdrueckliche Stufe-3-
Autorisierung fuer Schritt 1 GRAMMATIK und Schritt 2 PARSER;
3.3 MODELLTESTS und 3.4 KOOPERATION bleiben OFFEN und getrennt.
Lookup-vor-Bau 26.11.2026: 0 Treffer fuer eine GRAMMATIK-Datei
und 0 Treffer fuer lingua_parser; beide fehlten real
(NO_DUPLICATE).

## 1. Zeichensatz und Zeilenformat

- Zulaessige Zeichen: 0x20 bis 0x7E (printable ASCII) plus
  LF (U+000A) als einziger Zeilentrenner. Alles andere,
  insbesondere CR (U+000D), Tab, Umlaute, Emojis: UNGUELTIG
  (fail-closed, R7).
- Zeilenformat: SCHLUESSEL:WERT, genau EIN Schluessel je
  Zeile, GROSSGESCHRIEBEN, Muster ^[A-Z][A-Z0-9_]{0,15}$.
- Der ERSTE Doppelpunkt trennt Schluessel und Wert. Ein
  zusaetzlicher Doppelpunkt im Wert ist NUR in EVID
  (Positionssyntax ::) und in TIME (festes UTC-Muster)
  erlaubt.
- Werte sind nicht leer. Leerzeichen im Wert sind NUR in
  EVID erlaubt, und zwar je EIN optionaler Leerzeichen vor
  und nach dem Belegtrenner ::. Der Belegverweis selbst
  enthaelt keine Leerzeichen.
- EINE abschliessende Leerzeile am Nachrichtenende ist
  erlaubt; jede weitere Leerzeile macht UNGUELTIG.
- Leere Nachricht: UNGUELTIG.

## 2. Schluesselalphabet (12 Schluessel)

PFLICHTFELDER (alle vier je Nachricht):

| Schluessel | Wertemuster |
| TASK | ^[A-Z0-9][A-Z0-9._-]{0,63}$ |
| STATE | VER, UNV, DET, OBS, MEAS, REMEAS, REV, UNK, DISPUTED (Wortkern #571) |
| EVID | n/m ::beleg mit n<=m; EIN optionales Leerzeichen vor und nach :: erlaubt; ^[0-9]{1,4}/[0-9]{1,4}$ und Beleg ^[0-9A-Za-z._/-]{1,64}$ |
| NEXT | VERIFY, AUDIT, REPORT, HOLD, CLOSE, COOP |

OPTIONALE FELDER:

| GOAL | SECURITY, EFFICIENCY, UTILITY, MEASUREMENT, COOPERATION |
| ACTION | AUDIT, VERIFY, MEAS, REMEAS, REV, REPORT, COOP, REC |
| GATE | HOLD, OPEN, FAIL (Zustandsanzeige, KEINE Befugnis, R6) |

SICHERHEITSBLOCK (Anhang #572, ATOMAR: alle fuenf oder keiner):

| VERSION | Sprachversion ^[0-9]{1,3}$ (1 = diese Grammatik) |
| FROM | Absenderkennung ^[A-Z0-9][A-Z0-9._-]{0,63}$ |
| TO | Empfaengerkennung ^[A-Z0-9][A-Z0-9._-]{0,63}$ |
| TIME | Ablaufzeit UTC ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$, Kalender geprueft |
| MSGID | Nachrichten-ID ^[A-Z0-9][A-Z0-9._-]{0,63}$ |

Unbekannter Schluessel, unbekannter Wert, doppelter Schluessel
oder fehlendes Pflichtfeld: UNGUELTIG (R7). KEIN Erraten, KEIN
stiller Default, KEINE stille Reparatur: ein Empfaenger
antwortet mit UNK und Grundangabe (KERN Fehlerregel 5). EVID ist
eine Deckungsangabe (n von m gezaehlt): ANZEIGE != BELEG, die
Zaehlung ist NIEMALS ein Wahrheitsgrad (R4).

## 3. Fehlercodes (fail-closed, vollstaendig)

| E01 INPUT | Eingabe ist keine Zeichenkette |
| E02 ZEICHENSATZ | Zeichen ausserhalb 0x20-0x7E plus LF (inkl. CR) |
| E03 LEERE_NACHRICHT | keine Zeilen |
| E04 LEERZEILE | Leerzeile innerhalb der Nachricht |
| E05 KEIN_DOPPELPUNKT | Zeile ohne Trennzeichen |
| E06 SCHLUESSEL | Schluessel entspricht nicht dem Muster |
| E07 UNBEKANNTER_SCHLUESSEL | Schluessel nicht im Alphabet |
| E08 DOPPELT | Schluessel kommt zweimal vor |
| E09 WERT_LEER | Wert ist leer |
| E10 DOPPELPUNKT_IM_WERT | Doppelpunkt im Wert ausserhalb EVID-Positionssyntax und TIME-Muster |
| E11 MUSTFELD_FEHLT | TASK, STATE, EVID oder NEXT fehlt |
| E12 WERT_UNGUELTIG | Wert verletzt sein Muster oder seine Wertemenge |
| E13 EVID_BEREICH | n > m |
| E14 UNGUELTIGE_ZEIT | TIME verletzt Format oder Kalender |
| E15 SICHERHEITSBLOCK_UNVOLLSTAENDIG | Block nur teilweise vorhanden |

Jeder Fehler traegt Code, Zeilennummer und Grundangabe und hat
VORRANG vor jedem Teilresultat: Halb gueltig existiert nicht, und
eine beschaedigte, unvollstaendige, gefaelschte oder
widerspruechliche Nachricht MUSS ZUVERLAESSIG SCHEITERN
(Anhang #572: NEGATIVE TESTS SIND PFLICHT).

## 4. Umsetzung: Referenzparser (Schritt 2)

- controller/lingua_parser.py: klein, sicher, stdlib-only,
  KEIN Netz, KEIN Dateizugriff im Parserkern.
- parse() liefert ein deterministisches Ergebnis-Dict mit
  BEFUGNIS: KEINE; validate() liefert gueltig plus Ergebnis
  oder Code, Zeile, Grund, ohne Raise. Fail-closed: der
  ERSTE Fehler beendet die Pruefung.
- SIGNATUR: NICHT_IMPLEMENTIERT. Der Parser prueft STRUKTUR,
  nicht Herkunft, Identitaet oder Befugnis. Signatur- und
  Identitaetspruefung, Replay-Schutz und echte
  Berechtigungspruefung bleiben Stufe 3.3/3.4 sowie den
  existierenden Gates vorbehalten (KEINE Behauptung).
- CLI --self-check: prueft Beispiele und meldet ehrlich
  NICHT_GEPRUEFT fuer Modelltests und OFFEN fuer Kooperation.

## 5. Stufenplan (Stufe 3 nach Anhang #572)

- 3.1 GRAMMATIK: DIESES DOKUMENT.
- 3.2 PARSER: controller/lingua_parser.py (Referenz).
- 3.3 MODELLTESTS: OFFEN, eigene Tests je Modell; verschiedene
  KI-Modelle muessen dieselben Nachrichten identisch
  interpretieren; negative Tests sind Pflicht.
- 3.4 KOOPERATION: OFFEN, echte Modelluebergaben erst nach
  bestandenen Sicherheitstests.

## 6. Grenzen (ehrlich)

- SIGNATUR: NICHT_IMPLEMENTIERT; SIGNATURPRUEFUNG != PARSING.
- Modelltests: NICHT_GEPRUEFT; Kooperation: OFFEN.
- SPRACHE SCHAFFT KEINE BEFUGNIS (R6): reale Eingriffe
  bleiben je Aktion allowlist-pflichtig.
- Governance-Gate #96, Promotion-Gates #145/#146 und
  governance-gate-Workflow #551 bleiben unberuehrt und
  alleinverbindlich. DEFINIERT != ANGEWENDET.
