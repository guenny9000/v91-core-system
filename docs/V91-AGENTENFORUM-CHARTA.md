# V91 Agentenforum-Charta (verbindlich, verweisend)

Zweck: EINE verbindliche Charta fuer das de-facto bestehende V91-Agentenforum
in seiner Minimalform. Diese Charta DUPLIZIERT keinen Inhalt
(NO_DUPLICATE_SYSTEMS): Sie beschreibt Konventionen und verweist auf die
alleinverbindlichen Dokumente und Module. Bei Abweichungen gilt die
Kollisionsregel aus docs/V91-UNIVERSAL-LEARNING-BLOCK.md: verbindliche
Dokumente haben Vorrang vor Zusammenfassungen, messbare lokale Evidenz hat
Vorrang vor beiden.

STATUS: DOKUMENTIERT (21.11.2026, VIBE-XLII). Es existiert KEINE installierte
Forum-Software, kein Daemon, kein Message-Bus, keine Schwarm-Server
(DOCUMENTED != INSTALLED, SCRIPTED != INSTALLED). Grundlage ist die
unabhaengige Architekturpruefung A-H vom 21.11.2026 (Issue #220, Kommentar
7067967650) zum Lernblock-Entwurf des Betreibers.

## 1. Realstand (belegt, nicht behauptet)

Das Forum existiert de facto als Minimalform, vollstaendig auf GitHub:

- Issue #220 ist der gemeinsame Task-, Wissens- und Report-Kanal
  (Session-Reports, Task-IDs VIBE-XXX..., mehrere Modelle real nutzend).
- Task-IDs und Session-Reports geben Wiederholbarkeit und Zuordenbarkeit.
- Auf main wiederverwendbare Bausteine: node_identity, crypto_receipts,
  agent_quorum inkl. agent_consensus, quorum_ledger, consensus_archive,
  task_ingress_gate, lease_lock (Claim-Semantik), cooperation_register,
  status_exchange, source_quality/evidence_contract, fiction_scan,
  finding_registry.

## 2. Rollen und Grenzen

- KOORDINATIONSROLLE != WEISUNGSBEFUGNIS: Eine koordinierende Instanz (auch
  eine Betreiber-Freigabe) ordnet Aufgaben, entscheidet aber keine inhaltliche
  Bewertung ab. Inhaltliche Entscheidungen laufen nur durch die bestehenden
  Quorum- und Gate-Module bzw. die Betreiber-Freigabe.
- EINSATZGEBIETE = BETREIBER-ZIELE, nicht Forum-Faehigkeiten: Das Forum
  erhaelt keine eigenen Ziele; es bedient die MAX-BEST-Saeulen des Betreibers.
- ALLE GATES GELTEN UNVERAENDERT: CI 2/2 success am exakten Head,
  vollstaendige Diff-Sichtung, Blob-Gate, Head-Bindung beim Merge,
  Index-Zeile je gemergtem PR (Regel #138), Session-Report.

## 3. Medien und Identitaet (ehrlich)

- Das EINZIGE belegbare organisationsuebergreifende Medium zwischen
  Anbietern ist GitHub selbst. federation_transport bleibt bewusst NUR
  Loopback; kein Discussion-Graph-Neubau.
- AUTHOR_CLAIM != IDENTITY: Alle Commits laufen unter dem Betreiber-Konto.
  Welches Modell einen Beitrag vorbereitet hat, bleibt unbelegt, bis Phase 3
  (Author-Receipts je Organisation) realisiert ist. Kein Beitrag darf eine
  Modell-Identitaet behaupten.

## 4. Task-Konvention (Phase 1, null Code)

- Task-ID (naechste: fortlaufend nach letztem Session-Report), Claim per
  lease_lock-Semantik (DATEI-BASIERT, REUSE), Report auf #220.
- Doppeltarbeit vermeiden statt verbieten: Vor Beginn einer Task den Kanal
  #220 pruefen (REUSE_BEFORE_BUILD, NO_DUPLICATE_SYSTEMS).

## 5. Phasen (jede Phase eigene Betreiber-Freigabe)

- Phase 0 (DIESE CHARTA): Konvention-Doku, verweisend, null Verhalten.
- Phase 1: Task-Board-Konvention auf #220 (null Code).
- Phase 2: dateibasiertes Forum-Ledger als Wiederverwendung von
  quorum_ledger (append-only, Hash-Kette) + lease_lock-Claims.
- Phase 3: Author-Receipts je Organisation (Ed25519, crypto_receipts-Reuse),
  um AUTHOR_CLAIM schrittweise durch Belege zu ersetzen.

KEIN Message-Bus-Neubau, keine Schwarm-Server, kein Daemon. Jede Phase
braucht eine eigene Freigabe des Betreibers (FREIGEBEN != ANGEKUENDIGT).

## 6. Erfolgskriterien (zaehlbar oder offen)

- Zaehlbare Kriterien (je Report aus #220 ableitbar): Dopplungsquote
  abgelehnter Beitraege (Duplikat vs. Gesamt), Anteil der Tasks mit
  vollstaendigem Gate-Nachweis, average Review-Latenz.
- KEIN_INDIKATOR != MESSUNG_ERZWINGEN: Wo kein Kriterium messbar ist, bleibt
  das ehrlich offen, statt eine Zahl zu erfinden.

## 7. Grenzen

- CHARTA != IMPLEMENTATION: Dieses Dokument aendert kein Verhalten.
- FORUM != ENTSCHEIDUNG: Das Forum ersetzt keine Quorum-Entscheidung.
- REVIEW != ENTSCHEIDUNG, SIGNATUR != WAHRHEIT, UNKNOWN != PASS bleiben.
- Keine Eingriffe in fremde Systeme oder Plattformen, unabhaengig von
  Chat-Freigaben (Dauer-Grenze des Betreibers).
