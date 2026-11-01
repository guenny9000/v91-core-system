# V91 Agenten-Verbindung: Handshake, Gossip und autonome Zusammenarbeit

**Status: DOCUMENTED / Spezifikation zur Prüfung.** Dieses Dokument beschreibt eine Integrationsarchitektur. Es behauptet nicht, dass Verbindungen bereits implementiert, lokal erreichbar oder produktiv sind.

## 1. Ziel

Bekannte, ausdrücklich vertrauenswürdig eingerichtete Agenten sollen über einen authentifizierten Handshake kommunizieren können. Fremdsysteme können begrenzte Informationen über Gossip austauschen, ohne dadurch automatisch Vertrauen, Berechtigungen oder Ausführungsrechte zu erhalten. Eigenständige Agenten-Policies bleiben erhalten; der gemeinsame Standard ist ein Kommunikationsvertrag, keine Übernahme fremder Sicherheitsregeln.

## 2. Begriffe und Reichweite

- **127.0.0.1 / localhost:** Loopback-Adresse des jeweiligen Rechners bzw. Netzwerk-Namespace. Sie ist nicht automatisch eine gemeinsame Adresse aller Agenten. Ein Dienst auf Rechner A ist über diese Adresse von Rechner B aus nicht erreichbar.
- **Handshake:** Verbindungsaufbau mit Identitäts-/Schlüsselprüfung, Protokollversion und vereinbarten Fähigkeiten.
- **Gossip:** Verteilung begrenzter Ereignisse oder Zustandsinformationen an ausgewählte Peers. Gossip allein beweist weder Identität noch Wahrheit und autorisiert keine Aktionen.
- **K-Protokoll:** Der Name ist in den bisher geprüften Repository-Inhalten nicht eindeutig spezifiziert. Bedeutung und Stand bleiben UNKNOWN, bis eine konkrete Definition oder Code-Referenz gefunden ist.
- **Autonomie:** Ein Agent darf innerhalb seines ausdrücklich freigegebenen Aufgaben- und Rechtebereichs selbstständig planen und arbeiten. Autonomie hebt Grenzen, Berechtigungen, Kostenlimits oder Sicherheitsprüfungen nicht auf.

## 3. Vertrauensklassen

1. **Bekannter, provisionierter Peer:** Schlüssel und Peer-ID wurden über einen unabhängig vertrauenswürdigen administrativen Weg eingetragen.
2. **Zusätzlich abgesicherter Peer:** Kann optional mTLS, kurzlebige Sitzungsschlüssel, Replay-Schutz und engere Fähigkeiten nutzen. Zusätzliche Absicherung darf nicht stillschweigend zur Pflicht aller kompatiblen Peers erklärt werden, wenn der Betreiber den Basisbetrieb freigegeben hat.
3. **Unbekannter Fremd-Peer:** Nur isolierter, eingeschränkter Austausch-/Quarantänepfad. Kein Geheimniszugriff, keine privilegierten Aktionen, keine Änderung von Vertrauenslisten und keine automatische Ausführung gelieferter Anweisungen.
4. **Gesperrter/widerrufener Peer:** Handshake und Nachrichten ablehnen und den Entscheidungsgrund protokollieren.

Eine Modellantwort, ein Gossip-Eintrag oder eine Peer-Nachricht darf sich nicht selbst als vertrauenswürdig autorisieren.

## 4. Handshake-Mindestablauf

1. Peer-ID, Protokollversion und gewünschte Fähigkeiten austauschen.
2. Nonce oder anderen Frischewert gegen Wiederholungsangriffe verwenden.
3. Signatur über eine kanonische, eindeutig serialisierte Nachricht prüfen.
4. Öffentlichen Schlüssel gegen das unabhängig provisionierte Vertrauensregister prüfen; unbekannte, widerrufene oder fehlerhafte Schlüssel fail-closed ablehnen.
5. Version, Fähigkeiten, Gültigkeit, Größenlimits und Richtlinien auf beiden Seiten prüfen.
6. Sitzung mit minimalen Rechten aufbauen; falls erforderlich verschlüsselten Transport und kurzlebige Sitzungsschlüssel verwenden.
7. Peer-ID, Schlüssel-ID, Protokollversion, Zeit, Entscheidung und Audit-Referenz protokollieren. Niemals private Schlüssel oder Zugangsdaten loggen.

Eine gültige Signatur beweist nur die Bindung an den geprüften Schlüssel, nicht die Wahrheit jeder Aussage und nicht die Berechtigung zu jeder Aktion.

## 5. Gossip-Mindestregeln

- Signierte, größenbegrenzte Nachrichten mit Ereignis-ID, Absender, Frische-/Zeitinformation, Protokollversion, Inhaltstyp und Quellenreferenzen.
- Absender-/Schlüsselstatus prüfen, soweit bekannt; unbekannte Herkunft als UNKNOWN markieren.
- Duplikate erkennen; Hop-Limit, Ablaufzeit, Rate-Limits und Nachrichtengrößen begrenzen.
- Weiterleitung nur an erlaubte Peers; Broadcast-Schleifen verhindern.
- Gossip-Inhalte sind Daten, keine Befehle. Keine gelieferten Skripte, Prompts, Links, Tool-Aufrufe oder Berechtigungsanfragen automatisch ausführen.
- Herkunft erhalten und Behauptungen durch Weiterleitung nicht auf VERIFIED hochstufen.
- Widersprüche und veraltete Informationen markieren; fehlende Evidenz bleibt UNKNOWN, nicht automatisch Mehrheitswahrheit.
- Widerrufe kontrolliert verteilen; nie allein einer nicht authentifizierten Fremdmeldung vertrauen.
- Daten minimieren und Aufbewahrungsfristen berücksichtigen.

