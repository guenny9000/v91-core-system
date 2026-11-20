# V91 Architektur-Index (Bindende Uebersicht, verweisend)

Zweck: EIN verbindlicher Index der Dokumente, Module und Standort-Angaben.
Dieser Index DUPLIZIERT keinen Inhalt (NO_DUPLICATE_SYSTEMS): jedes
verlinkte Dokument bleibt alleinverbindlich. Bei Abweichungen gilt die
Kollisionsregel aus docs/V91-UNIVERSAL-LEARNING-BLOCK.md: verbindliche
Dokumente haben Vorrang vor Zusammenfassungen, messbare lokale Evidenz
hat Vorrang vor beiden.

Stand: 19. November 2026, main-Stand nach PR #172/#173 (Reparatur), Index-Zeilen fuer #165/#168/#170/#171 nachgezogen.

## 1. Verbindliche Dokumente (Vorrang vor diesem Index)

- docs/V91-MAX-BEST-GELUEBNIS.md (PR #126-#129, #131) - Geluebnis und Arbeitsmassstab.
- docs/V91-AUDIT-KERN.md (PR #120) - Audit-Kern, CLAIM != EVIDENCE, UNKNOWN != PASS, SCRIPTED != INSTALLED.
- docs/V91-UNIVERSAL-LEARNING-BLOCK.md (PR #134) - Universeller Lernblock v1.0, wortgetreu, inkl. Kollisionsregel.
- docs/V91-MANUELLER-LERNBLOCK.md (PR #133) - manueller Lernblock (Modell-Drill ohne Hardware).
- docs/V91-EVIDENCE-EXCHANGE.md (PR #135) - Evidence-Exchange-Format Stufe B.
- docs/V91-TAGESBERICHT-STANDARD.md (PR #130) - Tagesbericht-Standard.
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

Dieser Index wird bei jedem gemergten PR aktualisiert (eine Zeile je
Aenderung), aendert selbst nie Verhalten und kann keine Zustandssprueche
(STATUS:ACTIVE, SYNCHRON, DRIFT:0/3, VALID:VERIFIED) ersetzen: solche
Attribute entstehen ausschliesslich aus gepruefter Evidenz, nicht aus Text.

## 6. Aenderungslog (eine Zeile je gemergtem PR)

- 18.11.2026 #138 Architektur-Index angelegt (verweisend, keine Zustandssprueche).
- 18.11.2026 #139 Autarkie Phase 3: AutarkyTrend (ehrlicher Zwei-Fenster-Vergleich) in autarky_metrics, Verkabelung per --trend-baseline-ledger
- 18.11.2026 #140 Secret-Scan: fail-closed CI-Schritt (controller/secret_scan.py + audit.yml).
- 19.11.2026 #141 Startup-Check: offline Selbstpruefung als Komposition (controller/startup_check.py + tests).
- 18.11.2026 #142 Wirkungs-Datensatz-Vertrag (V91-WIRK als EvidenceReport) + PRUEFBFUND ChatGPT FIELD IMPACT in docs/V91-REGIONAL-RESILIENCE-MONITOR.md.
- 18.11.2026 #143 zweite FIELD-IMPACT-Bewertung: Experimentier-Regel + erweiterter Leitsatz im Resilience-Monitor (Abschnitt 8), Zensuren abgelehnt.
- 18.11.2026 #144 Ballast-Pflichtangabe in Wirkungs-Datensaetzen (SEQ:9032-Kern) + PRUEFBFUND: Zweitregister/Code abgelehnt (0 Repo-Treffer, defekter Konstruktor, Phantomdateien, Seeding ohne Baseline).
- 19.11.2026 #165 Foederations-Direktive v1.0 als verbindliches Dokument (docs/V91-GLOBAL-FEDERATION-DIRECTIVE.md, 11 Abschnitte + Kollisionsregel + ehrlicher main-Abgleich; DOKUMENTIERT != INSTALLIERT).
- 19.11.2026 #168 Waechter-Registry (controller/watcher_registry.py, 11 Rollen, IMPLEMENTED_FILES_PRESENT vs. VISION_UNIMPLEMENTED, 13 Tests; Stand-Zeile dieses Indexes wurde versehentlich auf nur die neuen Log-Zeilen reduziert und mit PR #173-Reparatur wiederhergestellt).
- 19.11.2026 #170 Struktur-Review-Waechter (controller/structure_review.py, 7 Direktiv-Kriterien, Evidenzpflicht fail-closed, 13 Tests) + Registry-Verdrahtung.
- 19.11.2026 #171 Forschungs-Beobachtungslog (controller/research_watch.py, SHA-256-verkettetes JSONL, Evidenzpflicht, fail-closed, 12 Tests); 11/11 Rollen mit Bausteinen.
- 19.11.2026 #172 Erste belegte Struktur-Einschaetzung als Datenfile (docs/structure-reviews/de-breg-stromsteuersenkung-2027.json, Quellen genannt, 2x NICHT_GEPRUEFT ehrlich, REVIEW != ENTSCHEIDUNG).
- 19.11.2026 #173(REPARATUR) Index-Zeilen fuer #165/#168/#170/#171 nachgezogen;(Datei-Inhalt) wurde durch leere Tool-Rueckgabe unvollstaendig gespeichert, vollstaendig rekonstruiert aus dem Stand vor #173 (CHECK != INHALTSPRUEFUNG).
- 19.11.2026 #177 Provider-neutrale 2-of-3-Review-Orchestrierung (agent_quorum: Drittabstimmung nur bei NO_QUORUM, keine Aktionen, keine Persistenz).
- 19.11.2026 #178 Quorum-Ledger: persistente, Ed25519-signierte Abstimmungsbelege (quorum_ledger, Hash-Kette, Replay-Floor ueber Neustarts, fail-closed; BELEGT != VERIFIZIERT).
- 19.11.2026 #179 Erste belegte Forschungs-Beobachtungen (6 Einträge, alle mit Primaerquelle; JSONL vom echten research_watch-Modul erzeugt und verifiziert; BELEGT_EINSCHAETZUNG != VERIFIZIERT).
- 19.11.2026 #209 Lernblock Souveraenitaet/Dezentralisierung/regionale Autarkie als verbindliches Dokument (wortgetreu + main-Abgleich je Saeule; OECD-Quelle NICHT zitierfaehig ohne Adresse; kein Vollzugsmandat; DOKUMENTIERT != INSTALLIERT).
- 19.11.2026 #211 Saeule Gesundheit: erste belastbare Datenbasis als structure_review-Datensatz (hessen-gesundheitsversorgung-vogelsberg-2026.json, Quellen genannt, NEGATIVE_FINDING_PROBLEMS_BELEGT); Lernblock-Bestandszeile ehrlich aktualisiert; DATENBASIS != MESSUNG.
- 19.11.2026 #212 Hessen-Reihe R2: Struktur-Datensaetze Saeule Energie (Energiemonitoring 2025 + MaStR-PV-Zubau Vogelsberg) und Saeule Wirtschaft (WIBank-KMU/EFRE); je REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN, DATENBASIS != MESSUNG.
- 19.11.2026 #213 Hessen-Reihe R3: Struktur-Datensaetze Saeule Wasser (Hessenwasser-Bilanz 2025, Sekundaerzitat gekennzeichnet) + Saeule Digitalisierung (Gigabit-Grundbuch Ende 2025); je REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; 6/6 Saeulen des Lernblocks mit Quellenbasis, DATENBASIS != MESSUNG.
- 19.11.2026 #214 V91-Runbook Mess-Pilot Alsfeld/Vogelsberg als verbindliches Dokument (Issue #101; MESSUNG != DATASET, VB-*-Messpunkte, fail-closed JSONL-Rohpfad; NO_DUPLICATE_SYSTEMS: Rohdatenerfassung getrennt von messwerte_ingest #200; SCRIPTED != INSTALLED, kein Sensor angebunden).
- 19.11.2026 #215 Pilot F: Messmatrix Mess-Pilot Alsfeld/Vogelsberg (docs/messmatrix/pilot-f-vb-mess-pilot-alsfeld-vogelsberg-2026.json, technologie/R2, 3 Indikatoren WIRKUNG/KOSTEN/RESILIENZ + 11 Tests + Wirkungsindex 6 Piloten; MATRIZ != WIRKUNG, SCRIPTED != INSTALLED).
- 19.11.2026 #216 Mess-Pilot Rohdaten-Writer (controller/mess_pilot.py + 17 Tests; append-only JSONL mit seq+SHA-256-Kette, fsync, Pre-/Post-Check, Fail-Closed-Status OK/UNKNOWN/ERROR/DEGRADED/OFFLINE/NOT_CONFIGURED/SENSOR_MISSING/OUT_OF_RANGE; Aufnahme nur via messwerte_ingest #200 gegen Pilot-F-Messmatrix; MESSUNG != DATASET, SCRIPTED != INSTALLED).
- 19.11.2026 #217 Struktur-Review Digitaler Euro (docs/structure-reviews/eu-ezb-digitaler-euro-2026.json; 3x BELEGT mit EZB-Praemiarquellen, 4x ehrlich NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; REVIEW != ENTSCHEIDUNG, DATENBASIS != MESSUNG).
- 20.11.2026 #218 Struktur-Review Lobbyregister Bundestag (docs/structure-reviews/de-lobbyregister-bundestag-2026.json; 6.374 aktive Eintraege per 18.11.2026; 2x PROBLEM_BELEGT: Spenderdatenschutz-Zielkonflikt (ADRA) und Schutzluecken laut Parlamentwatch; Novellierung BT-Drs. 20/7346 im Gang; REVIEW != ENTSCHEIDUNG).
- 20.11.2026 #219 Struktur-Review E-Government Hessen (docs/structure-reviews/hessen-egov-flaechendeckung-2026.json; Halbzeitbilanz 02.10.2026: 5 Leistungen bis Ende 2026, Anlagengenehmigung hessenweit online, >90% Kommunen bei An-/Ummeldung; 1x PROBLEM_BELEGT Datenschutzstruktur laenderuebergreifender Onlinedienste; REVIEW != ENTSCHEIDUNG).
- 20.11.2026 #222 Struktur-Review Buerokratieabbauprogramm Bund (docs/structure-reviews/de-breg-buerokratieabbau-2026.json; BT-Drs. 21/8067: 9,8 Mrd. EUR/Jahr saldiert seit dem ersten Entlastungskabinett; 43 Vorhaben im Berichtsumfang; zweites Kabinett zusaetzlich +600 Mio. EUR/Jahr, Regierungsbilanz insgesamt ca. 10,4 Mrd. EUR/Jahr; 72 als Sekundaerquellenangabe nicht amtlich abgegrenzt; 3x BELEGT, 4x NICHT_GEPRUEFT; CLAIM != REALISIERTE WIRKUNG; DATENBASIS != MESSUNG).
- 20.11.2026 #224 Lernblock VB-Messpunkte-IDs (docs/V91-LERNBLOCK-VB-MESSPUNKTE.md; 4 IDs VB-ENERGIE-01/NETZ-01/SYS-01/UMWELT-01 aus mess_pilot.py VB_METRICS als Tabelle; Status-Wortschatz; Windows-cmd-Aufruf; Kurzlauf-Rezept 10-20 Eintraege Host SOLAR-DESKTOP-01; SCRIPTED != INSTALLED).
- 20.11.2026 #227 Struktur-Review Netzreserve + NEP Strom (docs/structure-reviews/de-bnetza-netzreserve-2026.json; BNetzA-PM 22.05.2026: 7.407 MW Netzreservebedarf Winter 2026/27, Deckung 4.742 MW DE + 2.665 MW Ausland, Winter 2028/29: 8.274 MW; NEP 2025-2037/2045 zweiter Entwurf konsultiert bis 24.08.2026, Bestaetigung offen; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; MW-Zahlen = BNetzA-BERECHNUNGSWERTE, DATENBASIS != MESSUNG).
- 20.11.2026 #229 Struktur-Review Startchancen-Programm (docs/structure-reviews/startchancen-programm-2026.json; CHANCEN-Verbund 2-Jahres-Zwischenbilanz 07.10.2026: 450 regionale Netzwerke, >800 Multiplizierende, 8 Einheiten; Struktur-Ziele erreicht != Schueler-Wirkung; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Verbund-Angaben = CLAIM, DATENBASIS != MESSUNG).
- 20.11.2026 #230 Struktur-Review Nationale Wasserstrategie (docs/structure-reviews/nationale-wasserstrategie-2026.json; BMUKN-Primaerquellen: Strategie bis 2050, 10 Themenfelder, 78 Aktionen, 38 priorisierte mit oeffentlichem Umsetzungsstand, FAQ Stand 14.07.2026; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Ministeriums-Angaben = CLAIM, DATENBASIS != MESSUNG).
- 20.11.2026 #231 Struktur-Review Foederale Modernisierungsagenda (docs/structure-reviews/foederale-modernisierungsagenda-2026.json; Fortschrittsbericht 25.06.2026: Beschluss 04.12.2025, >200 Massnahmen mit Zieldatum, Arbeitsgruppen mit Federfuehrung, kommunale Spitzenverbaende eingebunden; Grenze: Abschaffung von Verfassungsebenen ausserhalb V91-Rahmens; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Regierungs-CLAIM, DATENBASIS != MESSUNG).
- 20.11.2026 #232 Lernblock Gemeinwohl- & Ethikdienst + V91-GCS (docs/V91-LERNBLOCK-GEMEINWOHLDIENST.md; Quartalsmodell statt Einmal-Dienst, 5 Modulideen, 8 Schutzregeln, GCS-Vorschlag mit EVIDENCE_BEFORE_CLAIMS; Status IDEA_DOCUMENTED, Behauptungs-Header des Ausgangsbeitrags nicht uebernommen; LERNBLOCK != IMPLEMENTATION).
- 20.11.2026 #233 GCS-Massnahme-001 Pilot-H-Messmatrix (docs/messmatrix/pilot-h-gcs-erste-hilfe-nachbarschaft-alsfeld-2026.json, gesundheit/R1, 3 Indikatoren WIRKUNG 4 freiwillige Quartalsmodule / KOSTEN 40 Personenstunden / RESILIENZ 50 percent Wiederkehrer + 11 Tests; erste konkrete Massnahme aus Lernblock #232; keine Umsetzung erfolgt, baseline 0; MATRIZ != WIRKUNG, IDEA != IMPLEMENTATION).
- 20.11.2026 #234 Struktur-Review Ernaehrungsstrategie (docs/structure-reviews/de-bmleh-ernaehrungsstrategie-2026.json; 'Gutes Essen fuer Deutschland', Kabinettsbeschluss 17.01.2024, rund 90 Massnahmen in 11 Handlungsfeldern, Umsetzungsstand 7 in Planung / 39 in Umsetzung / 13 abgeschlossen / 27 dauerhaft laut BMLEH-Fachseite Abruf 20.11.2026; Summe 86 vs. 'rund 90' Differenz offen; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Ministeriums-CLAIM, DATENBASIS != MESSUNG).
- 20.11.2026 #235 Struktur-Review Pakt fuer den Bevoelkerungsschutz (docs/structure-reviews/de-bmi-pakt-bevoelkerungsschutz-2026.json; Saeule Frieden/Krisenfestigkeit; Eckpunkte laut BBK-Meldung 22.05.2026: zehn Mrd. EUR bis 2029 fuer Zivile Verteidigung, NINA-App-Ausbau, zentrale Sirenen-Ansteuerung bis 2027, THW resiliente Standorte, Zivilschutz im Schulunterricht, Art. 73/70 GG; ehrlich: 13 vs. 12 typisierte Fahrzeuge, Differenz offen; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Regierungs-CLAIM, DATENBASIS != MESSUNG).
- 20.11.2026 #236 Struktur-Review Deutschland als KI-Nation 2030 (docs/structure-reviews/de-bmds-ki-nation-2030-2026.json; Saeule Technologie; BMDS KI-Taskforce Ergebnisbericht 02.11.2026: Vision in 6 Dimensionen, Kennzahlen/Zielwerte, 18 ressortuebergreifende Schlueselmassnahmen, Steuerungsbedarfe; TASKFORCE-VORSCHLAG, ZIELBILD != BESCHLUSS != UMSETZUNG; 3x BELEGT, 4x NICHT_GEPRUEFT, Verdict REVIEW_REQUIRED_UNGEPRUEFTE_KRITERIEN; Planungs-CLAIM, DATENBASIS != MESSUNG).
