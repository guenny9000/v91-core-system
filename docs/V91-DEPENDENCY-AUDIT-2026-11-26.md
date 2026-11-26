# V91 Dependency-Audit 2026-11-26 (Issue #591)

STATUS: GEMESSEN am main-Tail bd938198 (26.11.2026, Vibe-Abendlauf).
MESSUNG_AM_BAUM != GESAMTWAHRHEIT. REPORT != DELETE. Es wurde NICHTS
aus requirements.txt entfernt; dieses Dokument ersetzt keine
Betreiber-Entscheidung.

## Messwerkzeug

NEU controller/dependency_audit.py (v91.dependency_audit.v1,
stdlib-only, kein Netz): AST-basiertes Einsammeln aller Top-Level-
Importe der .py-Dateien des Bestands, Abgleich gegen die deklarierten
Pakete aus requirements.txt und requirements-dev.txt (-r-Kette).
Je deklariertem Paket ein Verdikt:

- GENUTZT: mindestens eine Import-Fundstelle (Pfade gedeckelt auf 20).
- NICHT_GEFUNDEN_IN_PY: 0 Import-Fundstellen. NICHT_GEFUNDEN !=
  UNGENUTZT: Nutzung ausserhalb des gescannten Baums bleibt UNKNOWN.

Nicht-.py-Nennungen (README, Workflows, Doku) werden getrennt als
HINWEISE ausgewiesen. HINWEIS != NUTZUNG. Ein Workflow, der ein Paket
installiert, belegt NICHT dessen Nutzung durch den Bestand.

## Messergebnis am main-Tail bd938198

Deklarierte Runtime-Pakete (requirements.txt):

1. cryptography: GENUTZT. 20+ Import-Fundstellen (gedeckelt), u. a.
   controller/ledger_anchor.py, controller/federation_sender.py,
   controller/federation_receiver.py, controller/signed_manifest.py,
   controller/encrypted_store.py, controller/witness_client.py,
   controller/state_monotonicity.py und zugehoerige Tests.
2. numpy: NICHT_GEFUNDEN_IN_PY. 0 Import-Fundstellen im gesamten
   Bestand (controller/, tests/, scripts/, examples/, addons/, v99/).
   Hinweise: README.md erwaehnt numpy; windows-local-verify.yml
   installiert numpy im Windows-Prueflauf. INSTALLATION != NUTZUNG.
   Der Windows-Prueflauf installiert damit ein Paket, das nach
   Stand dieser Messung von keinem Bestandsmodul importiert wird.
3. redis: NICHT_GEFUNDEN_IN_PY. 0 Import-Fundstellen. Textnennungen
   nur in Struktur-Review-Daten (docs/structure-reviews/), ohne
   Codebezug.

Deklarierte Dev-Pakete (requirements-dev.txt): pytest GENUTZT (20+
Testdateien importieren pytest; gedeckelt), ruff nur als
Konfiguration (pyproject.toml; WERKZEUGCONFIG != RUNTIME-ABHAENGIG-
KEIT, von der CI nicht als Import vorausgesetzt).

## Lesart und Grenzen (UNKNOWN bleibt UNKNOWN)

- NICHT_GEFUNDEN != UNGENUTZT: virtuelle Umgebungen, Startskripte
  ausserhalb des Repos, oder Offline-Konsumenten, die numpy/redis
  transitiv erwarten, kann diese Messung NICHT ausschliessen.
- Aus requirements.txt entfernen waere REVERSIBEL, ist aber eine
  Struktur-Entscheidung ueber das Produktions-Image und die
  Windows-Prueflaeufe: BETREIBER-ENTSCHEIDUNG, hier NICHT autonom
  vollzogen (ISOLATE_NOT_DESTROY, REQUEST != AUTHORIZATION).
- Nach einem etwaigen Betreiber-Prune gilt: NACHMESSUNG PFLICHT.
  Der Befund altert mit jedem Commit (Messtand: bd938198).
- SCRIPTED != INSTALLIERT: das Modul misst, es veraendert nichts.

## Vorschlag an den Betreiber (REVERSIBEL, mit NACHMESSUNG)

1. numpy aus requirements.txt und aus windows-local-verify.yml
   entfernen ODER die Windows-Verifizierung dokumentiert beibehalten
   (falls lokale Tools ausserhalb des Repos numpy brauchen).
2. redis aus requirements.txt entfernen ODER dokumentieren, wofuer
   es vorgesehen war (aktuell keine Spur im Code).
3. Nach jedem Schritt: python3 -m controller.dependency_audit
   --path . ausfuehren und das Ergebnis im Aenderungslog festhalten.

## Verifikation

- tests/test_dependency_audit.py: 18 Tests, lokal 18/18 OK
  (unittest, self-contained, nur tempfile).
- secret_scan CLEAN, fiction_scan CLEAN, index_lint 13/13 OK.
- CI-Beweis: siehe PR und Verifikationskommentar (3/3 am exakten
  Head ist die mergebedingung, lokale Laeufe sind KEIN Ersatz).
