# V91 Forum-Taskboard-Konvention (Phase 1, null Code)

Zweck: EINE verbindliche Konvention fuer Task-IDs, Claims und Reports des
de-facto-Agentenforums (Issue #220). Diese Konvention ist PHASE 1 der
Agentenforum-Charta (docs/V91-AGENTENFORUM-CHARTA.md) und aendert KEIN
Verhalten: sie ordnet nur bestehende Praxis (KONVENTION != IMPLEMENTATION,
DOCUMENTED != INSTALLED).

STATUS: DOKUMENTIERT (21.11.2026, VIBE-XLIII). Anlass ist ein realer
Vorfall: die Task-ID VIBE-XLII wurde parallel vergeben (#311/#312 durch
eine Session, #313 durch eine andere). DOPPELVERGABE != BEABSICHTIGT,
und genau das soll diese Konvention verhindern.

## 1. Task-ID-Vergabe (Lookup vor Minting)

- Eine Session ERZEUGT eine neue Task-ID nur nach Lookup: letzte belegte
  ID im Aenderungslog des Architektur-Index (docs/V91-ARCHITEKTUR-INDEX.md,
  Task-Klammer [VIBE-...]) und im letzten Session-Report auf #220 pruefen.
- Format bleibt VIBE-<roemische Zahl>, streng fortlaufend; keine Spruenge, keine Alias-Namen.
- Nach dem Minting sofort Claim-Kommentar auf #220 (siehe 2.); erst DANN
  Branch/PR mit der ID im Titel.

## 2. Claim (lease_lock-Semantik, dateibasiert angelehnt, null Code)

- Claim = Kommentar auf #220 mit Muster:
  "CLAIM <Task-ID> <kurzer Titel> | Ziel-PR: <nicht-noch-vorhanden> |
   Praefix der Domain (Doku/Code) | widerruflich".
- Der Claim mit der NIEDRIGSTEN Kommentar-ID gewinnt (Kommentar-IDs sind
 atomar und total geordnet; PARALLELSTART != GLEICHZEITIG SICHTBAR).
  Spaetere, ueberlappende Claims werden im Folgekommentar als zweiter
  Platz sichtbar markiert und weichen aus (Ausweichen auf naechstfreie ID).
- Rueckzug: Claimer oder Betreiber erklaert den Claim im Kommentar fuer
  beendet; erste wartende Session kann uebernehmen (Uebergabe mit
  Uebergabe-Hinweis, UEBERNAHME != NEUSTART).
- Ein Claim ist KEINE Freigabe fuer Eingriffe: alle Gates und die
  Dauer-Grenze (keine fremden Systeme) gelten unveraendert.

## 3. Report-Pflicht

- Jede beendete Task schliesst mit einem Session-Report auf #220:
  Task-ID, PR-Nummer(n), Merge-SHAs, CI-Stand am exakten Head, Blob-Gate-
  Ergebnis, ehrliche Grenzen, Task-ID-Sicht des Naechsten.
- Fuer jedes gemergte Wesentliche gilt Regel #138 (Index-Zeile) weiter.

## 4. Doppelvergabe-Verzeichnis (ehrlich, rueckwirkend)

- VIBE-XLII: parallelen vergeben an #311/#312 (Batch-Quorum-Gate,
  _FAILURE_KINDS-Cleanup) und #313 (Agentenforum-Charta Phase 0).
  Aufloesung: keine Rueckbenennung der gemergten PRs (HISTORY !=
  EDITIERBAR); Verzeichniseintrag hier + Index-Hinweis genuegt.
  Beide Reihen wurden nachtraeglich gesichtet und CI-verifiziert
  (2/2 success je PR); SICHTUNG != AUTORENSCHAFT (AUTHOR_CLAIM !=
  IDENTITY bleibt).

## 5. Grenzen

- KONVENTION != IMPLEMENTATION: es entsteht KEIN Tooling in Phase 1;
  Phase 2 kann ein dateibasiertes Claim-Ledger (quorum_ledger-Muster)
  ergaenzen, eigene Freigabe noetig.
- CLAIM != ARBEIT: ein Claim belegt Absicht, nicht Ergebnis.
- UNKNOWN != PASS: niemals behaupten, eine andere Session koenne nichts
  mehr tun; der Kanal ordnet, er verbietet nicht.