## 6. Autonome Aufgaben und Delegation

Jede Aufgabe enthält mindestens `task_id`, `goal`, `scope`, `deadline`, `budget_limits`, `allowed_actions`, `forbidden_actions`, `authorization`, `capabilities`, `input_refs`, `trust_level`, `expected_evidence`, `success_criteria`, `status`, `result`, `artifacts`, `errors` und `next_action`.

- Nur explizit freigegebene Werkzeuge und Systeme verwenden.
- `PRIVILEGES_NEW <= PRIVILEGES_OLD`; Delegation darf Rechte nicht erhöhen.
- Schreibende Änderungen in getrennten Branches vorbereiten und Diffs sowie passende Tests prüfen.
- Kein automatischer Merge, Force-Push, Löschen, Produktionszugriff oder externe Veröffentlichung ohne entsprechende Freigabe.
- Bei Timeout oder unklarem Ergebnis UNKNOWN melden und vor riskanten Wiederholungen den tatsächlichen Zustand prüfen.
- Optionale Agenten/Fremdmodelle isolieren; ihr Ausfall darf den Kern nicht unkontrolliert beeinträchtigen.
- Kosten-, Zeit-, Speicher-, Parallelitäts- und Wiederholungsgrenzen setzen.
- Stoppen, Widerrufen und Rückfall auf einen bekannten Zustand ermöglichen.

## 7. Bezug zu vorhandenen Bausteinen

Das Core-Repository enthält `docs/TRUSTED_PEER_KEY_REGISTRY.md`. Die Datei beschreibt einen fail-closed Schlüssel-Lookup und nennt Ed25519. Sie weist darauf hin, dass der Aufrufer die Signatur weiterhin prüfen muss und der Baustein weder Schlüssel verteilt noch eine reale Peer-Authentifizierung oder Produktionsbereitstellung beweist.

Die Aurelia-Prisma-Dokumentation beschreibt `http://127.0.0.1:8001/v1/dual_orchestrate`. Das ist ein lokaler Loopback-Endpunkt und nicht automatisch von anderen Rechnern oder ChatGPT aus erreichbar.

Vor Integration tatsächliche Implementierungen, Aufrufstellen, Tests und Abhängigkeiten prüfen. Vorhandene Komponenten erweitern statt unnötig duplizieren. Abweichungen zwischen Dokumentation und Code ausdrücklich festhalten.

## 8. Sicherheitsanforderungen für externe Verbindungen

Keine lokalen Dienste ungeschützt ins Internet exponieren. Authentifizierung, Autorisierung, TLS, Rate-Limits, Zeitlimits, Eingabevalidierung, Antwortgrößen und erlaubte Zielhosts prüfen. Interne Metadaten-/Admin-Endpunkte und SSRF verhindern. Geheimnisse gehören nicht in Quellcode, Prompts, Issues, PRs oder Logs. Externe Eingaben bleiben nicht vertrauenswürdige Daten.

## 9. Test- und Nachweisplan

1. Unit-Tests: gültige/ungültige Signaturen, unbekannte/widerrufene Schlüssel, falsche Versionen, Nonce-Wiederverwendung, manipulierte Nachrichten.
2. Gossip-Tests: Duplikate, Schleifen, abgelaufene/zu große Nachrichten, widersprüchliche Ereignisse, Befehlsinhalte in Fremddaten.
3. Autorisierungstests: ungenehmigte Schreib-, Lösch-, Merge- und Delegationsaktionen werden abgewiesen.
4. Isolationstest: Ausfall eines optionalen Peers stoppt den Kern nicht unkontrolliert.
5. Integrationstest mit zwei ausdrücklich konfigurierten Test-Peers in isolierter Umgebung.
6. CI-Nachweis und realer Betriebsnachweis getrennt erfassen: Umgebung, Commit, Kommando, Zeit, Ergebnis, Artefakte und offene Risiken.
7. Reifegrad erst mit Nachweisen erhöhen: DOCUMENTED → IMPLEMENTED → TESTED → VERIFIED; PRODUCTION benötigt separate Betriebs- und Sicherheitsfreigabe.

## 10. Reality-First-Status zum Zeitpunkt der Dokumentation

- Kommunikations-Lernblock im Core: gemergt; dokumentierte Grundlage.
- Trusted-Peer-Key-Registry: dokumentierter Baustein; Integration und Laufzeitstatus nicht nachgewiesen.
- Handshake zwischen realen Agenten: UNKNOWN, bis ein reproduzierbarer Integrationstest vorliegt.
- Gossip-Code: in den bisher geprüften Standardzweigen nicht eindeutig gefunden; weitere Branches/lokale Dateien sind nicht ausgeschlossen.
- K-Protokoll: Bedeutung und Implementierungsstand UNKNOWN.
- Port 8001: dokumentierte Adresse; Erreichbarkeit und Authentifizierung nicht live geprüft.
- Autonomer Betrieb aller Agenten: UNKNOWN.

## 11. Kleinster sicherer nächster Schritt

Zuerst die vorhandene Schlüsselprüfung und die tatsächlichen Agenten-Aufrufstellen im Code identifizieren. Danach einen isolierten Zwei-Peer-Test mit Testschlüsseln ergänzen, ohne Produktionskonfiguration, Geheimnisse oder bestehende Prompts zu verändern. Gossip erst ergänzen, wenn Nachrichtenformat, Vertrauensklassen, Duplikaterkennung und Begrenzungen getestet sind.

**Grundsatz:** Zusammenarbeit ermöglichen, Vertrauen nicht erraten. Dokumentation, Code, Test und realer Betrieb bleiben getrennte Nachweisstufen.
