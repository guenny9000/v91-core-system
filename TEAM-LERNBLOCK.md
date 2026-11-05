# V91 TEAM-LERNBLOCK – überprüfbarer Systemstand

**Version:** 3.1  
**Stand der Dokumentation:** 2026-11-05  
**Status:** Dokumentation; einzelne Funktionen sind implementiert und durch die jeweils genannten Tests/CI-Prüfungen begrenzt belegt. Kein pauschaler Produktiv-, Dauerbetriebs- oder Autonomiestatus.

> **Grundregel:** UNKNOWN bleibt UNKNOWN. Ein Konzept ist keine Implementierung. Ein Commit ist kein Test. Ein grüner CI-Lauf belegt nur die tatsächlich ausgeführten Schritte für genau diesen Commit. Ein Hash beweist weder Urheberschaft noch Wahrheit noch WORM-Speicherung.

---

## 1. Was V91 tatsächlich enthält

### v91-core-system
Repository: https://github.com/guenny9000/v91-core-system

Laut aktueller Architektur-Dokumentation enthält das Repository unter anderem:

- `controller/observer.py`: erfasst lokale Queue-Zähler und den Parse-Zustand des Audit-Logs und schreibt einen lokalen Snapshot.
- `controller/worker.py`: verarbeitet eine begrenzte Offline-Aufgabenliste. Zulässig sind `health_snapshot`, `sha256_file` und `verify_sha256`.
- `controller/runtime_control.py`: kann auf dem Docker-Host reale Compose-Zustände und CPU-/Speicherwerte beobachten. Eine Skalierung ist eng begrenzt und benötigt ausdrückliche Opt-in-Freigaben.
- `controller/controller.py`: synthetische Demonstration. Zufallswerte sind keine Live-Telemetrie und steuern den realen Aktor nicht.
- `tests/` und `.github/workflows/audit.yml`: enthalten ausgewählte Sicherheits-/Funktionstests sowie konfigurierte CI-Prüfungen.

**Grenzen:** Keine verifizierte globale V91-Instanz, kein nachgewiesener 24/7-Betrieb und keine verifizierte Produktivbereitstellung. Anwendungs-Latenz-/Fehlertelemetrie ist nicht vollständig angeschlossen. Das lokale JSONL-Audit ist nicht automatisch WORM oder signiert. Die CI ersetzt keinen lokalen Windows- oder Docker-Host-Test.

### V91_Agathon
Repository: https://github.com/guenny9000/V91_Agathon

Die README dokumentiert lokale Audit-Bausteine:

- Einen bestehenden HashChainAuditLogger mit bestehendem API-/Dateiformat.
- Ein zusätzliches strengeres JSONL-Ledger mit UTC-Formatprüfung, Sequenz-/Hash-Prüfung, Symlink-Schutz sowie expliziten Append- und read-only Verify-Befehlen.
- Ed25519-Hilfsfunktionen für Signatur und Prüfung.
- Eine lokale Demo mit synthetischen Daten.

**Nicht implementiert laut README:** Remote-/Multi-Node-Orchestrierung, persistente Schlüsselverwaltung, unabhängiger Zeitzeuge, WORM-Speicher, Hardware-Telemetrie, Modelltraining und autonome Produktivaktionen. Platzhalter melden fehlende Funktionen ausdrücklich.

### v91-audit-ledger
Repository: https://github.com/guenny9000/v91-audit-ledger

Dieses eigenständige Repository ist laut README als primäre gepflegte Implementierung **abgelöst**. Die strengere Ledger-Implementierung wurde nach Agathon portiert. Das Repository bleibt als historische Referenz bestehen. Bestehende Ledger-Dateien dürfen nicht automatisch gemischt, migriert oder umgeschrieben werden.

### Aurelia-Prisma
Repository: https://github.com/guenny9000/Aurelia-Prisma

Dieses Repository enthält weitere Supervisor-/Orchestrator-Komponenten. Es ist nicht gleichbedeutend mit einem nachgewiesenen V91-Gesamtsystem. Vor Netzwerkfreigaben müssen Bind-Adressen, Authentisierung, Berechtigungen, Geheimnisverwaltung und Audit-Endpunkte separat geprüft werden. Die tatsächliche Erreichbarkeit eines konkreten Rechners ist aus Repository-Code allein nicht ableitbar.

---

## 2. Sicherheits- und Entscheidungsregeln

1. **REQUEST != AUTHORIZATION.** Eine Anfrage, ein Modellvorschlag oder ein Heartbeat ist keine Ausführungsfreigabe.
2. **DETECTION != AUTHORIZATION.** Erkennung darf keine eigenständige irreversible Aktion auslösen.
3. **CLAIM != EVIDENCE.** Jede Statusaussage benötigt einen konkreten, nachvollziehbaren Beleg.
4. **UNKNOWN statt erfundener Null- oder Erfolgswerte.**
5. **ISOLATE_NOT_DESTROY.** Fehlerhafte oder nicht vertrauenswürdige Eingaben isolieren; bekannte gute Daten und Wiederherstellungspunkte erhalten.
6. **Least Privilege.** Nur notwendige Rechte; keine beliebige Shell- oder Code-Ausführung aus externen Vorschlägen.
7. **Dry-Run vor realen Änderungen.** Reale Aktionen nur mit expliziter, eng begrenzter Freigabe, Vorher-/Nachher-Prüfung und Rückfallplan.
8. **Keine blinden Merges, Force-Pushes oder pauschalen Überschreibungen.**
9. **Keine Behauptung von WORM, Signaturvertrauen, Identität oder wahrer Ereigniszeit allein aufgrund einer Hash-Kette.**
10. **Keine Verschlechterung:** Bei unklarem Ergebnis stoppen, Zustand erhalten und den Befund als UNKNOWN oder CONFLICT ausweisen.

