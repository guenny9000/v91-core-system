# V91 Bridge-Secret-/PII-Screening: Stufe-4-Luecke geschlossen (26.11.2026)

Stand: 26.11.2026, gegengetestet am Branch
feat/v91-bridge-secret-screening-20261126 (Zahlen sind Messstand,
kein Ewigkeitsanspruch; ZAHL == STAND != VERTRAG).

STATUS: DOKUMENTIERT - GEGENGETESTET | SCREEN == MUSTER != GARANTIE.

## 1. Anlass und Messstand davor

Die Bestandsaufnahme docs/V91-492-BESTANDSAUFNAHME-2026-11-26.md
(Stufe 4) mass am main dc887e43: das Bridge-Gate prueft NUR
destruktive Code-Muster; ein Secret, Token oder personenbezogener
Text in einem oeffentlichen Bridge-Issue wurde NICHT erkannt,
sondern ungefiltert klassifiziert (meist ACCEPTED_ISOLATED),
gehasht und im lokalen Ledger abgelegt. Verdikt am damaligen
Messtand: LUECKE, NICHT_GELOEST_BEKANNT, Fix gehoert in einen
eigenen, gegengetesteten PR. Dieser PR ist genau jener Fix fuer
die Abruf-Seite; die Bestandsaufnahme bleibt als Messtand
unangetastet (BESTANDSAUFNAHME != FIX).

## 2. Verhalten nach dem Ausbau (am Code nachgemessen)

- JEDE Aufnahme laeuft vor der Ablage durch
  controller/bridge_screening.py (screen_text, fail-closed bei
  Nicht-String-Eingabe).
- Hochsignalige Secret-Formen und Zuweisungs-Muster werden per
  REUSE aus controller/secret_scan.py importiert (PR #140):
  dieselben Pattern-Objekte, KEINE zweite Liste
  (NO_DUPLICATE_SYSTEMS, gegen Objekt-Identitaet getestet).
- Neu und nur hier: personenbezogene Formen E-Mail und deutsche
  IBAN (DE + 20 Ziffern, leerstellen-tolerant). Namen,
  Adressen und freie Text-Beschreibungen werden NICHT
  erkannt (ehrliche Grenze, siehe Abschnitt 5).
  ERWEITERUNG 27.11.2026 (Telefon-Redaktion): deutsche Telefon-
  nummern werden jetzt redigiert (+49-Form und nationale 0-Form,
  7-14 Ziffern mit Leerstelle/Bindestrich/Schraegstrich als
  Trennern; kurze Alltagsfolgen wie PLZ/Uhrzeit/Datum bleiben
  unberuehrt). Bekanntes Over-Blocking: Ziffern-Anhaenge
  (Durchwahl) und z. B. ISBN mit fuehrender 0 werden mitredigiert
  (PII-SCHUTZ VOR BEQUEMLICHKEIT, Redaktion ueber Quell-Bezug
  reversibel). Modul nach Erweiterung I: 7919 B, 28 Screening-Tests.
- ERWEITERUNG II 27.11.2026 (#613, Adress-Redaktion): vollstaendige
  deutsche Postadresse EINER Zeile (Strassenname mit Suffix +
  Hausnummer + 5-stellige PLZ + Ort) wird redigiert; Teiladressen
  (nur Strasse bzw. nur PLZ+Ort) und freie Namen bleiben bewusst
  UNERKANNT (dokumentiertes Unterblocken, MUSTER != GARANTIE).
  Modul jetzt 8832 B, 30 Screening-Tests.
- Mehrzeilige PRIVATE-KEY-Bloecke werden als Ganzes redigiert
  (BEGIN-Zeile bis END-Zeile inclusive).
- Fundstellen werden im abgelegten Text durch [REDACTIERT]
  ersetzt, bevor die Zeile im Ledger landet. Der SHA-256 bleibt
  eine Hashung ueber den ROHTEXT: der Hash bezeugt den Rohstoff,
  die Ablage kann redigiert sein (ABDRUCK != ABLAGE).
- Fundmeldungen tragen NUR Art und Zeilennummer, NIEMALS einen
  Ausschnitt (auch die Meldung darf kein Geheimnis transportieren;
  gegen die Ledger-Datei getestet: Token kommt im Klartext NICHT
  mehr vor).
- Das Gate bleibt orthogonal und unberuehrt: drei feste Zustaende
  (ACCEPTED_ISOLATED, BLOCKED_PATTERN, MISSING_HANDOVER_MARKER)
  klassifizieren destruktive Muster auf dem ROHTEXT; das
  Screening ist ein zusaetzlicher, unabhaengiger Schritt
  (GATE != SCREENING, SECRET != DESTRUKTIV). Ein Kern kann also
  gleichzeitig BLOCKED_PATTERN und redigiert sein - destruktiver
  Rest bleibt abgelegt (ISOLATE_NOT_DESTROY), das Secret ist weg.
- Der Bericht von collect_kerns zaehlt screening_counts
  {CLEAN, REDACTED}; jede Ledger-Zeile traegt screening_status
  und screening_findings.

## 3. Sofortregeln bleiben unberuehrt

- Betreiber-Verantwortung vor dem Posten oeffentlicher Issues gilt
  weiter (das Screening ist eine Rueckfalle, KEINE Freigabe).
- Ablage bleibt KEINE Verifikation: AUFGENOMMEN != VERIFIZIERT.
- Das Issue-Template mahnt jetzt ausdruecklich: KEINE Secrets,
  Schluessel, Tokens, Passwoerter oder personenbezogenen Daten in
  ein oeffentliches Issue schreiben.

## 4. Messwerte des Ausbaus (am Branch nachgemessen)

- controller/bridge_screening.py: 6966 B, stdlib-only.
- controller/kern_bridge.py: 11749 B (vorher 10410 B am main
  dc887e43; Verdrahtung + Vertragsabsatz im Module-Kopf).
- tests/test_bridge_screening.py: 23 Tests (Screen-Unit 18,
  Bridge-Verkabelung 5), alle gruen im lokalen Treiber.
- Bestand gruen: tests/test_kern_bridge.py (22 Tests) und
  tests/test_kern_bridge_intake_std.py (8 Sonden) unveraendert
  gruen (Gate- und Ledger-Pins unberuehrt).
- Token-Literale in den Tests sind aus Fragmenten konstruiert,
  damit der CI-Schritt controller.secret_scan diese Datei als
  CLEAN misst (getestet: python -m controller.secret_scan --path .
  liefert status CLEAN am Branch).

## 5. Ehrliche Grenzen

- SCREEN == MUSTER != GARANTIE: erkannt werden die bekannten
  hochsignaligen Formen; die Unschaedlichkeit des Rests wird
  NICHT behauptet.
- Zuweisungs-Werte mit Platzhaltermarken (test, beispiel,
  dummy, ...), Variablen-Referenzen ($) und Pfadwerten (/)
  gelten wie im Datei-Scanner als Konfiguration, nicht als
  Secret-Literal (dokumentierte Regel, keine Raterei). Ein
  absichtlich so getarntes Geheimnis kann durchrutschen.
- Dedup bleibt Rohtext-SHA: ein Wiederholungsabruf mit
  identischem Rohtext wird als bekannt gezaehlt, nicht
  erneut abgelegt (nachgemessen).
- PII-Kreise sind bewusst klein (E-Mail, IBAN-DE); jede
  Erweiterung geht in einen eigenen PR (Verhaltensausbau ==
  neuer PR).
