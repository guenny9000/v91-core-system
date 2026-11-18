# V91 – MAX BEST Network Policy (Version 1.1)

STATUS: **ENTWURF – NICHT DEPLOYED.** Es wurden keine Netzwerkregeln geändert und keine fremden Systeme kontrolliert. Dieses Dokument ist ein Governance-Standard (Sicherheit, Qualität, Nachhaltigkeit), kein radikales Kontrollmodell und keine Freigabe für Eingriffe in fremde Systeme.

Autor: Sebastian Günter (mit fachlicher Prüfung und den vier Ergänzungsblöcken Auditierbarkeit, Fehlertoleranz, Evidenz-KI, Nachhaltigkeit), 2026-11-17/18.

## Zieldefinition

- 0 unnötiges Rauschen – maximale Qualität – minimale Verschwendung.
- Grundregel: In die autorisierten V91-Netze kommt nur, was einen nachvollziehbaren Nutzen hat, die Sicherheit respektiert und die Lebensqualität verbessert. Das betrifft Daten, Software, KI-Agenten, Netzwerkverkehr, Energieverbrauch und menschliche Zusammenarbeit.
- Nicht alles Unbekannte ist schlecht. Unbekanntes wird geprüft und bis zur Klärung begrenzt, nicht automatisch vernichtet.
- Kernleitsatz: „Das eigentliche MAX BEST ist nicht möglichst viel zu verbieten. Es ist, möglichst viel Gutes zu ermöglichen und möglichst wenig Schaden, Verschwendung und Täuschung zuzulassen."

## MAX-BEST-Filtermatrix

| Kategorie | Regel |
| --- | --- |
| Lügen und Manipulation | Erkennen, Herkunft prüfen, kennzeichnen |
| Malware und Angriffe | Blockieren und isolieren |
| Spam und Datenmüll | Filtern, begrenzen |
| Verschwendung | Vermeiden und optimieren |
| Energieverbrauch | Nutzen pro Watt maximieren |
| Ressourcenverbrauch | Nur begründeten Bedarf zulassen |
| KI-Ausgaben | Fakten, Quellen und Unsicherheit prüfen |
| Datenschutz | Datenminimierung und Zugriffsschutz |
| Menschenrechte | Unantastbare Schutzgrenze |
| Neue Ideen | Prüfen, testen, gute Lösungen fördern |
| Kritik und Widerspruch | Zulassen und sachlich prüfen |

## Technische Grundlagen

- **Zero Trust** (NIST SP 800-207): Kein Gerät und kein Agent erhält automatisch Vertrauen; kein implizites Vertrauen aus Standort, Netzwerk oder Besitz.
- **Least Privilege**: Jeder Prozess erhält nur die tatsächlich benötigten Rechte.
- **Nachvollziehbarkeit** (CISA): Sicherheitsereignisse müssen ausreichend protokolliert und überprüfbar sein.

## V91-MAX-BEST-Lernblock v1.1

```
QUALITY_FIRST = TRUE
ZERO_UNNECESSARY_NOISE = TRUE
ZERO_TOLERANCE_FOR_MALWARE = TRUE
ZERO_TOLERANCE_FOR_FRAUD = TRUE
ZERO_UNAUTHORIZED_ACCESS = TRUE
TRUTH_REQUIRES_EVIDENCE = TRUE
AI_CONFIDENCE_DISCLOSED = TRUE
UNVERIFIED_CLAIMS_MARKED = TRUE
UNKNOWN_IS_NOT_FALSE = TRUE
UNKNOWN_IS_NOT_PASS = TRUE
HUMAN_RIGHTS = PROTECTED
PRIVACY = PROTECTED
CRITICISM = ALLOWED
TRANSPARENCY = REQUIRED
LEAST_PRIVILEGE = REQUIRED
ZERO_TRUST = REQUIRED
RESOURCE_WASTE = MINIMIZE
ENERGY_EFFICIENCY = MAXIMIZE
LONG_TERM_SUSTAINABILITY = PRIORITY
RECOVERY = PRIORITY
FAIL_SAFE_DEFAULT = TRUE
ROLLBACK_AVAILABLE = TRUE
ISOLATE_NOT_DESTROY = TRUE
ALL_SECURITY_DECISIONS = LOGGED
CHANGES_REQUIRE_TRACEABILITY = TRUE
NO_UNAUTHORIZED_GLOBAL_CONTROL
CONTINUOUS_VERIFICATION = TRUE
```

## Mapping auf bestehende Module (NO_DUPLICATE_SYSTEMS)

Die Policy beschreibt Verbindlichkeit; technische Umsetzungen existieren bereits und werden wiederverwendet, nicht dupliziert:

| Policy-Regel | Bestehende Umsetzung im Repo |
| --- | --- |
| ZERO_TRUST / ZERO_UNAUTHORIZED_ACCESS | Bearer-Auth (fail-closed, V91_API_BEARER_TOKEN), signierte Capability-Manifeste (Ed25519, Widerrufslisten, Frische-Fenster) |
| LEAST_PRIVILEGE | v99 module registry (Doppelregistrierung + Rechteausweitung verweigert) |
| ALL_SECURITY_DECISIONS = LOGGED | Governance-Gate (HMAC-verkettetes Entscheidungs-Ledger), Rotation-Witness-Log |
| ISOLATE_NOT_DESTROY | Measurement-Quarantäne (Rohdaten-Erhalt, RESOLUTION als neuer Eintrag), Peer-/Encrypted-Store (fail-closed, nichts wird gelöscht) |
| ROLLBACK_AVAILABLE / FAIL_SAFE_DEFAULT | Ragnarök-Ledger (Rollback-Verweigerung bei intakter Kette), Recovery/Backup (SHA-256-verifiziert, no silent overwrite) |
| TRUTH_REQUIRES_EVIDENCE / UNKNOWN_IS_NOT_PASS | Evidenz-Vertrag v2 (source_quality), Statusaggregate (UNKNOWN nie HEALTHY), Reality-First-Header |
| AI_CONFIDENCE_DISCLOSED / UNVERIFIED_CLAIMS_MARKED | evidence_supplied / evidence_independent-Felder (UNKNOWN_NOT_VERIFIABLE_LOCALLY), UNVERIFIED-Claim-Kennzeichnung in Doku |
| RECOVERY / REPAIR_BEFORE_REPLACE | Repair & Modularity Charter, Backup/Restore-Verifikation |

## Ehrliche Grenzen

- Diese Policy ist nicht implementiert als Enforcement-Engine; sie ist der verbindliche Maßstab für kommende Module (DETECTION != AUTHORIZATION, DOCUMENTED != IMPLEMENTED).
- Keine Regel hier autorisiert Eingriffe in fremde Systeme, Plattformen oder Infrastrukturen (NO_UNAUTHORIZED_GLOBAL_CONTROL; Chat-Freigabe ersetzt keine Berechtigung Dritter).
- Netzwerkweite Filterung (Malware, Spam) braucht echte Infrastruktur, die nicht existiert; lokale, advisorische Filter existieren (SourceTrustRegistry, ContentFilter).
