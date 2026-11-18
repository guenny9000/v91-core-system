# V91 – Evidence Exchange (Stufe B des universellen Lernblocks)

Status: DOKUMENTIERT + CODE (controller/evidence_report.py, CI-geprüft) –
NICHT DEPLOYED. Dieses Format erzeugt keine Synchronisation, keinen
Transport und keinen Netzwerkbetrieb: FORMAT != SYNCHRONISATION.

## Zweck

Modelle und Menschen können Prüfberichte austauschen, ohne gemeinsame
Hardware oder einen zentralen Server: jede Instanz erzeugt und prüft
lokale JSON-Dateien; der Austausch selbst ist manuell oder über
separat autorisierte Schnittstellen.

## Format (schema_version 1)

Kanonisches JSON mit SHA-256-Prüfsumme über den sortierten Inhalt:

- `schema_version`, `report_id` (Inhalts-Fingerprint, 16 Hex),
  `checksum` (64 Hex), zeitzonen-bewusstes `created_at`
- `producer` (z. B. Modellname), `subject` (Prüfgegenstand)
- `items`: Liste aus `claim`, `status`, optional `evidence` und `note`
- `previous_checksum`: optionaler Link auf den Vorgänger-Bericht (Versionskette;
  nichts wird verdrängt oder gelöscht, ISOLATE_NOT_DESTROY)

Statusmeldungen sind die des Universalen Lernblocks v1.0 (PR #134):
BELEGT, IN ARBEIT, VORSCHLAG, NICHT GEPRÜFT, UNKNOWN (vereinfachte
Zugangsfassung von UNKNOWN / BLOCKED / REVIEW_REQUIRED, PR #120, #98).

## Fail-Closed-Regeln

- BELEGT ohne Evidenz-Referenz wird verweigert (CLAIM != EVIDENCE).
- Jede gelieferte Evidenz muss eine strukturell gültige Referenz sein
  (URL/DOI/SHA-256/Pfad/citation/ledger_id); die Prüfung ist der
  Evidenz-Vertrag v2 aus v99/filter/source_quality.py (Issue #51,
  PR #53), wiederverwendet, nicht dupliziert.
- Naive Zeitstempel, unbekannte Felder, unbekannte Statuswerte und
  leere Pflichtfelder werden abgelehnt, nie korrigiert.
- verify_report() prüft Schema, Items, Zeitstempel und Prüfsumme;
  save_report() speichert nur verifizierte Berichte.
- Manipulation (claim, status oder jedes andere Feld geändert) wird
  über die Prüfsumme erkannt.

## Nutzung (CLI)

Bericht erzeugen (Items als JSON-Liste aus claim/status/evidence):

    python controller/evidence_report.py build --producer "modell-x" \
        --subject "V91-Kern" --items-file items.json --out report.json

Bericht prüfen (beim Empfänger, egal welches Modell):

    python controller/evidence_report.py verify --file report.json

Folgeversion: --previous-checksum <checksum des Vorgänger-Berichts>.

## Ehrliche Grenzen

- VALIDATED != INDEPENDENT: eine gültige Referenz beweist Struktur,
  nicht Wahrheit; Unabhängigkeit bleibt lokal nicht prüfbar.
- Keine Signaturen in dieser Stufe; Ed25519-Receipts existieren bereits
  (controller/crypto_receipts.py, PR #57) und können später additiv
  ergänzt werden (NO_DUPLICATE_SYSTEMS).
- Keine globale Synchronisation, kein Hosting, kein Automatismus: wer
  sagt "alle Modelle synchronisieren jetzt", muss es messen und belegen.
