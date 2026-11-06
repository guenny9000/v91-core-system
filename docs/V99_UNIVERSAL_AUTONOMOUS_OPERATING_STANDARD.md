# V99 – Universal Autonomous Operating Standard (ENTWURF, Phase 1)

Status: ENTWURF, umgesetzt als Phase 1 (Modulstandard, Registry, Agent-Kern,
Schluesselrotations-Vertrag, Regressionstests). Kein laufender Betrieb,
keine Scheduler-, Netzwerk- oder Persistenzfunktionen in Phase 1.

## Ziel

Alle Module (V91 Core, Agathon, Aurelia Prisma, externe Plattformen) harmonieren
in einem gemeinsamen Sicherheitsrahmen statt gegeneinander zu arbeiten.
Plattformunabhaengig (Windows, Linux, macOS, Container), anbieterunabhaengig.

## Verbindliche Grundregeln

1. HUMAN_LIFE_FIRST – Menschen schuetzen, keine Toetung oder Verletzung.
2. PLATFORM_INDEPENDENT – Keine unnoetige Herstellerbindung.
3. MODEL_INDEPENDENT – Unterschiedliche KI-Modelle arbeiten zusammen, keines kontrolliert die anderen automatisch.
4. NO_DUPLICATE_SYSTEMS – Vorhandene Funktionen wiederverwenden (z. B. existierende Bearer-Auth, bestehende Ledgers).
5. AUTOMATE_ROUTINE – Sichere Routinepruefungen automatisieren.
6. VERIFY_BEFORE_EXECUTION – Jede Aenderung vor Ausfuehrung pruefen.
7. PRESERVE_EXISTING_DATA – Bestehende Daten und APIs erhalten.
8. RECOVERY_BEFORE_OPTIMIZATION – Wiederherstellbarkeit zuerst.
9. UNKNOWN_IS_NOT_SUCCESS – Unbekannte Ergebnisse sind nie Erfolg; UNKNOWN ist nie HEALTHY.
10. LEAST_PRIVILEGE – Module erhalten nur noetige Rechte; Rechteausweitung durch Module selbst wird verweigert.
11. AUDIT_EVERY_CHANGE – Aenderungen nachvollziehbar dokumentieren.
12. NO_UNCONTROLLED_DELETION – Keine irreversible Loeschung ohne gesonderte Berechtigung und gepruefte Sicherung.
13. CONTINUOUS_IMPROPMENT – Regelmaessig pruefen, lernen, verbessern.
14. NO_FALSE_PRODUCTION_CLAIMS – Tests sind keine Produktionsnachweise.

## Autonomiestufen

| Stufe | Funktion | Verhalten |
|---|---|---|
| 0 | Beobachten | Status erfassen |
| 1 | Pruefen | Tests, Diagnosen, Sicherheitskontrollen |
| 2 | Vorbereiten | Reparatur/Updates im Dry-Run |
| 3 | Kontrolliert ausfuehren | Reversible, genehmigte Aenderungen |
| 4 | Autonomer Routinebetrieb | Vorab erlaubte, begrenzte Massnahmen |

Erkennen, Pruefen, Freigeben und Ausfuehren sind getrennte Vorgaenge.
Ein erkannter Fehler ist keine Berechtigung zur Aenderung.

## Phase-1-Umfang in diesem PR

- v99/core/status.py: einheitliche Statuswerte, Aggregation (UNKNOWN schlaegt HEALTHY).
- v99/core/module_standard.py: module.json-Standard, fail-closed-Validierung.
- v99/core/registry.py: Modul-Register, Doppelregistrierung und Rechteausweitung verweigert.
- v99/core/agent.py: Inspektions-/Vorschlags-/Ausfuehrungskern mit PolicyEngine.
- v99/security/key_rotation.py: Provider-Adapter-Vertrag; alter Schluessel bleibt bei jedem Fehlschlag aktiv.
- v99/config/module.example.json: Beispiel-Modulbeschreibung.
- tests/test_v99_phase1.py: Regressionstests (nur stdlib).

## Korrekturen gegenueber dem Chatab-Entwurf (dokumentiert)

- _init_ -> __init__ (Tippfehler).
- Inspektionsfehler und Identitaetsabweichungen erzeugen UNKNOWN statt Verwirrung.
- key_rotation: Widerruf des alten Schluessels nur nach erfolgreichem activate(); bei Aktivierungsfehler bleibt der alte Schluessel aktiv (der Entwurf beschrieb dies als Forderung, der Beispielcode setzte es nicht um).
- Keine zweite Authentisierung (NO_DUPLICATE_SYSTEMS): bestehende Bearer-Auth (V91_API_BEARER_TOKEN) und bestehende Ledgers werden nicht dupliziert.

## Noch nicht implementiert (ehrlich)

Scheduler, persistente Speicherung, Signaturpruefung, echte Provider-Adapter,
Update-Manager, Recovery-Adapter, Plattformdienste (systemd/launchd/Taskplaner).
Phasen 2-8 folgen; jede Phase mit eigener CI-gepruefter Freigabe.

## Abnahmekriterien (Auszug)

- Doppelte Registrierung wird verhindert (Test).
- Rechteausweitung durch Module wird verweigert (Test).
- UNKNOWN wird nie als HEALTHY aggregiert (Test).
- Nicht reversible oder freigabepflichtige Aktionen werden nicht ausgefuehrt (Test).
- Schluesselrotation ohne Freigabe ist wirkungslos, bei Fehlschlag bleibt der alte Schluessel aktiv (Tests).
