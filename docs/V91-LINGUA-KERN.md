# V91-LINGUA-KERN (Stufe 2: gemeinsame Protokollsprache, ENTWURF)

Status: ENTWURF eines Kernvokabulars und Nachrichtenformats.
DOKUMENTIERT != IMPLEMENTIERT: Es gibt KEINEN Parser auf main.
Nachtrag 26.11.2026 (Betreiber-Go Stufe 3.1/3.2): GRAMMATIK und
Referenzparser sind ergaenzt, siehe docs/V91-LINGUA-GRAMMATIK.md
und controller/lingua_parser.py; dieser KERN bleibt Wortkern der
Stufe 2 im ENTWURF-Status.
KEIN zweites Marker-System [NO_DUPLICATE_SYSTEMS]: Der Wortkern
SUBORDINIERT sich dem Erkenntnis- und Revisionsprotokoll #569 und
der Anzeige-Schicht #570; er ergaenzt nur Ablauf-Schluessel, die
#569 nicht abdeckt. SPRACHE ist KEINE BEFUGNIS.

Provenienz: Betreiber-Stufenplan 25./26.11.2026 (Stufe 1
Erkenntnis- und Belegsystem, Stufe 2 gemeinsame V91-Protokollsprache,
Stufe 3 direkte Modell-Kooperation mit gegenseitiger Pruefung).
Betreiber-Vorgabe: SICHERHEIT HAT VORRANG VOR EFFIZIENZ.
Lookup-vor-Bau: kein Treffer fuer "LINGUA" oder "Protokollsprache"
im Bestand; Stufe 2 fehlt real.

## 1. Zweck und Niveau

- LINGUA ist eine BETRIEBSSPRACHE fuer Modell-zu-Modell-Uebergaben
  (Handoffs, Audit-Zeilen, Gate-Meldungen), nicht fuer Menschen.
- Deutsch bleibt die Erklaerungsschicht fuer den Betreiber und alle
  menschlichen Rueckfragen. LINGUA ersetzt keine menschliche
  Kommunikation.
- Jedes Modell muss dieselbe Nachricht GLEICH verstehen. Ziel ist
  Eindeutigkeit und Vollstaendigkeit, nicht Wohlklang.
- ENTWURF != NORM: Ohne Stufe 3 ist LINGUA ein Wortkern-ENTWURF.
  Niemand ist heute verpflichtet, LINGUA zu sprechen.

## 2. Fuenf Eigenschaften (Betreiber-Vorgabe, verbindlich)

1. SICHERHEIT: Keine unberechtigten Aktionen; SPRACHE != BEFUGNIS.
2. EFFIZIENZ: Wenige Zeichen und Rechenschritte, aber niemals
   durch Weglassen von Informationen; Sicherheit geht vor.
3. VOLLSTAENDIGKEIT: Keine verlorenen Informationen; ein
   unbekannter Zustand wird als UNK uebertragen, niemals durch
   Interpretation ersetzt.
