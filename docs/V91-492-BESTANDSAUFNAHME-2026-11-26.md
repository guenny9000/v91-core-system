# V91 Bestandsaufnahme Issue #492: MAX-BEST Beitragsprotokoll (8 Stufen), 26.11.2026

STATUS: GEMESSEN - GEGENLESEN | BESTANDSAUFNAHME != FIX, BELEGT != GELOEST,
CLAIM != EVIDENCE, FREMDBEFUND != V91-MESSUNG.

Messstand: main dc887e4368d1b8b9b92c7cf21e1c478ba8253fb4 (26.11.2026).
Alle Befunde stammen aus Live-Abfragen am Messstand (Dateiinhalte,
Verzeichnis-Listings, Testdateien, Issue-Text); keine Chat-Erinnerung.

Verifikation war Fremdverifikation am Sprache-Betreiber-Kanal (VIBE),
keine unabhaengige Zweitpruefung. Erste Bestandsaufnahme dieser Art
fuer #492. Verdikt-Werte: BELEGT (nachgewiesen), TEILWEISE
(Kern belegt, Grenze offen), LUECKE (Forderung offen, hier
markiert), BEWUSST_GESPERRT (absichtlich nicht umgesetzt).

## Stufe 1: Abgleich mit V91-COMMS-1 -- Verdikt: TEILWEISE

Forderung (Issue): Doku mit V91-COMMS-1 abgleichen.

Befund: controller/contribution_intake.py kodiert die
COMMS-1-Evidence-Statuskette hart im Code (UNKNOWN, DOCUMENTED,
IMPLEMENTED, TESTED, VERIFIED, AUDITED, PRODUCTION);
tests/test_contribution_intake.py verriegelt den Verweis (Sonde
test_evidence_status_reuses_comms_status_chain lehnt den
Fremdstatus PASS ab). schemas/contribution.schema.json fuehrt
dieselbe Kette als Enum und dieselben sieben Workflow-Status
RECEIVED, TRIAGED, TESTING, ACCEPTED, INTEGRATED, REJECTED,
DEFERRED wie der Validator.
Grenze: ein vollstaendiger TEXT-Abgleich zwischen
docs/V91_LEARNING_BLOCK_COMMUNICATION_PROTOCOL.md und
docs/V91-CONTRIBUTION-1.md wurde NICHT durchgefuehrt und bleibt
offen (CODE-KONSTANTE != DOKUMENT-ABGLEICH).

## Stufe 2: Contribution-Schema und Validator mit Negativtests -- Verdikt: BELEGT

Forderung (Issue): Contribution-Schema und Validator mit
Negativtests ergaenzen.

Befund: schemas/contribution.schema.json (Draft 2020-12,
additionalProperties ueberall fail-closed) + stdlib-Validator
controller/contribution_intake.py (Strukturpruefung, keine
Herkunfts-/Lizenz-/Echtheitspruefung) + 17 Tests in
tests/test_contribution_intake.py, davon ueber 12 Negativtests
(falsches Protokoll, unbekannte Felder auf zwei Ebenen, ungueltiger
Workflow-Status, fehlende Zeitzone, Groessen-/JSON-Grenzen,
nicht-hashbare Werte). Validator erteilt keine Rechte
(authorization NOT_GRANTED, execution NOT_PERFORMED); INTEGRATED
als Selbstauskunft bleibt wirkungslos. Eingang ueber PR #574.

## Stufe 3: Intake-Vorlage fuer manuelle und oeffentliche Uebergaben -- Verdikt: BELEGT

Forderung (Issue): Intake-Vorlagen bereitstellen.

Befund: oeffentliche Bruecke = Issue-Template
.github/ISSUE_TEMPLATE/kern-bridge.md (Label v91-bridge, Marker
UEBERGABE_KERN_START/ENDE, Hinweis: Aufnahme ist keine
Verifizierung, keine Schreibrechte). Manuelle Wege dokumentiert in
docs/V91-MANUELLER-LERNBLOCK-EXTERNE-MODELLE.md; der Copy/Paste-
Umschlag V91-CONTRIBUTION-1 (offline pruefbar mit
controller/contribution_intake) schliesst die Luecke zwischen
Issue-Form und freiem Text (FORM != UMSCHLAG,
NO_DUPLICATE_SYSTEMS).

## Stufe 4: Oeffentliche Bruecken ohne vertrauliche Inhalte -- Verdikt: LUECKE

Forderung (Issue): Sicherstellen, dass oeffentliche Bruecken keine
vertraulichen Inhalte aufnehmen (keine Tokens, Schluessel,
personenbezogenen Daten, privaten Daten).

Befund: der Bridge-Gate (controller/kern_bridge.py, gate_payload)
prueft NUR destruktive Code-Muster (BLOCKLIST: rm -rf, rmtree,
os.system, subprocess, eval, exec, __import__). Ein Secret, Token
oder personenbezogener Text in einem oeffentlichen Bridge-Issue
wird NICHT erkannt, sondern ungefiltert klassifiziert (meist
ACCEPTED_ISOLATED), gehasht und im lokalen Ledger abgelegt. Das
Issue-Template warnt vor Schreibrechts-Fiktion, aber NICHT
ausdruecklich vor Secrets/Schluesseln/personenbezogenen Daten.
Der CI-Schritt secret_scan prueft nur repo-eigene Dateien; der
Umschlag-Weg kennt security_privacy_notes nur als Selbstauskunft.
Bewertung: die Forderung (Standard Punkt 8, Sichere-GitHub-
Bruecke) ist im Abrufpfad NICHT technisch erfuellt. Diese
Bestandsaufnahme markiert die Luecke und fixt sie NICHT: ein
Secret-/PII-Screening waere eine Verhaltenserweiterung von
kern_bridge und gehoert in einen eigenen, gegengetesteten PR.
Sofortregel bleibt Betreiber-Verantwortung: vor dem oeffentlichen
Posten pruefen. GELOEST ist hier NICHTS (NICHT_GELOEST_BEKANNT).