---

## 3. Statussprache

| Status | Bedeutung |
|---|---|
| UNKNOWN / NICHT GEPRÜFT | Kein ausreichender aktueller Beleg |
| DOKUMENTIERT | In einer konkreten Datei oder einem Issue beschrieben |
| IMPLEMENTIERT | Im angegebenen Commit ist der Code vorhanden |
| VERIFIZIERT | Der konkrete Test/Prüfschritt lief erfolgreich; Umgebung und Commit sind genannt |
| PRODUKTIV | Nur mit eigenständigem Betriebs-, Sicherheits- und Monitoringnachweis |
| CONFLICT | Belege oder Versionen widersprechen einander |
| ISOLATED | Betroffene Eingabe/Komponente ist vom weiteren Austausch getrennt |

Diese Statuswerte gelten nur für den jeweils benannten Gegenstand und Umfang. Ein bestandener Unit-Test macht nicht das Gesamtsystem produktiv.

---

## 4. Sichere lokale Prüfungen

Für das Core-Repository sind die konkreten Befehle und Voraussetzungen in der aktuellen README beschrieben. Typischer Testlauf aus dem Repository-Verzeichnis:

```powershell
python --version
python -m pytest tests/ -v
```

Für Agathon:

```powershell
python -m pip install -e .
python -m pytest -q
```

Für das lokale Ledger ist die read-only Prüfung ausdrücklich von einem Append getrennt:

```powershell
python -m v91.ledger --ledger .\runtime\audit.jsonl verify
```

Diese Befehle sind **Anleitungen**, keine Behauptung, dass sie auf einem bestimmten Rechner in diesem Moment ausgeführt wurden. Vor einem Ergebnisbericht sind Betriebssystem, Python-Version, exakter Commit, Befehl, Exitcode und vollständige Ausgabe festzuhalten. Keine produktiven Datenbanken oder laufenden Dienste für einen Test überschreiben.

---

## 5. Offene Arbeit – nach Risiko und Nutzen priorisiert

1. **Dokumentationskonsistenz:** Alle Lernblöcke und Startanleitungen an den aktuellen Architekturstand angleichen; alte LIVE-/BFT-/Selbstheilungs-/WORM-Behauptungen entfernen oder als unbestätigt markieren.
2. **Core-Prüfung:** Aktuelle Tests und CI für den exakten Commit dokumentieren; Windows- und Docker-Host-Prüfung getrennt nachweisen.
3. **Aurelia-Prisma-Sicherheit:** Netzwerk-Bindings und Audit-/Chat-Endpunkte mit Tests absichern; bestehende Daten und laufende Dienste nicht ungeprüft verändern.
4. **Schlüsselvorfall-Nachweis:** Provider-seitige Rotation und Prüfung historischer Geheimnisreste separat belegen. Das Entfernen eines Wertes aus der aktuellen Datei widerruft keinen Schlüssel.
5. **Ledger-Härtung:** Schlüsselverwaltung, vertrauenswürdige Zeit, externe/WORM-Aufbewahrung und Wiederherstellung separat entwerfen und prüfen; keine dieser Eigenschaften aus einer Hash-Kette ableiten.
6. **Kooperation/Peer-Protokoll:** Zuerst Schema, Zustandsmaschine, Signatur-/Replay-/Expiry-Tests und isolierte lokale Testinstanzen; kein Remote-Code, keine automatische Übernahme fremder Vorschläge.
7. **Nachhaltigkeit:** Für jede Kennzahl Quelle, Einheit, Baseline, Unsicherheit, Messzeitpunkt und unabhängige Prüfung definieren. Keine globalen Einsparungen oder Wirkungen ohne reale Messdaten behaupten.

---

## 6. Was V91 nicht eigenmächtig tun darf

V91 kann keine fremden Staaten, Unternehmen, Stromnetze, Finanzsysteme oder Infrastrukturen einseitig steuern oder abschalten. Es kann Vorschläge, Analysen, Messmethoden und überprüfbare Verbesserungen bereitstellen. Externe Maßnahmen benötigen zuständige menschliche und rechtliche Autorisierung, Verhältnismäßigkeit, Sicherheitsprüfung und einen überprüfbaren Rückfallweg.

**Ziel bleibt:** Menschenwürde und Grundversorgung schützen, Schaden vermeiden, ökologische und soziale Resilienz stärken und Verbesserungen messbar machen – ohne die Grenzen der tatsächlichen Technik oder Belege zu verschleiern.

---

## Änderungsnotiz 3.1 – 2026-11-05

- Veraltete Behauptungen wie „alle Repos LIVE“, BFT-Quarantäne-Enforcement, automatische Löschung, tägliche produktive Pipeline, globale Selbstoptimierung und „Truth approaching infinity“ entfernt.
- Tatsächliche README-/Architektur-Aussagen von nicht implementierten Funktionen getrennt.
- Standalone Audit Ledger als abgelöst gekennzeichnet und Agathon als gepflegte Portierung benannt.
- Sicherheits-, Autorisierungs- und Evidenzgrenzen explizit gemacht.
- Offene Aufgaben nach Risiko und messbarem Nutzen priorisiert.

**Bezug:** Core issue #36 – Dokumentationsbereinigung und Reality-First-Konsistenz.
