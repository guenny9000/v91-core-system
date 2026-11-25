# V91 Index-Entscheidung (nach PR #521/#532)

Status: ENTSCHIEDEN und UMGESETZT (PR #532, gemergt 25.11.2026).
Dieses Dokument beantwortet die Frage aus PR #521 (Index-Verschlankung)
nachtraeglich in einer eigenen Datei, weil die urspruengliche
Entscheidung nur in PR-Beschreibung und Aenderungslog stand
(PROTOKOLL == DOKUMENT != ZUSTANDSPRUEF).

## Entscheidung

GEWAEHLT: verlustfreie Auslagerung des Aenderungslogs nach
docs/archive/V91-ARCHITEKTUR-AENDERUNGSLOG.md (append-only, Index
verweist nur). Kein Eintrag wurde geloescht: ALLE 205 Zeilen des
main-Stands nach PR #531 sind wortvermoeglich im Archiv inklusive der
Unicode-Randzeile #299 (BEWEIS: test_real_index_lint_clean lints Index
UND Archiv und verlangt > 20 Session-Eintragszeilen).

## Bewertete Alternativen

- OPTION A (25 aktuelle Eintraege + Archiv): ABGELEHNT in dieser Form.
  Das Selektionskriterium "25 neueste" haette Chronologie reflektiert,
  nicht Gewicht, und jede Grenzzahl waere willkuerlich; der Betreiber-
  Wunsch war Verschlankung OHNE Datenverlust. Umgesetzt stattdessen:
  Index enthaelt NUR noch Struktur und Verweise (6.852 Bytes statt
  > 64 kB), die CHRONIK liegt komplett im Archiv.
- OPTION B (alerte Index-/Validator-Regel): TEILWEISE UMGESETZT,
  nicht als neue Datei, sondern als echte Pruefungen:
  tests/test_index_lint.py + tests/test_index_transition_lint.py
  (13 Tests) plus controller/index_lint.py und index_transition_lint.py.
  Eine zusaetzliche "INDEX_DECISION.md"-Pflichtdatei wurde NICHT
  geschaffen (dieses Dokument hier erfuellt den Zweck, sonst
  NO_DUPLICATE_SYSTEMS).

## Ehrliche Grenzen

- ARCHIV == CHRONIK != GELTENDE REGEL; LINT != WAHRHEIT.
- Das Kriterium "keine doppelten IDs" aus der externen Checkliste
  betrifft ein_SCHEMA (index.jsonl + archive_index.jsonl), das in
  diesem Repo NIE existierte; hier sind Eintraege datierte
  Protokollzeilen. Es wird bewusst KEIN paralleles Schema erfunden
  (KEINE_FIKTIVEN_NACHWEISE).
