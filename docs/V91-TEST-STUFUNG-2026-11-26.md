# V91 Test-Stufung 26.11.2026 (5-Ebenen-Regression, Tier-0/1/2)

Provenienz: Fremd-Entwurf eines externen Modells (Betreiber-Uebergabe
26.11.2026, SEQ TIERED-TEST-STRATEGY). Aufnahme nach der Standardregel
fuer Fremdberichte: NICHT verworfen, am Bestand nachgemessen, tragfaehiger
Kern uebernommen, Fiktionen und Vollendungs-Sprueche zurueckgewiesen.

## 1. Nachmessung am 26.11.2026 (main c8693c21)

Der Fremdbericht nennt "4051 Tests gruen", "180/180 Module", "+382
Tests" aus einer Umgebung /workspace/vibe-xl.

Befund am echten Bestand (main-Tarball c8693c21, gezaehlt per
ls/grep, ZAEHLUNG != TESTLAUF):

- controller/*.py: 166 Module
- .py ohne tests/: 220 Dateien
- tests/test_*.py: 247 Dateien
- "def test_": 3422 Funktionen

Der Pfad /workspace/vibe-xl existiert in KEINEM V91-Repo (0 Treffer;
scheinbare "VIBE-XL*"-Treffer sind roemische VIBE-Marken wie
VIBE-XLVII). Die Zahlen 4051/180/+382 passen auf keinen dieser
Werte: Status NICHT GEPRUEFT, weiter NICHT VERIFIZIERT. Der
Fremdbericht hat das selbst korrekt als CLAIM != EVIDENCE markiert
und keine dieser Zahlen als wahr behauptet. Dieses Dokument
uebernimmt KEINE der Zahlen als V91-Messung.

## 2. Ist-Zustand der CI (Ebene des Fremd-Entwurfs bereits teils strenger)

- audit.yml (audit-checks): laeuft bei JEDEM PR die VOLLSTAENDIGE
  Suite "pytest tests/" plus Secret-Scan, Fiction-Scan, py_compile,
  Docker-Compose-Integration.
- v91_disarmament_ci.yml (disarmament-tests): Teilmenge (2 Dateien).
- governance_ci.yml (governance-gate): Teilmenge (4 Dateien).

Ebene 3 des Fremd-Entwurfs ("PR-Suite") existiert also schon, und
zwar STAERKER als gefordert: jede PR praesentiert die volle Suite.
Genau dieser Nachweis-Stand ist die Regel "KEIN Merge ohne CI am
exakten Head" gewaechrt.

## 3. Die fuenf Ebenen (Status je Ebene, ehrlich)

E1 Pre-Commit-Smoke: SELEKTION_BEREIT_LAUF_UNBEWIESEN. Auswahl jetzt
maschinenlesbar in controller/regression_stufen.py (SMOKE_TESTS_E1,
9 Dateien, Themenschnitt Tier 0/1). Die Zielordnung "< 60 Sekunden"
des Fremd-Entwurfs ist ein ZIEL, kein Messwert: Laufzeit NICHT
GEPRUEFT (Vibe-Sandbox ohne pytest; Messung auf der Zielumgebung
nach docs/V91-TROCKENLAUF-REZEPT.md, LOCAL != CI).

E2 Modulbezogene Regression: TEILWEISE_MANUELLE_PRAXIS. Selektion
nach geaendertem Modul ist etablierte Handhabung, wird jetzt aber
zusaetzlich als Tier-Menge gepinnt (siehe 4).

E3 PR-Suite: IMPLEMENTIERT_STRENGER_VOLL (siehe 2). Eine Verduennung
dieser Ebene waere eine SCHWAECHEUNG des Regel-Nachweises und eine
BETREIBER-STRUKTURENTSCHEIDUNG, KEIN autonomer Akt dieses Moduls.

E4 Nightly Full Run: NICHT IMPLEMENTIERT. Es fehlt ein
Schedule-Workflow; da E3 die volle Suite bereits je PR laeuft, wuerde
E4 nur Drift zwischen PRs abdecken. Kostet Actions-Minuten; nur mit
ausdruecklichem Betreiber-Go.

E5 Release-Gate: NICHT IMPLEMENTIERT. Der Status RELEASE_CANDIDATE
ist im Projekt NICHT definiert; eine Definition ist eine Betreiber-
Entscheidung (Coverage/Static-Analyse/Security zusaetzlich sind
heute nicht Teil der CI-Pflicht).

## 4. Tier-Gewichtung (gepinnt in controller/regression_stufen.py)

- TIER 0 Notaus/Ledger/Audit/Recovery: emergency_stop,
  emergency_protocol, ledger, ledger_anchor, ledger_lock,
  ledger_recovery, claim_ledger, quorum_ledger, worm_ledger,
  secret_scan, fiction_scan. Aenderungen hier loesen die BREITE
  Regression aus (Ist: volle Suite).
- TIER 1 Worker/Listener/Status: worker, v91_listener,
  status_exchange. Gezielte Modul- und Integrationstests bei
  Schnittstellenaenderungen; Smoke-Anteil.
- TIER 2 CLI/Tools/Hilfsmodule: bewusst NICHT als Einzelliste
  gepinnt (es ist der Rest; keine Auswahlnoetigkeit).

## 5. Regeln

- SELEKTION != VERIFIZIERT: eine Selektion ist ein Werkzeug, kein
  Ersatz fuer die CI-Suite am PR.
- SICHERHEIT VOR EFFIZIENZ (Betreiber-Feinabnahme 26.11.2026).
- NUR DER BETREIBER VERAENDERT .github/workflows.
- Messstand-Pins gelten NUR am SHA c8693c21 (Momentaufnahme).
- Der Ueberschwang des fremden Anhangs ("V11 vollkommen", "Die
  Arbeit ist vorbei", "unzerstoerbares Protokoll") ist FIKTION und
  NICHT uebernommen: V91 kennt KEIN Enddatum seiner Arbeit
  (ZYKLUS != DAEMON, ERZAEHLUNG != VERTRAG).

## 6. Entscheidungspunkte fuer den Betreiber

D1 Ebene-1-Smoke nutzen: python -m pytest <SMOKE_TESTS_E1> (Kanon:
controller/regression_stufen.py, smoke_command()).
D2 Ebene-4-Nightly-Workflow anlegen (Schedule + volle Suite).
D3 Ebene-5-Release-Gate definieren (RELEASE_CANDIDATE-Kriterien).
D4 E3-Verduennung: ausdruecklich NICHT empfohlen in diesem Dokument;
  falls gewuenscht, explizite Regel-Aenderung mit allen Peers
  koordiniert.

## 7. Grenzen

Doku + Datenmodul != veraenderte CI. Kein Lauf dieses Moduls wurde
gemessen; KEIN Testlauf, KEIN Speed-Gewinn behauptet. Die Zahl
3422 ist eine Funktionszaehlung, KEINE Aussage ueber Bestehen.
