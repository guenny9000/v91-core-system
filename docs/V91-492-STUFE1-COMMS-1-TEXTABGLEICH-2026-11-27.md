# V91 #492 Stufe 1: Text-Abgleich V91-COMMS-1 vs V91-CONTRIBUTION-1, 27.11.2026

STATUS: GEMESSEN - DOKUMENTIERT | TEXTABGLEICH != INHALTSPRUEFUNG,
ABGLEICH != FREIGABE, CODE-KONSTANTE != DOKUMENT-ABGLEICH.

Messstand: main c6aab964681237ab1e5a38c74c8031e2cd248c3c (27.11.2026,
nach PR #613/#614). Alle Befunde stammen aus Live-Messungen mit
controller/comms_text_abgleich.py (Skript-Modus exit 0, Bericht
ABGLEICH_UNVOLLSTAENDIG leer) gegen die realen Dokumente; keine
Chat-Erinnerung. Messergebnis ist reproduzierbar: 17 Tests in
tests/test_comms_text_abgleich.py verriegeln Extraktion, Abgleich
und Negativsonden.

## Ausgangslage

Die Bestandsaufnahme #582 (Stufe 1, Verdikt TEILWEISE) hielt fest:
Code-Konstanten und Schema kodieren die COMMS-1-Kette, aber ein
vollständiger TEXT-Abgleich zwischen
docs/V91_LEARNING_BLOCK_COMMUNICATION_PROTOCOL.md und
docs/V91-CONTRIBUTION-1.md war NICHT durchgeführt. Dieser Abgleich
schließt genau diese Lücke.

## Befund 1: Evidenz-Statuskette identisch

Gemessen in allen vier Quellen, zeichenweise:

UNKNOWN -> DOCUMENTED -> IMPLEMENTED -> TESTED -> VERIFIED -> AUDITED
-> PRODUCTION

- COMMS-1-Dokument, Abschnitt 2 (verbindliche Statuskette)
- CONTRIBUTION-1-Dokument (Wiederverwendung-Abschnitt)
- controller/contribution_intake.py (EVIDENCE_STATUSES)
- schemas/contribution.schema.json (enum)

Verdikt: BELEGT (Maschinenmessung, keine Handablesung).

## Befund 2: Workflow-Kette bewusst nur im Umschlag-Dokument

RECEIVED, TRIAGED, TESTING, ACCEPTED, INTEGRATED, REJECTED, DEFERRED
ist in CONTRIBUTION-1 und in Code/Schema dokumentiert, in COMMS-1
kommt die Kette NICHT vor (Messwert: workflow_chain_in_comms = None).
Das ist kein Widerspruch: COMMS-1 regelt Evidenz-Reifestufen,
CONTRIBUTION-1 regelt den Übermittlungs-Anspruch eines Beitrags.
CONTRIBUTION-1 selbst erklärt den Workflow-Status als Anspruch, den
der Validator nicht bestätigt. Verdikt: BELEGT als dokumentierte
Trennung (ZWEI KETTEN != EIN DURCHMESSER, ANSPRUCH != STATUS).

## Befund 3: Feldlisten mit klarer Semantik-Trennung

COMMS-1 Abschnitt 4 (Agenten-Auftrag): task_id, goal, scope,
constraints, authorization, environment, input_refs,
expected_evidence, status, result, artifacts, next_action.

CONTRIBUTION-1 (Beitragsumschlag): protocol, contribution_id, origin,
goal, scope, inputs_and_provenance, proposed_change, interfaces,
tests_and_evidence, known_limits, security_privacy_notes, status,
next_action (+ optionale license-Angabe).

Überlappung: goal, scope, status, next_action. Befund: das Feld
"status" ist in COMMS-1 ein Evidenzstatus der Reife-Kette, in
CONTRIBUTION-1 ein übermittelter Workflow-Anspruch. Gleicher Name,
unterschiedliche Bedeutung. Der Umschlag-Validator prüft nur den
Workflow-Anspruch; Evidenzangaben bleiben an die COMMS-1-Kette
gebunden. Verdikt: BELEGT als Semantik-Divergenz, die im Code
korrekt getrennt behandelt wird (FORMFELD != BEDEUTUNG).

## Befund 4: Regelgegenstücke vorhanden

Sechs Kernschutzregeln haben ein messbares Gegenstück im
Umschlag-Dokument: CLAIM/Behauptung ist kein Nachweis, keine
Geheimnisse in öffentlichen Kanälen, externe Inhalte sind
nicht vertrauenswürdig, keine Autorisierung, isolierte Prüfung vor
Integration, Offline-Nutzung. Verdikt: BELEGT für diese sechs
gemessenen Gegenstücke; die übrigen COMMS-1-Regeln (Abschnitt 3)
wurden punktweise gelesen und nicht als Widerspruch befunden, aber
nicht einzeln maschinell gemessen (LESBEFUND != MESSBEFUND).

## Grenzen

- Ein Wort- und Kettenabgleich beweist keine inhaltliche Richtigkeit
  oder vollständige Regelentsprechung; er prüft nur die kodierten
  Vergleichspunkte.
- Kein Formel-Abgleich mathematischer Inhalte, kein Abgleich der
  Abschnitte 5-18 von COMMS-1 gegen CONTRIBUTION-1-Texte.
- Der Abgleich vergleicht Dokumente; er prüft keine Laufzeit.

## Ergebnis

Die Stufe-1-Lücke der Bestandsaufnahme #582 (fehlender Text-Abgleich)
ist mit dieser Messung geschlossen: BELEGT für Ketten, Feldlisten und
Regelgegenstücke. Stufe 1 von #492 geht von TEILWEISE auf
ABGLEICH_ERFOLGT; die Bewertung der übrigen Stufen bleibt
unberührt. Ein Pull Request ist ein Änderungsvorschlag, kein Beweis
für Produktionsreife.