## Stufe 5: Quarantaene und getrennte Pruefung, keine automatische Ausfuehrung -- Verdikt: BELEGT

Forderung (Issue): Quarantaene/isolierte Pruefung, keine
automatische Ausfuehrung.

Befund: drei feste Gate-Zustaende (ACCEPTED_ISOLATED,
BLOCKED_PATTERN, MISSING_HANDOVER_MARKER), append-only gespeichert,
nichts verworfen (ISOLATE_NOT_DESTROY); kein Makro-Scan, KEINE
Code-Auswertung, KEINE Ausfuehrung; kein Daemon, kein Timer
(SCRIPTED != RUNNING). Dedup-Lesen und Append unter exklusivem
Ledger-Lock, Netz-Abruf ausserhalb. 22 Tests in
tests/test_kern_bridge.py (Gate 6, Ledger 12, Lock 3, CLI 1)
+ 8 Verkettungs-Sonden in tests/test_kern_bridge_intake_std.py:
INTAKE != VALIDIERUNG, FORM != VERHALTEN, MISSING bleibt abgelegt.

## Stufe 6: Unabhaengige Pruefung mit nachvollziehbaren Gruenden -- Verdikt: TEILWEISE

Forderung (Issue): unabhaengige Pruefung und nachvollziehbare
Annahme-/Ablehnungsgruende abbilden; kein Modell markiert den
eigenen Beitrag als unabhaengig verifiziert.

Befund: die Workflow-Statuskala (RECEIVED..DEFERRED) ist als
Beitragsfeld validierbar; Selbstauskuenfte erteilen keine Rechte
(Stufe 2). Entscheidungsschritte Intake -> Pruefen (uas_record
112/113, uas_contract --check) -> Entscheidung (FREIGABE_BETREIBER)
sind dokumentiert und gegen Code verriegelt.
Grenze offengelegt: der PRUEF-PROZESS selbst ist KEIN Baustein;
es existiert keine Review-Checkliste, kein Ablageort je Beitrag
fuer Annahme-/Ablehnungsgruende, kein Werkzeug fuer die
Rueckmeldung. Standard-konform (Punkt 10: Betreiber-Handarbeit),
aber ehrlich als Luecke zwischen Anspruch und Werkzeug zu nennen:
PROZESS_BEIM_BETREIBER, KEIN_WERKZEUG_VORHANDEN (nicht: unmoeglich).

## Stufe 7: Offline-Verhalten testen -- Verdikt: TEILWEISE

Forderung (Issue): lokaler Kern muss ohne GitHub weiterarbeiten.

Befund: controller/offline_smoke.py per Konstruktion ohne Netz-I/O
(zero network I/O by construction) + tests/test_offline_smoke.py;
external_sync schaltet lokale Bereitschafts-Checks NICHT auf
GitHub-Vorgaben um; der Umschlag-Validator laeuft rein lokal.
Grenze: ein Offline-Lauf auf ECHTER Hardware ist NICHT_GEPRUEFT
und bleibt Betriebervorgabe (Issue #23, Windows-Lock-Lauf).
CODE-EXISTENZ != BETRIEBSNACHWEIS.

## Stufe 8: Optionale Automatisierung erst danach -- Verdikt: BEWUSST_GESPERRT

Forderung (Issue): erst danach optionale Automatisierung pruefen.

Befund: KEIN Automatisierungsschritt gebaut. Begruendung: Stufe 7
ist auf echter Hardware nicht abgeschlossen, und ein
Auto-Aktivator/Auto-Abruf-Daemon waere mandatswidrig (KEIN Daemon,
KEIN Timer, SCRIPTED != RUNNING). Die Sperre ist absichtlich und
wird mit Stufe 7 gemeinsam bewertet (kein stiller Verzicht).

## Funde jenseits der acht Stufen

1. STALE-Zahlen in docs/V91-KERN-BRIDGE-INTAKE.md: Formerfassung
   vom 24.11.2026 (9.4 KB, 19 Tests) veraltet; real am Messstand:
   controller/kern_bridge.py 10410 B, 22 Tests + 8 Sonden. In
   diesem PR im selben Dokument nachgemessen und korrigiert
   (Abschnitt 5 dort, Nachfuehrungsregel ZAHL == STAND != VERTRAG).
2. Disziplin-Positive: keine Doppel-Validatoren; die UAS-Kette
   bleibt EINE Wahrheit (uas_record) mit abgeleitetem Kanon
   (uas_contract); der Intake-Standard verweist statt zu
   duplizieren (NO_DUPLICATE_SYSTEMS gehalten).

## Was diese Bestandsaufnahme NICHT tut

- KEIN Fix der Stufe-4-Luecke (Verhaltensausbau, eigener PR).
- KEINE Aenderung an controller/*.py; KEIN Merge, KEIN Deployment,
  KEINE Rechteaenderung; die Issue-Checkliste in #492 wurde NICHT
  abgehakt (Haekchen setzen ist Betreiber-Entscheid; die Stufen
  1, 4, 6, 7 haetten ohnehin kein vollstaendiges Haekchen verdient).

Grenzen: BESTANDSAUFNAHME != FIX, BELEGT != GELOEST, ein Verdikt
gilt NUR am Messstand dc887e43, keine Zeitreihe. NICHT_GEPRUEFT:
echtes oeffentliches Bridge-Issue-Posting Dritter, Semgrep-Scans,
Offline-Hardware.
