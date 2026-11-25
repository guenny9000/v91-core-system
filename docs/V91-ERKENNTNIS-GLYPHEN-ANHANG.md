# V91 Erkenntnis-Glyphen-Anhang

Status: ANHANG zu docs/V91-ERKENNTNIS-UND-REVISIONSPROTOKOLL.md (#569).
KEIN zweites Protokoll, keine zweite Markerschicht, kein Parser,
kein Datenformat-Zwang. Subordination: DIE TEXTKENNUNG IST
NORMATIV; jede Glyphe und jedes Emoji ist nur eine optionale
Darstellungshilfe (#569 Abschnitt 2). Glyphen/Emojis werden hier
nur als Unicode-Codepunkte angegeben (ASCII-pure Datei).

## 1. Pruefbefund zum Betreiber-Entwurf (Betreiber-Emoji-Tabelle 26.11.2026)

- Die Epistemik-Zeichen der Tabelle decken sich mit #569 (CLAIM ?,
  OBS U+25C9, MEAS U+223F, VER U+2713, IMP U+2197, REMEAS U+27F3,
  UNK U+25C7, DISPUTED !). UEBERNOMMEN als Emoji-Zuordnung.
- KORRIGIERT: Der Entwurf setzte ein Refresh-Symbol (U+1F504) an
  die Stelle von REV. Das kollidiert mit REMEAS (U+27F3,
  Kreispfeil). REV bleibt auf U+2727 (Sternchen) gepinnt,
  passend zu #569. EINE DREHUNG IST KEINE REVISION; REVISION
  BRAUCHT ANLASS, NEUEN BELEG UND PROVENIENZVERWEIS.
- ERGAENZT: Ergebnis-Farben und Kontext-Zeichen sind reine
  ANZEIGE. FARBE != BELEG, EMOJI != STATUS-QUELLE. Die
  normative Statussprache bleibt im Protokoll #569 und im Kanon
  (UNKNOWN != PASS, NICHT_GEPRUEFT, DOKUMENTIERT != IMPLEMENTIERT).
- Die historische Abgrenzung aus #569 Abschnitt 8 gilt hier
  unveraendert: historischen Zeichen und Emojis wird keine
  V91-Bedeutung zugeschrieben; MYTHOS != SPEZIFIKATION.

## 2. Tabelle A - Erkenntnismarker (Schicht 1, normativ ist der Text)

| Marker | Zeichen (CP) | Emoji-Ersatz (CP) | Bedeutung |
| CLAIM | ? (U+003F) | U+1F914 | Behauptung, unbewiesen |
| OBS | (U+25C9) | U+1F441 | beobachtet, mit Beobachter/Zeit |
| MEAS | (U+223F) | U+1F4CF | gemessen, mit Wert/Einheit/Methode |
| VER | (U+2713) | U+2705 | verifiziert im engen Rahmen |
| IMP | (U+2197) | U+1F527 | konkrete Verbesserung umgesetzt |
| REMEAS | (U+27F3) | U+1F501 | nachgemessen gegen Baseline |
| UNK | (U+25C7) | U+2753 | unbekannt, unzureichende Datenlage |
| DISPUTED | ! (U+0021) | U+26A0 | Widerspruch, Anomalie, Gegenbeleg |
| REV | (U+2727) | U+2727 | revidiert; KEIN Pfeil/Refresh, siehe 1 |

## 3. Tabelle B - Bereichszeichen (Schicht 2, neutrale Kontextangabe)

| Emoji (CP) | Bedeutung |
| U+1F333 | Gesamtsystem / lebendiges Gefuege (Yggdrasil-Bild, ERZAEHLUNG) |
| U+1F409 | Sichtbarmacher fuer Schwachstellen (Nidhoegg-Bild, DETECTION != ZERSTOERUNG, Anhang der Abendgeschichte #568) |
| U+1FAA8 | Massnahmenstein / fester Eintrag (Metafelder per #568) |
| U+26A1 / U+1F50B | Energie / Leistung / Betriebsmittel |
| U+2699 / U+1F4BB | System / Technik / Laufzeit |
| U+1F464 / U+1F91D | Verantwortlichkeit / Mensch / Wirkung |

Diese Zeichen benennen nur, WO etwas gilt. Sie erzeugen keine
Zustaende und keine Befugnisse. Ein Bereichszeichen allein ist
stets ein Hinweis ohne Beweislast.

## 4. Tabelle C - Ergebnis-Anzeige (Schicht 3, ANZEIGE != BELEG)

| Zeichen (CP) | Bedeutung |
| U+1F7E2 (gruen) / U+2714 | Nachweis erbracht im definierten Rahmen |
| U+1F7E1 (gelb) / U+23F3 | in Pruefung, offen, unvollstaendig |
| U+1F534 (rot) / U+274C | fehlgeschlagen, widerlegt, nicht bestanden |
| U+1F4DC / U+1F4CE | Beleg-/Protokollverweis ANGEZEIGT; Existenz != Inhalt |
| U+26D4 / U+1F6D1 | Stopp, blockiert, Fail-Closed |

GRUEN zeigt eine abgeschlossene Pruefung an, STIFTET sie nicht.
Wer gruen zeigt, nennt Pruefrahmen, Stand und Quelle (#569
Abschnitt 3-4). Findings-Taxonomie und Statusvokabular des Kanons
bleiben unberuehrt.

## 5. Tabelle D - Fluss- und Verknuepfungsoperatoren

| Operator | Beispiel | Bedeutung |
| U+2192 | CLAIM U+2192 MEAS | naechster Schritt, Uebergang |
| != | OBS != VER | strikte Trennung, keine Gleichsetzung |
| + | IMP + REMEAS | Kombination im selben Kontext |
| :: | MEAS ::Issue-101 | Metadaten-Bindung/Referenz |

## 6. Schwarz-Weiss- und Graustufen-Anzeige (Deckung, NICHT Wahrheitsgrad)

Zweck: farbunabhaengige Darstellung (Terminal, Druck, Schwarz-
Weiss-Modell-Umgebungen ohne Farbtreue). Graustufen zeigen
AUSSCHLIESSLICH ABDECKUNG gezaehlter Einheiten (n von m),
NIEMALS einen Wahrheitsgrad.

| Zeichen (CP) | Bedeutung |
| U+25FB leer | Einheit offen / nicht geprueft |
| U+25D0 halbfarbig | Teilschritt abgearbeitet (Prozess, keine Wahrheit) |
| U+25D4 / U+25D5 | Viertel-/Dreiviertel-Fortschritt von Teilschritten |
| U+25BE / U+25AE | gefuellt: Einheit MIT BELEG abgeschlossen (im Rahmen) |

Regeln:
1. WAHRHEIT IST BINAER PRO AUSSAGE: eine Aussage ist mit Beleg
   verifiziert oder nicht. "HALB VERIFIZIERT" IST UNVERIFIZIERT.
   Grau entsteht NUR durch Zaehlung mehrerer Einheiten.
2. MUSTER: [U+25AE U+25AE U+25FB U+25FB 2/4 VER ::Verweis] -
   2 von 4 Aussagen des Verweises verifiziert; Zaehlung und
   Belegverweis in Textform sind Pflicht.
3. 0 von m bleibt vollstaendig offen: KEIN Auffuellen, KEIN
   Rundungserfolg, KEIN 0-Ersatz (UNKNOWN != PASS gilt auch
   hier). Grau ist ANZEIGE, kein Beleg.
4. Schwarz/Weiss binaer: weiss/offen (U+25AF) weist auf UNKNOWN
   oder offene Pruefung hin, gefuellt/schwarz (U+25AE) auf
   ABGESCHLOSSEN-MIT-BELEG im genannten Rahmen; Fail-Closed
   bleibt U+26D4 aus Tabelle C.

## 7. Kettenregeln (Kontexterhalt)

1. REIHENFOLGE: Erst der Bereich (z.B. U+2699), dann Erkenntnis-
   oder Handlungsschritte (CLAIM U+2192 MEAS U+2192 VER U+2192
   IMP U+2192 REMEAS), am Ende die Ergebnis-Anzeige (U+1F7E2).
2. TRENNUNG ERZWINGEN: Abkuerzungen zwischen Markern sind
   unzulaessig: CLAIM != VER, OBS != IMP, Farbe != Beleg.
3. BELEGPFLICHT: Nach jeder Kette folgt in Textform, was genau
   geprueft oder gemessen wurde (Quelle, Wert, Zeitpunkt, Rahmen).
   Ohne Belegangabe bleibt jede Kette ein Hinweis ohne Beweislast.

Beispiel (nur Illustration, KEIN Zustandsattribut):
U+2699 CLAIM U+2192 MEAS U+2192 VER U+2192 IMP U+2192 REMEAS
U+1F7E2 ::Commit-Referenz - Aussage geprueft, gemessen,
verifiziert, verbessert und gegen Baseline nachgemessen.
REV ist keine Kette, sondern jederzeit ueberall zulaessig (#569
Abschnitt 6).

## 8. Grenzen dieses Anhangs

Emojis und Glyphen sind Darstellungshilfen fuer Menschen und
Protokolle; sie sind weder Maschinenvertrag noch zweite
Statusquelle, auch nicht in Schwarz-Weiss. Die Textkennung aus
#569 bleibt normativ. Fehlt eine Glyphe, wird sie falsch
dargestellt oder veraendert sich ihre Bedeutung, gilt allein der
Text. DOKUMENTIERT != IMPLEMENTIERT; eine technische Auswertung
dieser Tabellen benoetigte einen eigenen Entwurf mit Tests und
Autorisierung.