4. KOMPATIBILITAET: Unterschiedliche Modelle verstehen dieselbe
   Nachricht gleich; ASCII-pure, farbunabhaengig (#570).
5. ERWEITERBARKEIT: Neue Schluessel nur als Anhang mit Tests;
   alte Regeln werden dabei nicht zerstoert (append-only).

## 3. Hartes Regelwerk

- R1 WAHRHEIT IST BINAER PRO AUSSAGE: BELEGT oder NICHT BELEGT.
  HALB VERIFIZIERT IST UNVERIFIZIERT (#570).
- R2 UNBEKANNT MUSS EXPLIZIT SEIN: Fehlende Information wird als
  UNK uebertragen; KEIN Rueckschluss, KEIN stiller Default,
  KEINE Ersetzung durch Interpretation.
- R3 KEIN INFORMATIONSVERLUST FUR KUERZE: Verdichten ist erlaubt,
  Weglassen nicht; gekuerzt wird nur Redundanz, niemals
  Pflichtfelder oder Belegverweise.
- R4 ANZEIGE != BELEG: DECKUNG IST NUR ZAEHLUNG; n von m gezaehlte
  Einheiten ist eine Deckungsangabe, NIEMALS Wahrheitsgrad (#570).
- R5 WIEDERHOLUNG IST KEINE REVISION: REV ist inhaltliche
  Ueberarbeitung, REMEAS ist Nachmessung (#569/#570 unberuehrt).
- R6 SPRACHE SCHAFFT KEINE BEFUGNIS: Eine LINGUA-Nachricht
  autorisiert nichts; reale Eingriffe bleiben je Aktion
  allowlist-pflichtig (Betreiber-Sicherheitsregeln).
- R7 FAIL-CLOSED: Unbekannter Schluessel, unbekannter Wert oder
  fehlendes Pflichtfeld macht die Nachricht UNGUELTIG; kein
  Erraten, kein stiller Default.

## 4. Wortkern (Subordination zu #569, KEIN zweiter Kanon)

| Schluessel | Bedeutung | Bindung |
| VER | Beleg vorhanden | = Marker VER (#569) |
| UNV | Aussage ohne Beleg | CLAIM-Niveau (#569) |
| DET | Erkenntnis entdeckt | neu, ehrlich unbelegt |
| OBS | beobachtet (Beobachter/Zeit) | = Marker OBS (#569) |
| MEAS | gemessen (Wert/Einheit/Methode) | = Marker MEAS (#569) |
| REMEAS | nachgemessen (Baseline) | = Marker REMEAS (#569) |
| REV | inhaltlich ueberarbeitet | = Marker REV (#569) |
| UNK | unbekannt | = Marker UNK (#569) |
| DISPUTED | Widerspruch/Anomalie | = Marker DISPUTED (#569) |
| EFF | Wirkung nachgewiesen | sonst NICHT_GEPRUEFT |
| ACT | Handlung ausgefuehrt | Ablauf-Schluessel |
| SAFE | Sicherheitspruefung angestossen | Ablauf-Schluessel |
| HOLD | angehalten (Gate-Zustand) | Ablauf-Schluessel |
| REC | Wiederherstellung | Ablauf-Schluessel |
| COOP | Kooperation angeboten | Ablauf-Schluessel |

EFF ohne Messbasis bleibt STATE UNV / NICHT_GEPRUEFT; Wirkung
behaupten ohne Nachweis ist REGELVERSTOSS (R1/R2).

## 5. Nachrichtenformat (Grammatik-ENTWURF, noch nicht normativ)

- Zeilenformat: SCHLUESSEL:WERT; je Zeile GENAU EIN Schluessel;
  Schluessel GROSSGESCHRIEBEN; ASCII-pure.
- Pflichtfelder je Nachricht: TASK, STATE, EVID, NEXT.
- EVID ist eine Deckungsangabe n von m mit Belegverweis (::);
  Zaehlung und Verweis in Textform sind Pflicht (#570).
- Beispiel (Betreiber-Vorlage, Illustration, KEINE Norm):

  TASK:042
  GOAL:SECURITY
  STATE:UNV
  EVID:0/4 ::offen
  ACTION:AUDIT
  GATE:HOLD
  NEXT:VERIFY

## 6. Fehlerregeln (fail-closed)

1. Fehlendes Pflichtfeld => UNGUELTIG.
2. Unbekannter Schluessel oder unbekannter Wert => UNGUELTIG.
3. Doppelter Schluessel in einer Nachricht => UNGUELTIG.
4. GATE-Ergebnis ohne EVID-Beleg => UNGUELTIG (Behauptung != Beleg).
5. Ein Empfaenger repariert nicht stumm: Er antwortet mit UNK und
   Grundangabe; keine Ergaenzung aus Interpretation (R2).

## 7. Stufenplan

- Stufe 1 ERLEDIGT: Erkenntnis- und Revisionsprotokoll #569;
  Glyphen- und Deckungs-Anzeige #570.
- Stufe 2 DIESES DOKUMENT: Wortkern und Format-ENTWURF.
- Stufe 3 TEILWEISE UMGESETZT (26.11.2026, Betreiber-Go): 3.1
  GRAMMATIK und 3.2 Referenzparser sind ergaenzt (eigener PR,
  CI 3/3 am exakten Head); OFFEN bleiben 3.3 gemeinsame Tests je
  Modell, 3.4 Einsatz in Handoffs; weitere Schritte nur mit
  Betreiber-Autorisierung und eigenem PR (Abendstandard).

## 8. Grenzen

LINGUA ist ein Sprachkern-ENTWURF, keine Laufzeitsteuerung und
kein Gate-Ersatz; Governance-Gate #96, Promotion-Gates #145/#146
und governance-gate-Workflow #551 bleiben alleinverbindlich.
Unbekannt bleibt unbekannt; eine Nachricht stiftet keinen Zustand
und keine Befugnis. DOKUMENTIERT != IMPLEMENTIERT.
