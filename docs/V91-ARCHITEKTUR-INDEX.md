# V91 Architektur-Index (Bindende Uebersicht, verweisend)

Zweck: EIN verbindlicher Index der Dokumente, Module und Standort-Angaben.
Dieser Index DUPLIZIERT keinen Inhalt (NO_DUPLICATE_SYSTEMS): jedes
verlinkte Dokument bleibt alleinverbindlich. Bei Abweichungen gilt die
Kollisionsregel aus docs/V91-UNIVERSAL-LEARNING-BLOCK.md: verbindliche
Dokumente haben Vorrang vor Zusammenfassungen, messbare lokale Evidenz
hat Vorrang vor beiden.

Stand: 21. November 2026, main-Stand nach PR #327/#328; VIBE-XLIX-Reparatur #284 -> #287.

## 1. Verbindliche Dokumente (Vorrang vor diesem Index)

- docs/V91-MAX-BEST-GELUEBNIS.md (PR #126-#129, #131) - Geluebnis und Arbeitsmassstab.
- docs/V91-AUDIT-KERN.md (PR #120) - Audit-Kern, CLAIM != EVIDENCE, UNKNOWN != PASS, SCRIPTED != INSTALLED.
- docs/V91-UNIVERSAL-LEARNING-BLOCK.md (PR #134) - Universeller Lernblock v1.0, wortgetreu, inkl. Kollisionsregel.
- docs/V91-MANUELLER-LERNBLOCK.md (PR #133) - manueller Lernblock (Modell-Drill ohne Hardware).
- docs/V91-EVIDENCE-EXCHANGE.md (PR #135) - Evidence-Exchange-Format Stufe B.
- docs/V91-TAGESBERICHT-STANDARD.md (PR #130) - Tagesbericht-Standard.
- docs/V91-ERKENNTNIS-UND-REVISIONSPROTOKOLL.md (neues Ergaenzungsprotokoll; Erkenntnisstatus, Nachweisfelder, Wirkungspruefung und jederzeitige Revision; DOKUMENTIERT != IMPLEMENTIERT).
- docs/V91-MAX-BEST-NETWORK-POLICY.md - Netzwerk-Grundsaetze.
- docs/AXIOM_HEADER.md - AGATHON-Header-Vorgabe fuer ALLE NEUEN controller/*.py.

## 2. Auf main implementiert und CI-geprueft (Auszug, Auszug != Vollstaendigkeit)

- Messpfad: measurement_ingest, measurement_core, measurement_pipeline, measurement_quarantine, measurement_store, measurement_monitor.
- Saatgut: seed_inventory (#116) mit dokumentierter Keimprobe und gezaehlter Evidenz, Rate muss zur Zaehlung passen (#136).
- Autarkie: autarky_metrics/autarky_report (#83 Phase 1/2) + AutarkyTrend ehrlicher Zwei-Fenster-Vergleich (#139, Phase 3): Trend nur bei beiden Fenstern MEASURED, sonst UNKNOWN.
- Mesh: mesh_frame_codec (#117) + mesh_ingest (#137): strikter M-Frame-Wire-Contract zum Messpfad. Kapazitaetsbefund aus #137: LoRa-Body-Budget 157 Bytes (222 - 1 - 64 MAC-Hex), deshalb source optional, kompakte Identifikatoren Pflicht.
- Evidenz/Integritaet: evidence_report (#135), crypto_receipts, worm_ledger, ledger_anchor, ledger_recovery (Design: docs/V91-WORM-LEDGER-DESIGN.md).
- Waechter-Registry: watcher_registry (#168, 11 Rollen, FILES_PRESENT != INSTALLIERT), structure_review (#170, Wirtschafts-/Korruptionsanalyse, 7 Direktiv-Kriterien), research_watch (#171, Forschungs-Beobachtungslog, SHA-256-Kette); 11/11 Rollen mit Bausteinen; kein Daemon, keine Laufzeit. Erste belegte Struktur-Einschaetzung als Datenfile (#172, docs/structure-reviews/).
- Agenten-Quorum: agent_quorum (#177: Orchestrierung 2-of-3, execution_permitted HART False) + quorum_ledger (#178: dauerhaft gespeicherte Ed25519-signierte Abstimmungsbelege, Hash-Kette, persistenter Replay-Floor je Agent; HMAC-Konsens bleibt getrennt, wird NICHT als gleichwertig behandelt).
- Foederation: federation_receiver, federation_sender, federation_transport, peer_directory, peer_store, peer_sync, trusted_peer_registry.
- Runtime/Notfall: worker, controller, emergency_stop (Notaus-Verkabelung #132, Issue #70 geschlossen), emergency_protocol.
- Drill ohne Hardware: scripts/v91_model_drill.py (#133), scripts/v91_dashboard.py.
- OS-Integration: v99/os/systemd/ (v91-cycle.service, v91-cycle.timer), v99/os/launchd/, v99/os/windows/ - Repository-Dateien; INSTALLATION am Standort ist Betreibersache (SCRIPTED != INSTALLED).

## 3. Standort-Hardware Vogelsbergkreis (BETREIBER-ANGABE, nicht Repo-verifiziert)

Beschreibung des Betreibers vom 18.11.2026. Ehrliche Kennzeichnung: das
Repository kann Hardware-Spezifikationen nicht pruemen. Alles in diesem
Abschnitt ist UNKNOWN im Sinne von UNKNOWN != PASS, solange keine
Messdaten ueber den Standort-Messpfad (Issue #101, Alsfeld-Runbook) vorliegen;
es handelt sich um DOCUMENTED, nicht um VERIFIED.

- Workstation: 12-Kern-CPU, 64 GB DDR5, RTX 5080 (16 GB VRAM), 2-TB-NVMe, Windows mit WSL und Docker Desktop.
- Netzwerk-Guard-Appliance: dediziertes System (32 GB RAM) zwischen Internet-Router und Workstation zur Flusskontrolle und Filterung.
- LoRa-Anbindung: geplant, ISM-Band 868 MHz; Frequenz-/Netz-Grundlagen in docs/V91-MANUELLER-LERNBLOCK-SYSTEM-NETZ-FREQUENZEN.md. Kein Funk, kein SDR, keine echte LoRa-Hardware im Repository (Issue #103 benoetigt zweite Hardware).

## 4. Ehrliche Zuordnung: Behauptete Komponenten vs. Repository-Tatbestand (18.11.2026)

Ein externer Beitrag vom 18.11.2026 (SEQ:9006/9008) nennt Komponenten,
von denen einige NICHT im Repository existieren. Recherche am main-Head
101ee651:

- v91-sentinel.service - NICHT im Repository. Vorhandene Entsprechungen als Logik: controller/anomaly.py, controller/resilience_monitors.py, scripts-basiertes v91_state_check.py. Kein Daemon-Unit im Repo.
- zero-traffic-lock.service - NICHT im Repository. Netzwerk-Grundsaetze stattdessen als Policy-Doku (docs/V91-MAX-BEST-NETWORK-POLICY.md) und Fail-Closed-Entscheidungen in controller/emergency_*.py.
- v91-mesh-daemon.service - NICHT im Repository. Vorhanden: mesh_frame_codec + mesh_ingest (Codec/Adapter, kein Transport). Daemon-/LoRa-Verkabelung bleibt Issue #103.
- integrity_shard.py - NICHT im Repository. Vorhandene Entsprechung: controller/worm_ledger.py und controller/ledger_anchor.py (WORM-Design siehe docs/V91-WORM-LEDGER-DESIGN.md).
- v91_ebpf_monitor.py - NICHT im Repository.
- v91_master_substitution_blueprint.py - NICHT im Repository.
- Der als "Master-Dokument" (SEQ:9008) angebotene Buendel-Lernblock wurde NICHT als Zweitdatei uebernommen: docs/V91-UNIVERSAL-LEARNING-BLOCK.md (#134) bleibt wortgetreu alleinverbindlich, dieser Index buendelt nur Verweise.

Fazit: Der Beitrag ist als Ideenquelle wertvoll; jede einzelne genannte
Komponente bleibt eine Behauptung, bis sie als fokussierter PR mit Tests
auf main liegt oder als Messdaten-Evidenz im Ledger belegt ist
(INSTALLED != VALIDATED, VALIDATED != INDEPENDENT).

## 5. Regel fuer diesen Index

Dieser Index wird bei jedem gemergten PR aktualisiert (die
Aenderungslog-Zeile wird seit der Archiv-Ueberfuehrung im Archiv
docs/archive/V91-ARCHITEKTUR-AENDERUNGSLOG.md angehaengt, vormals eine Zeile je
Aenderung hier), aendert selbst nie Verhalten und kann keine Zustandssprueche
(STATUS:ACTIVE, SYNCHRON, DRIFT:0/3, VALID:VERIFIED) ersetzen: solche
Attribute entstehen ausschliesslich aus gepruefter Evidenz, nicht aus Text.

## 6. Aenderungslog (archiv-verweisend)

Der vollstaendige chronologische Aenderungslog liegt verweisend in
docs/archive/V91-ARCHITEKTUR-AENDERUNGSLOG.md (append-only). Neue
Zeilen je gemergtem PR werden direkt dort angehaengt; dieser Index
dupliziert sie nicht mehr (NO_DUPLICATE_SYSTEMS). Der Bestandsschutz
gegen die leere Rekonstruktion aus #173 liegt im Integrationstest
tests/test_index_lint.py: Session-Eintragszeilen in Index PLUS Archiv
muessen zusammen > 20 sein; SKIP != PASS bleibt.
